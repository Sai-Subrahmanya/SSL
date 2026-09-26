"""Logical storage abstraction.

Record lifecycle (``PR-STORAGE-009``, ``D-035``)::

    CREATED -> STORED -> PENDING_UPLOAD -> UPLOADED -> CONFIRMED -> RETAINED

Key semantics:

* a record is valid only when its **commit marker** is set (``PR-STORAGE-003``),
* **upload confirmation is not deletion** - ``CONFIRMED`` only permits removal
  from the pending upload queue,
* automatic deletion is disabled by default (``PR-STORAGE-005``),
* a storage-full condition is explicit and never silently drops records
  (``PR-STORAGE-006``).

The abstraction is deliberately medium-independent: no flash chip, file
system or memory layout is implied.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from .enums import RecordLifecycleState, RecordType
from .errors import StorageError, StorageFullError
from .identity import Identifier
from .time_model import Timestamp

def compute_crc32(data: bytes) -> int:
    """Deterministic CRC-32 (same polynomial as zlib) over ``data``."""
    import zlib

    return zlib.crc32(data) & 0xFFFFFFFF

@dataclass
class StorageRecord:
    """A persisted record with its integrity envelope."""

    sequence_number: int
    timestamp: Timestamp
    record_type: RecordType
    payload: Dict[str, object]
    device_id: Identifier
    lifecycle_state: RecordLifecycleState = RecordLifecycleState.CREATED
    crc: Optional[int] = None
    commit_marker: bool = False
    upload_attempts: int = 0

    @property
    def sequence(self) -> int:
        return self.sequence_number

    def compute_crc(self) -> int:
        import json

        body = json.dumps(self.payload, sort_keys=True, separators=(",", ":"))
        header = "%d|%d|%s|%s" % (
            self.sequence_number,
            self.timestamp.ticks,
            self.record_type.value,
            str(self.device_id),
        )
        return compute_crc32((header + "|" + body).encode("utf-8"))

    def integrity_ok(self) -> bool:
        if self.crc is None:
            return False
        return self.crc == self.compute_crc()

    def is_valid(self) -> bool:
        """A record is valid only when committed and integrity-checked."""
        return self.commit_marker and self.integrity_ok()

@dataclass
class RetentionPolicy:
    """Retention configuration.

    Automatic deletion is disabled by default. ``minimum_retention_ticks``
    is a hard floor that no policy may violate; the numeric value is an open
    engineering decision (assumption ``A-29``) and defaults to ``None``.
    """

    automatic_deletion: bool = False
    minimum_retention_ticks: Optional[int] = None

    def within_minimum_retention(self, record: StorageRecord, ticks: int) -> bool:
        """True while the record is still inside the hard minimum retention."""
        if self.minimum_retention_ticks is None:
            return False
        return (ticks - record.timestamp.ticks) < self.minimum_retention_ticks

    def may_delete(self, record: StorageRecord, ticks: int) -> bool:
        """Whether an *authorized* deletion is permitted right now.

        Automatic deletion is a separate question (see ``may_auto_delete``):
        the default policy disables automatic deletion, not authorized
        deletion.
        """
        return not self.within_minimum_retention(record, ticks)

    def may_auto_delete(self, record: StorageRecord, ticks: int) -> bool:
        """Whether the configured policy would delete the record automatically."""
        return self.automatic_deletion and self.may_delete(record, ticks)

class RecordStore:
    """A deterministic, medium-independent record store.

    The store models the semantics that matter for validation: commit
    markers, CRC integrity, a pending upload queue, a retained historical
    store, corruption detection, power-loss recovery and a storage-full
    condition.
    """

    def __init__(
        self,
        capacity: Optional[int] = None,
        retention: Optional[RetentionPolicy] = None,
        on_delete=None,
    ) -> None:
        """Create a record store.

        ``on_delete`` is an optional callback invoked as
        ``on_delete(record, actor, ticks)`` whenever a retained record is
        deleted, so the caller can raise the deletion audit event required by
        ``PR-STORAGE-009``. Deletion is never silent.
        """
        if capacity is not None and capacity <= 0:
            raise StorageError("capacity must be positive when specified")
        self._capacity = capacity
        self._retention = retention or RetentionPolicy()
        self._records: Dict[int, StorageRecord] = {}
        self._pending_upload: List[int] = []
        self._sequence = 0
        self._full = False
        self._power_lost = False
        self._deleted: List[int] = []
        self._on_delete = on_delete

    # ------------------------------------------------------------------
    # properties
    # ------------------------------------------------------------------
    @property
    def records(self) -> Tuple[StorageRecord, ...]:
        return tuple(self._records.values())

    @property
    def pending_upload(self) -> Tuple[StorageRecord, ...]:
        return tuple(self._records[s] for s in self._pending_upload if s in self._records)

    @property
    def retained(self) -> Tuple[StorageRecord, ...]:
        return tuple(
            r
            for r in self._records.values()
            if r.lifecycle_state
            in (RecordLifecycleState.RETAINED, RecordLifecycleState.CONFIRMED)
        )

    @property
    def is_full(self) -> bool:
        return self._full

    @property
    def retention(self) -> RetentionPolicy:
        return self._retention

    @property
    def deleted_sequences(self) -> Tuple[int, ...]:
        return tuple(self._deleted)

    def __len__(self) -> int:
        return len(self._records)

    # ------------------------------------------------------------------
    # write path
    # ------------------------------------------------------------------
    def create(
        self,
        record_type: RecordType,
        payload: Dict[str, object],
        timestamp: Timestamp,
        device_id: Identifier,
    ) -> StorageRecord:
        """Create, commit and store a record, then queue it for upload.

        Raises :class:`StorageFullError` when the store cannot accept the
        record. The condition is never silent (``PR-STORAGE-006``).
        """
        if self._power_lost:
            raise StorageError("store is in a power-loss state; recover() first")
        if self._capacity is not None and len(self._records) >= self._capacity:
            self._full = True
            raise StorageFullError(
                "store is full (%d of %d records); new record not accepted"
                % (len(self._records), self._capacity)
            )

        self._sequence += 1
        record = StorageRecord(
            sequence_number=self._sequence,
            timestamp=timestamp,
            record_type=record_type,
            payload=dict(payload),
            device_id=device_id,
        )
        # commit: CRC then commit marker, in that order (PR-STORAGE-003)
        record.crc = record.compute_crc()
        record.commit_marker = True
        record.lifecycle_state = RecordLifecycleState.STORED
        self._records[record.sequence_number] = record
        self._pending_upload.append(record.sequence_number)
        record.lifecycle_state = RecordLifecycleState.PENDING_UPLOAD
        return record

    # ------------------------------------------------------------------
    # upload path (queue removal is NOT deletion)
    # ------------------------------------------------------------------
    def mark_uploaded(self, sequence_number: int) -> StorageRecord:
        record = self._require(sequence_number)
        record.upload_attempts += 1
        record.lifecycle_state = RecordLifecycleState.UPLOADED
        return record

    def mark_confirmed(self, sequence_number: int) -> StorageRecord:
        """Record upstream confirmation.

        The record leaves the *pending upload queue* and is marked
        ``RETAINED``. The historical record is **not** deleted.
        """
        record = self._require(sequence_number)
        record.lifecycle_state = RecordLifecycleState.CONFIRMED
        if sequence_number in self._pending_upload:
            self._pending_upload.remove(sequence_number)
        record.lifecycle_state = RecordLifecycleState.RETAINED
        return record

    def upload_confirmed(self, sequence_number: int) -> StorageRecord:
        """Alias kept for readability at call sites."""
        return self.mark_confirmed(sequence_number)

    def next_pending(self) -> Optional[StorageRecord]:
        pending = self.pending_upload
        return pending[0] if pending else None

    # ------------------------------------------------------------------
    # integrity / corruption
    # ------------------------------------------------------------------
    def detect_corruption(self) -> Tuple[StorageRecord, ...]:
        """Return records that fail their integrity check."""
        corrupt = []
        for record in self._records.values():
            if record.lifecycle_state is RecordLifecycleState.DELETED:
                continue
            if not record.commit_marker or not record.integrity_ok():
                if record.lifecycle_state is not RecordLifecycleState.CORRUPT:
                    record.lifecycle_state = RecordLifecycleState.CORRUPT
                corrupt.append(record)
        return tuple(corrupt)

    def corrupt(self, sequence_number: int) -> StorageRecord:
        """Simulate storage corruption of a committed record."""
        record = self._require(sequence_number)
        record.payload = dict(record.payload)
        record.payload["__corrupted__"] = True
        record.lifecycle_state = RecordLifecycleState.CORRUPT
        return record

    # ------------------------------------------------------------------
    # power loss
    # ------------------------------------------------------------------
    def simulate_power_loss(self) -> Tuple[int, ...]:
        """Simulate an abrupt power loss.

        Records whose commit marker was never set are incomplete and will be
        discarded on recovery. Returns the sequence numbers affected.
        """
        incomplete = tuple(
            r.sequence_number for r in self._records.values() if not r.commit_marker
        )
        self._power_lost = True
        return incomplete

    def recover(self) -> Tuple[StorageRecord, ...]:
        """Recover to a consistent state after power loss.

        Incomplete records are discarded; corrupt records are reported and
        excluded from the pending upload queue. Returns the discarded records.
        """
        discarded = []
        for sequence in list(self._records):
            record = self._records[sequence]
            if not record.commit_marker or not record.integrity_ok():
                record.lifecycle_state = RecordLifecycleState.CORRUPT
                discarded.append(record)
                del self._records[sequence]
                if sequence in self._pending_upload:
                    self._pending_upload.remove(sequence)
        self._power_lost = False
        return tuple(discarded)

    # ------------------------------------------------------------------
    # deletion (explicit, authorized, audited)
    # ------------------------------------------------------------------
    def delete(self, sequence_number: int, actor: str, ticks: int) -> StorageRecord:
        """Explicitly delete a retained record.

        Refuses to delete anything still inside the minimum retention window,
        and refuses to delete a record that is still pending upload.
        """
        record = self._require(sequence_number)
        if sequence_number in self._pending_upload:
            raise StorageError(
                "record %d is still pending upload and cannot be deleted"
                % sequence_number
            )
        if self._retention.within_minimum_retention(record, ticks):
            raise StorageError(
                "record %d is inside the minimum retention window" % sequence_number
            )
        record.lifecycle_state = RecordLifecycleState.DELETED
        self._deleted.append(sequence_number)
        if self._on_delete is not None:
            self._on_delete(record, actor, ticks)
        return record

    def automatic_deletion_candidates(self, ticks: int) -> Tuple[StorageRecord, ...]:
        """Records that a configured retention policy would delete.

        With the default policy this is always empty.
        """
        if not self._retention.automatic_deletion:
            return ()
        return tuple(
            r
            for r in self._records.values()
            if r.lifecycle_state is RecordLifecycleState.RETAINED
            and self._retention.may_auto_delete(r, ticks)
        )

    # ------------------------------------------------------------------
    def _require(self, sequence_number: int) -> StorageRecord:
        record = self._records.get(sequence_number)
        if record is None:
            raise StorageError("unknown record sequence %d" % sequence_number)
        return record
