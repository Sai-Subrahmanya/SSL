"""Storage model tests (PR-STORAGE-*).

Covers: record lifecycle, commit markers, corruption detection, power-loss
recovery, storage-full visibility, upload confirmation without deletion, and
retention.
"""


import pytest

from sslv1.enums import RecordLifecycleState, RecordType
from sslv1.errors import StorageError, StorageFullError
from sslv1.identity import Identifier
from sslv1.storage import RecordStore, RetentionPolicy, StorageRecord
from sslv1.time_model import Timestamp

DEVICE = Identifier("LAMP-01")


def ts(ticks: int) -> Timestamp:
    return Timestamp(ticks=ticks, sync_state=None) if False else Timestamp(
        ticks=ticks, sync_state=__import__("sslv1.enums", fromlist=["TimeSyncState"]).TimeSyncState.SYNCHRONIZED
    )


@pytest.fixture
def store():
    return RecordStore()


def make_record(store, sequence_ticks=1000, payload=None):
    return store.create(
        record_type=RecordType.MEASUREMENT,
        payload=payload or {"voltage": 230.0},
        timestamp=ts(sequence_ticks),
        device_id=DEVICE,
    )


# --------------------------------------------------------------------------
# 32. storage lifecycle
# --------------------------------------------------------------------------
def test_record_lifecycle_created_to_retained(store):
    record = make_record(store)
    assert record.lifecycle_state is RecordLifecycleState.PENDING_UPLOAD
    assert record.commit_marker is True
    assert record.crc is not None

    store.mark_uploaded(record.sequence_number)
    assert record.lifecycle_state is RecordLifecycleState.UPLOADED

    store.mark_confirmed(record.sequence_number)
    assert record.lifecycle_state is RecordLifecycleState.RETAINED
    assert record.lifecycle_state is RecordLifecycleState.RETAINED


def test_sequence_numbers_are_monotonic(store):
    first = make_record(store, 1000)
    second = make_record(store, 2000)
    assert second.sequence_number == first.sequence_number + 1


def test_records_carry_the_required_envelope(store):
    record = make_record(store)
    assert record.sequence_number >= 1
    assert record.timestamp.ticks == 1000
    assert record.payload == {"voltage": 230.0}
    assert record.crc is not None
    assert record.commit_marker is True


def test_uncommitted_record_is_not_valid():
    record = StorageRecord(
        sequence_number=1,
        timestamp=ts(1000),
        record_type=RecordType.EVENT,
        payload={"a": 1},
        device_id=DEVICE,
    )
    assert record.is_valid() is False
    record.crc = record.compute_crc()
    record.commit_marker = True
    assert record.is_valid() is True


# --------------------------------------------------------------------------
# 33. upload confirmation without deletion
# --------------------------------------------------------------------------
def test_upload_confirmation_does_not_delete_the_record(store):
    record = make_record(store)
    store.mark_uploaded(record.sequence_number)
    store.mark_confirmed(record.sequence_number)

    # The record left the pending upload queue but is still retained.
    assert record.sequence_number not in [r.sequence_number for r in store.pending_upload]
    assert record.sequence_number in [r.sequence_number for r in store.retained]
    assert len(store) == 1
    assert record.lifecycle_state is not RecordLifecycleState.DELETED


def test_queue_removal_and_deletion_are_distinct_operations(store):
    record = make_record(store)
    store.mark_uploaded(record.sequence_number)
    store.mark_confirmed(record.sequence_number)
    assert len(store.retained) == 1
    assert len(store.pending_upload) == 0

    # Deletion is a separate, explicit operation.
    store.delete(record.sequence_number, actor="admin-01", ticks=10_000)
    assert record.lifecycle_state is RecordLifecycleState.DELETED
    assert len(store.retained) == 0


def test_pending_upload_records_cannot_be_deleted(store):
    record = make_record(store)
    with pytest.raises(StorageError):
        store.delete(record.sequence_number, actor="admin-01", ticks=10_000)


# --------------------------------------------------------------------------
# 34. storage full
# --------------------------------------------------------------------------
def test_storage_full_is_explicit_and_never_silent():
    store = RecordStore(capacity=2)
    make_record(store, 1000)
    make_record(store, 2000)
    assert store.is_full is False

    with pytest.raises(StorageFullError):
        make_record(store, 3000)
    assert store.is_full is True
    # The two existing records are untouched.
    assert len(store) == 2


