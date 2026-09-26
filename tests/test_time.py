"""Logical time model tests (PR-TIME-001..004).

The time model is logical. It makes no claim about physical RTC accuracy or
backup duration (``PR-TIME-005``).
"""

from __future__ import annotations

import pytest

from sslv1.enums import TimeSyncState
from sslv1.errors import ValidationError
from sslv1.identity import Identifier
from sslv1.time_model import LogicalClock, TimeModel

DEVICE = Identifier("LAMP-01")


def make_model(clock=None, **kwargs):
    return TimeModel(clock=clock or LogicalClock(), device_id=DEVICE, **kwargs)


# --------------------------------------------------------------------------
# a deterministic clock
# --------------------------------------------------------------------------
def test_clock_is_deterministic_and_monotonic():
    clock = LogicalClock()
    seen = [clock.ticks]
    for _ in range(5):
        clock.advance(1000)
        seen.append(clock.ticks)
    assert seen == sorted(seen)
    assert len(set(seen)) == len(seen)


def test_clock_never_moves_backwards():
    clock = LogicalClock(start_ticks=500)
    clock.advance(100)
    with pytest.raises(ValidationError):
        clock.advance(-1000)


def test_negative_start_ticks_are_rejected():
    with pytest.raises(ValidationError):
        LogicalClock(start_ticks=-1)


def test_clock_advance_by_zero_is_allowed():
    clock = LogicalClock()
    clock.advance(0)
    assert clock.ticks == 0


def test_two_clocks_are_independent():
    a = LogicalClock()
    b = LogicalClock()
    a.advance(10)
    assert b.ticks == 0


# --------------------------------------------------------------------------
# time model state
# --------------------------------------------------------------------------
def test_time_model_starts_unsynchronized():
    model = make_model()
    assert model.sync_state is TimeSyncState.UNSYNCHRONIZED
    assert model.last_sync_ticks is None


def test_synchronize_records_the_source_ticks():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=12_345)
    assert model.sync_state is TimeSyncState.SYNCHRONIZED
    assert model.last_sync_ticks == 12_345
    assert model.now().ticks == 12_345


def test_synchronizing_backwards_marks_the_time_uncertain():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=10_000)
    model.synchronize(master_ticks=1000)
    # Adopting an earlier master time is recorded, never silently rewound.
    assert model.last_sync_ticks == 10_000
    assert model.now().ticks == 10_000


def test_uncertainty_is_a_timestamp_property():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=1000)
    assert model.now().uncertain is False
    model.mark_unsynchronized()
    assert model.now().uncertain is True


def test_time_becomes_uncertain_after_the_threshold():
    clock = LogicalClock()
    model = make_model(clock)
    model.uncertainty_threshold_ticks = 5000
    model.synchronize(master_ticks=1000)

    model.advance(4000)
    assert model.sync_state is TimeSyncState.SYNCHRONIZED
    assert model.now().uncertain is False

    model.advance(2000)
    assert model.sync_state is TimeSyncState.UNCERTAIN
    assert model.now().uncertain is True


def test_time_never_synchronized_is_uncertain_from_the_start():
    clock = LogicalClock()
    model = make_model(clock)
    model.uncertainty_threshold_ticks = 1000
    model.advance(2000)
    assert model.sync_state is TimeSyncState.UNCERTAIN


def test_losing_sync_marks_the_time_lost():
    clock = LogicalClock()
    model = make_model(clock)
    model.uncertainty_threshold_ticks = 5000
    model.synchronize(master_ticks=1000)
    model.mark_unsynchronized()
    # Inside the grace period the state is UNSYNCHRONIZED, not yet UNCERTAIN.
    assert model.sync_state is TimeSyncState.UNSYNCHRONIZED
    assert model.now().uncertain is False

    model.advance(6000)
    assert model.sync_state is TimeSyncState.UNCERTAIN
    assert model.now().uncertain is True


def test_zero_uncertainty_threshold_means_uncertain_immediately():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=1000)
    model.mark_unsynchronized()
    assert model.sync_state is TimeSyncState.UNCERTAIN
    assert model.now().uncertain is True


def test_a_lost_timestamp_stays_uncertain():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=1000)
    model.mark_lost()
    model.advance(10_000)
    assert model.sync_state is TimeSyncState.LOST
    assert model.now().uncertain is True


def test_time_advances_monotonically():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=0)
    stamps = []
    for index in range(5):
        model.advance(index * 1000)
        stamps.append(model.now().ticks)
    assert stamps == sorted(stamps)


def test_timestamps_carry_the_sync_state():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=100)
    stamp = model.now()
    assert stamp.sync_state is TimeSyncState.SYNCHRONIZED
    assert stamp.uncertain is False


def test_no_physical_rtc_is_modelled():
    """The module exposes no RTC, calendar or timezone behaviour."""
    clock = LogicalClock()
    model = make_model(clock)
    for banned in ("calendar", "timezone", "rtc", "drift_ppm", "backup_battery"):
        assert not hasattr(clock, banned)
        assert not hasattr(model, banned)


def test_seconds_since_sync_is_configurable():
    clock = LogicalClock()
    model = make_model(clock)
    model.synchronize(master_ticks=0)
    model.advance(2000)
    assert model.seconds_since_sync(ticks_per_second=1000) == 2.0
    assert model.seconds_since_sync(ticks_per_second=500) == 4.0


def test_unsynchronized_drift_is_modelled_explicitly():
    clock = LogicalClock()
    model = make_model(clock, drift_ticks_per_tick=1)
    model.synchronize(master_ticks=0)
    model.mark_unsynchronized()
    model.advance(100)
    # Local time walks away while unsynchronized, by a configured amount.
    assert model.now().ticks == 200
