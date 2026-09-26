"""Logical time handling for the digital prototype.

The digital prototype models **logical** clock semantics only:

* a deterministic monotonic logical clock (no wall-clock dependency),
* timestamp generation,
* offline timestamps with an explicit validity indication,
* synchronization state and recovery.

It does **not** model, and must not be used to claim validation of, physical
RTC behaviour such as backup retention duration, leakage, temperature
effects, oscillator accuracy or power-interruption behaviour
(``PR-TIME-005``, ``D-039``, assumption ``A-26``).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

from .enums import TimeSyncState
from .errors import ValidationError
from .identity import Identifier


@dataclass(frozen=True, order=True)
class Timestamp:
    """A record timestamp carrying its own validity indication.

    ``ticks`` is a monotonic logical tick count. ``sync_state`` records how
    trustworthy the wall-clock interpretation is.
    """

    ticks: int
    sync_state: TimeSyncState

    def __post_init__(self) -> None:
        if self.ticks < 0:
            raise ValidationError("timestamp ticks must be non-negative")

    @property
    def synchronized(self) -> bool:
        return self.sync_state == TimeSyncState.SYNCHRONIZED

    @property
    def uncertain(self) -> bool:
        return self.sync_state in (TimeSyncState.UNCERTAIN, TimeSyncState.LOST)

    def as_datetime(self, epoch: datetime) -> datetime:
        """Deterministic wall-clock interpretation against a fixed epoch."""
        return epoch + timedelta(milliseconds=self.ticks)

    def isoformat(self, epoch: datetime) -> str:
        return self.as_datetime(epoch).replace(tzinfo=timezone.utc).isoformat()


class LogicalClock:
    """A deterministic monotonic clock driven only by explicit ``advance`` calls.

    Using an explicit clock keeps the whole digital prototype reproducible:
    no test or scenario depends on wall-clock time.
    """

    def __init__(self, start_ticks: int = 0, epoch: Optional[datetime] = None) -> None:
        if start_ticks < 0:
            raise ValidationError("start_ticks must be non-negative")
        self._ticks = int(start_ticks)
        self.epoch = epoch or datetime(2026, 1, 1, tzinfo=timezone.utc)

    @property
    def ticks(self) -> int:
        return self._ticks

    def advance(self, ticks: int = 1) -> int:
        """Advance the clock and return the new tick count."""
        if ticks < 0:
            raise ValidationError("cannot advance the clock backwards")
        self._ticks += int(ticks)
        return self._ticks

    def timestamp(self, sync_state: TimeSyncState = TimeSyncState.SYNCHRONIZED) -> Timestamp:
        return Timestamp(ticks=self._ticks, sync_state=sync_state)


@dataclass
class TimeModel:
    """Per-device logical time state.

    Tracks the local clock, the synchronization state, when the device was
    last synchronized, and a configurable drift model used to simulate an
    unsynchronized node whose local clock walks away from master time.
    """

    clock: LogicalClock
    device_id: Identifier
    sync_state: TimeSyncState = TimeSyncState.UNSYNCHRONIZED
    last_sync_ticks: Optional[int] = None
    #: Logical ticks of drift accumulated per clock tick while unsynchronized.
    drift_ticks_per_tick: int = 0
    #: How long a device may stay unsynchronized before its time is UNCERTAIN.
    #: ``0`` means "uncertain as soon as synchronization is lost".
    uncertainty_threshold_ticks: int = 0

    def __post_init__(self) -> None:
        if self.drift_ticks_per_tick < 0:
            raise ValidationError("drift_ticks_per_tick must be non-negative")
        if self.uncertainty_threshold_ticks < 0:
            raise ValidationError("uncertainty_threshold_ticks must be non-negative")

    # -- local clock -------------------------------------------------------
    @property
    def ticks(self) -> int:
        return self.clock.ticks

    def advance(self, ticks: int = 1) -> int:
        """Advance local time, accumulating modelled drift while unsynchronized."""
        self.clock.advance(ticks)
        if self.sync_state is not TimeSyncState.SYNCHRONIZED and self.drift_ticks_per_tick:
            self.clock.advance(self.drift_ticks_per_tick * ticks)
        self._refresh_uncertainty()
        return self.clock.ticks

    # -- synchronization ---------------------------------------------------
    def synchronize(self, master_ticks: int) -> Timestamp:
        """Adopt master time and return the resulting timestamp."""
        if master_ticks < 0:
            raise ValidationError("master_ticks must be non-negative")
        if self.clock.ticks < master_ticks:
            self.clock.advance(master_ticks - self.clock.ticks)
        self.sync_state = (TimeSyncState.SYNCHRONIZED if self.clock.ticks == master_ticks
                           else TimeSyncState.UNCERTAIN)
        self.last_sync_ticks = self.clock.ticks
        return self.now()

    def mark_unsynchronized(self) -> None:
        """Record that synchronization has been lost.

        Uncertainty is re-evaluated immediately: a timestamp produced right
        after losing synchronization must not still claim to be synchronized.
        """
        self.sync_state = TimeSyncState.UNSYNCHRONIZED
        self._refresh_uncertainty()

    def mark_lost(self) -> None:
        self.sync_state = TimeSyncState.LOST

    def _refresh_uncertainty(self) -> None:
        """Re-evaluate whether local time is still trustworthy.

        A device that has never been synchronized is uncertain from the start;
        otherwise the elapsed time since the last successful synchronization is
        compared against the configured threshold. A synchronized device whose
        local clock has walked past the threshold becomes UNCERTAIN as well.
        """
        if self.sync_state is TimeSyncState.LOST:
            return
        reference = 0 if self.last_sync_ticks is None else self.last_sync_ticks
        elapsed = self.clock.ticks - reference
        if elapsed >= self.uncertainty_threshold_ticks:
            self.sync_state = TimeSyncState.UNCERTAIN

    # -- accessors ---------------------------------------------------------
    def now(self) -> Timestamp:
        return Timestamp(ticks=self.clock.ticks, sync_state=self.sync_state)

    def seconds_since_sync(self, ticks_per_second: int = 1000) -> Optional[float]:
        if self.last_sync_ticks is None:
            return None
        return (self.clock.ticks - self.last_sync_ticks) / float(ticks_per_second)