def test_automatic_deletion_is_disabled_by_default(store):
    record = make_record(store, 1000)
    store.mark_uploaded(record.sequence_number)
    store.mark_confirmed(record.sequence_number)
    # No retention policy is configured, so nothing is ever auto-deleted.
    assert store.automatic_deletion_candidates(ticks=10_000_000) == ()


def test_retention_policy_requires_explicit_configuration():
    """Automatic deletion is disabled by default and needs explicit policy."""
    record = StorageRecord(
        sequence_number=1,
        timestamp=ts(1000),
        record_type=RecordType.EVENT,
        payload={},
        device_id=DEVICE,
    )
    default_policy = RetentionPolicy()
    # Authorized deletion is allowed, automatic deletion is not.
    assert default_policy.may_delete(record, ticks=10_000_000) is True
    assert default_policy.may_auto_delete(record, ticks=10_000_000) is False
    assert default_policy.automatic_deletion is False
    assert default_policy.minimum_retention_ticks is None

    configured = RetentionPolicy(automatic_deletion=True, minimum_retention_ticks=5000)
    assert configured.may_delete(record, ticks=10_000) is True
    assert configured.may_delete(record, ticks=2000) is False
    assert configured.may_auto_delete(record, ticks=2000) is False
    assert configured.may_auto_delete(record, ticks=10_000) is True


def test_deletion_inside_minimum_retention_is_refused():
    store = RecordStore(retention=RetentionPolicy(minimum_retention_ticks=5000))
    record = make_record(store, 1000)
    store.mark_uploaded(record.sequence_number)
    store.mark_confirmed(record.sequence_number)
    with pytest.raises(StorageError):
        store.delete(record.sequence_number, actor="admin-01", ticks=3000)
    store.delete(record.sequence_number, actor="admin-01", ticks=9000)
    assert record.lifecycle_state is RecordLifecycleState.DELETED
    assert store.deleted_sequences == (record.sequence_number,)


# --------------------------------------------------------------------------
# corruption and power loss
# --------------------------------------------------------------------------
def test_corrupted_record_is_detected_and_flagged(store):
    record = make_record(store)
    store.corrupt(record.sequence_number)
    corrupt = store.detect_corruption()
    assert record.sequence_number in [r.sequence_number for r in corrupt]
    assert record.lifecycle_state is RecordLifecycleState.CORRUPT
    assert record.integrity_ok() is False


def test_power_loss_discards_incomplete_records(store):
    complete = make_record(store, 1000)
    # Simulate a record whose commit marker was never written.
    store._sequence += 1
    partial = StorageRecord(
        sequence_number=store._sequence,
        timestamp=ts(2000),
        record_type=RecordType.EVENT,
        payload={"partial": True},
        device_id=DEVICE,
    )
    store._records[partial.sequence_number] = partial

    incomplete = store.simulate_power_loss()
    assert partial.sequence_number in incomplete
    assert complete.sequence_number not in incomplete

    discarded = store.recover()
    assert [r.sequence_number for r in discarded] == [partial.sequence_number]
    assert complete.sequence_number in store._records
    assert store.is_full is False


def test_power_loss_recovery_keeps_committed_records_uploadable(store):
    record = make_record(store, 1000)
    store.simulate_power_loss()
    store.recover()
    assert record.sequence_number in [r.sequence_number for r in store.pending_upload]


def test_corrupt_record_is_excluded_from_upload(store):
    record = make_record(store, 1000)
    store.corrupt(record.sequence_number)
    store.simulate_power_loss()
    discarded = store.recover()
    assert record.sequence_number in [r.sequence_number for r in discarded]
    assert record.sequence_number not in [
        r.sequence_number for r in store.pending_upload
    ]


def test_store_refuses_operations_while_in_power_loss_state(store):
    make_record(store, 1000)
    store.simulate_power_loss()
    with pytest.raises(StorageError):
        make_record(store, 2000)


def test_zero_capacity_is_rejected():
    with pytest.raises(StorageError):
        RecordStore(capacity=0)


def test_unknown_sequence_is_rejected(store):
    with pytest.raises(StorageError):
        store.mark_uploaded(999)
