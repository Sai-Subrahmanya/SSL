"""System-level validation of the implemented V1 digital system.

Each test in this module validates a property that a requirement states in its
own words, across the whole hierarchy rather than one component at a time.
Every test drives the existing subsystems (real ``LampNode``,
``GroupController``, ``MasterControlCenter``, command, authorization, storage,
fault, notification and time components); nothing is replaced by a stand-in and
no new production behaviour is introduced here.

Covered properties:

* PR-OFFLINE-001/002/003 and PR-COMM-009 - the field layer keeps functioning
  while no supervision layer is reachable at all, and the work it did is not
  lost when the upstream link returns.
* PR-OFFLINE-005 - a recovery interrupted halfway claims nothing as delivered
  and loses nothing, and the remainder arrives exactly once afterwards.
* PR-CONTROL-006 and PR-FAULT-009 - no fault condition, acknowledged or not,
  ever switches the lamp off or engages the (unused) protection hook.
* PR-MEASURE-003 - energy accumulates proportionally and monotonically and
  survives a restart; only an authorized reset clears it.
* PR-CONFIG-005 - an *applied* configuration and its version survive a
  restart, and the version really did persist rather than reset to zero.

What each of these would detect in a real installation: a hidden dependency of
lighting operation on supervision connectivity, silent record loss or a false
delivery claim across a recovery outage, a fault path that darkens the street,
an energy counter that resets on restart, and a configuration that silently
reverts to defaults.

Digital-only boundary: as everywhere else in this repository these tests prove
model behaviour - logical clock, in-memory bus, modelled devices. They say
nothing about mains, EMC, relay life, physical RTC retention or any other
hardware property.
"""

from __future__ import annotations

import pytest

from conftest import healthy_sources
from fault_injection import ENGINEER, OPERATOR, under_current
from mcc_harness import MccSim
from test_integration import (
    GRP1,
    SITE,
    integrated,
    observe,
    off_sources,
    report,
)
from sslv1.comm import MessageType
from sslv1.enums import (
    CommandState,
    Freshness,
    LampAvailability,
    ConfiguredMode,
    FaultState,
    NotificationState,
    OverrideState,
    RecordType,
)
from sslv1.identity import Identifier
from sslv1.mcc import MccUpstreamLink


# ---------------------------------------------------------------------------
# PR-OFFLINE-001 / -002 / -003, PR-COMM-009 - no supervision layer at all
# ---------------------------------------------------------------------------
def test_local_operation_survives_a_total_supervision_outage():
    """No MCC, no upstream link, no controller traffic - the lamp still works.

    The node is driven only by its own control cycle, exactly as a field
    device whose bus master and backhaul are both down. Nothing is polled and
    nothing is transmitted, so any dependence of local lighting operation on a
    supervision layer shows up as a lamp that stops switching.
    """
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    sim.set_upstream(SITE, GRP1, False)
    transmitted_before = sim.bus(SITE, GRP1).stats.transmitted

    # Dark room: the automatic decision is local and must switch the lamps on.
    for lamp in sim.lamp_ids(SITE, GRP1):
        sim.step(SITE, GRP1, lamp, sources=healthy_sources(light_level=10.0),
                 ticks=sim.clock.ticks + 1000)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-02") is True

    # Bright room with a de-energised load: still local, still works.
    for lamp in sim.lamp_ids(SITE, GRP1):
        sim.step(SITE, GRP1, lamp, sources=off_sources(),
                 ticks=sim.clock.ticks + 1000)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-02") is False

    # Nothing crossed the bus: no poll, no command, no supervision traffic.
    assert sim.bus(SITE, GRP1).stats.transmitted == transmitted_before
    # The MCC, which was never able to observe anything, must not have invented
    # a view: it has no records and no healthy lamp.
    assert sim.mcc.upstream_records(SITE, GRP1) == ()
    unreachable = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert unreachable.availability is LampAvailability.UNAVAILABLE, \
        "with the upstream down the MCC cannot supervise the lamp"
    assert unreachable.freshness is Freshness.UNKNOWN, "and it has no current view"
    assert unreachable.measured_ticks is None

    # The offline work was recorded locally, not discarded.
    node = sim.node(SITE, GRP1, "LAMP-01")
    measurements = [r for r in node.storage.records
                    if r.record_type is RecordType.MEASUREMENT]
    assert len(measurements) == 2, "both cycles are locally recorded"

    # And it is not lost when the upstream link comes back: the recovery step
    # delivers the history that accumulated while nothing was reachable.
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.EVENT_REPORT, site=SITE, group=GRP1)
    sim.set_upstream(SITE, GRP1, True)
    outcome = sim.mcc.recover_upstream(SITE, GRP1)[
        (Identifier(SITE), Identifier(GRP1))]
    assert outcome["recovered"] is True
    assert outcome["remaining"] == []
    received = sim.mcc.upstream_records(SITE, GRP1)
    assert received, "the field history reached the MCC after recovery"
    assert any(r.record_type is RecordType.MEASUREMENT for r in received)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability.value == "HEALTHY"


# ---------------------------------------------------------------------------
# PR-OFFLINE-005 / PR-STORAGE-008 - an interrupted recovery
# ---------------------------------------------------------------------------
class InterruptingUpstream(MccUpstreamLink):
    """The MCC end of the link, with a bounded number of accepted uploads.

    The link reports itself as available (the outage is over as far as the
    controller can tell) but stops accepting records after ``accept`` uploads,
    which models the upstream going down *again* during the replay.
    """

    def __init__(self, mcc, site, group, accept):
        super().__init__(mcc, site, group)
        self._remaining = accept

    def upload(self, record):
        if self._remaining <= 0:
            return False
        self._remaining -= 1
        return super().upload(record)

    def accept_more(self, count=10_000):
        self._remaining = count


def test_recovery_interrupted_midway_claims_nothing_and_loses_nothing():
    """Half a replay is reported as half a replay - never as a full delivery."""
    sim = MccSim(
        lamps_per_group=2,
        status_max_age_ticks=100_000,
        upstream_factory=lambda mcc, site, group: InterruptingUpstream(
            mcc, site, group, accept=3),
    )
    controller = sim.gc(SITE, GRP1)
    sim.cycle(ticks=1000)
    pending_before = [r.sequence_number for r in controller.storage.pending_upload]
    assert len(pending_before) > 3, "the outage produced a replayable backlog"

    first = sim.mcc.recover_upstream(SITE, GRP1)[
        (Identifier(SITE), Identifier(GRP1))]
    assert first["recovered"] is True
    assert first["confirmed"] == 3, "only the accepted uploads are confirmed"
    assert first["uploaded"] == 3
    assert len(sim.mcc.upstream_records(SITE, GRP1)) == 3, "no phantom receipts"
    # Everything else is still pending and reported as such, not as delivered.
    remaining = [r.sequence_number for r in controller.storage.pending_upload]
    assert first["remaining"] == remaining
    assert len(remaining) > 0, "the backlog was not fully replayed"
    assert first["failed"] == len(remaining)
    assert not set(first["remaining"]) & {r.sequence_number
                                         for r in sim.mcc.upstream_records(SITE, GRP1)}

    # The link returns for good: the remainder arrives, once, in sequence
    # order, and nothing is lost or duplicated.
    sim.upstream(SITE, GRP1).accept_more()
    second = sim.mcc.recover_upstream(SITE, GRP1)[
        (Identifier(SITE), Identifier(GRP1))]
    assert second["remaining"] == []
    assert controller.storage.pending_upload == ()
    received = sim.mcc.upstream_records(SITE, GRP1)
    sequences = [r.sequence_number for r in received]
    assert len(sequences) == len(set(sequences)), "no record was stored twice"
    assert sequences == sorted(sequences), "arrival order follows sequence order"
    assert sim.mcc.duplicate_uploads == 0, "no duplicate delivery was needed"
    # Exactly the retained history arrived: no loss, no invention.
    assert set(sequences) == {r.sequence_number for r in controller.storage.retained}
    assert len(sequences) == len(controller.storage.retained)


# ---------------------------------------------------------------------------
# PR-CONTROL-006 / PR-FAULT-009 - a fault must never darken the street
# ---------------------------------------------------------------------------
def test_a_fault_never_switches_the_lamp_off_or_engages_protection():
    """The fault and notification machinery is observational, not switching."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True, "dark room, lamp on"

    fault = sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current(),
                              ticks=sim.clock.ticks + 1000)
    assert fault.state is FaultState.CONFIRMED
    assert fault.notification_state in (NotificationState.PENDING,
                                       NotificationState.ACK_PENDING,
                                       NotificationState.REMINDER_DUE)

    # Run the notification machinery far past every configured deadline while
    # the operator never acknowledges. The lamp must stay on and the (unused)
    # protection hook must never be engaged by the fault path.
    for step in range(1, 6):
        sim.step(SITE, GRP1, "LAMP-01",
                 sources=under_current(), ticks=sim.clock.ticks + 60_000)
        assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True, \
            "an unacknowledged fault switched the lamp off (step %d)" % step
    assert node.control.protection.active is False, "no protection condition exists in V1"
    assert fault.state is FaultState.CONFIRMED, "notification timers do not close faults"

    # Acknowledging it is an audit action, not a lighting input either.
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.EVENT_REPORT, site=SITE, group=GRP1)
    assert sim.mcc.active_faults(SITE, GRP1), "the fault is visible upstream"
    node.acknowledge_fault(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 1000)
    sim.step(SITE, GRP1, "LAMP-01", sources=under_current(),
             ticks=sim.clock.ticks + 1000)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True
    assert node.control.active_override is OverrideState.NONE


# ---------------------------------------------------------------------------
# PR-MEASURE-003 - energy accumulation, restart survival, authorized reset
# ---------------------------------------------------------------------------
def test_energy_accumulates_proportionally_and_survives_a_restart():
    """The accumulator is a monitored quantity: it grows, lasts, and is gated."""
    sim = integrated(lamps_per_group=1, status_max_age_ticks=100_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")

    def energy_after(power, moment):
        """Step once at ``power`` and return the energy the node published."""
        sim.step(SITE, GRP1, "LAMP-01", sources=healthy_sources(power=power),
                 ticks=moment + node.config.measurement_interval_ticks)
        return node.last_measurement.energy

    moment = sim.clock.ticks
    start = energy_after(100.0, moment)
    after_one = energy_after(100.0, moment + 1000)
    after_two = energy_after(100.0, moment + 2000)
    assert after_one > start and after_two > after_one, "energy accumulates over time"
    interval_wh = after_two - after_one
    # The increment is proportional to power: doubling the load doubles the
    # energy added over the same configured interval.
    doubled = energy_after(200.0, moment + 3000)
    assert (doubled - after_two) == pytest.approx(2 * interval_wh, rel=1e-9)

    # A watchdog restart is not a reset: the accumulator is retained across it.
    before_restart = node.last_measurement.energy
    node.restart(ticks=node.time.ticks + 1)
    after_restart = energy_after(100.0, node.time.ticks + 100)
    assert after_restart == pytest.approx(before_restart + interval_wh), \
        "the energy accumulated before the restart was not discarded"

    # Only an authorized reset clears it, and the refusal changes nothing.
    denied = node.reset_energy(OPERATOR, ticks=node.time.ticks + 10)
    assert denied.state in (CommandState.FAILED, CommandState.REJECTED)
    assert energy_after(0.0, node.time.ticks + 100) == pytest.approx(after_restart)
    allowed = node.reset_energy(ENGINEER, ticks=node.time.ticks + 20)
    assert allowed.state is CommandState.ACTUAL_STATE_VERIFIED
    # The next reading starts a new accumulation from zero: the counter really
    # was cleared, it just is not rewritten into an already-published sample.
    assert energy_after(100.0, node.time.ticks + 100) == pytest.approx(interval_wh)


# ---------------------------------------------------------------------------
# PR-CONFIG-005 - an applied configuration survives a restart
# ---------------------------------------------------------------------------
def test_an_applied_configuration_and_its_version_survive_a_restart():
    """Persistence is claimed only for a configuration that really changed."""
    sim = integrated(lamps_per_group=1, status_max_age_ticks=100_000)
    observe(sim)
    controller = sim.gc(SITE, GRP1)
    node = sim.node(SITE, GRP1, "LAMP-01")
    assert node.config_version == 0

    record = controller.distribute_configuration(
        Identifier("LAMP-01"),
        {"configured_mode": list(ConfiguredMode).index(ConfiguredMode.FIXED_SCHEDULE),
         "fault_confirmation_count": 5},
        ENGINEER,
        config_version=2,
    )
    sim.pump(SITE, GRP1)
    controller.collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED, record.result
    assert node.config_version == 2

    node.restart(ticks=sim.clock.ticks + 1)
    assert node.config.configured_mode is ConfiguredMode.FIXED_SCHEDULE
    assert node.config.fault_confirmation_count == 5
    assert node.config_version == 2

    # The version really persisted: a write re-using version 2 is refused as
    # stale, and only a strictly newer version is accepted.
    stale = controller.distribute_configuration(
        Identifier("LAMP-01"), {"fault_confirmation_count": 3}, ENGINEER,
        config_version=2)
    sim.pump(SITE, GRP1)
    controller.collect_responses()
    assert stale.state is CommandState.FAILED
    assert node.config.fault_confirmation_count == 5

    # The readback path carries the surviving configuration, so the operator
    # view after a restart is the node's actual state, not a default.
    controller.read_configuration(Identifier("LAMP-01"))
    sim.pump(SITE, GRP1)
    controller.collect_responses()
    readback = controller.registration_for(Identifier("LAMP-01")).configuration
    assert readback["config_version"] == 2
    assert readback["parameters"]["configured_mode"] == list(ConfiguredMode).index(
        ConfiguredMode.FIXED_SCHEDULE)
    report(sim)


def test_an_unsynchronized_node_keeps_time_and_never_claims_synchronized():
    """Local timekeeping continues offline; validity is never invented."""
    sim = integrated(lamps_per_group=1, status_max_age_ticks=100_000)
    node = sim.node(SITE, GRP1, "LAMP-01")
    sim.step(SITE, GRP1, "LAMP-01", sources=healthy_sources(light_level=10.0),
             ticks=1000)
    first = node.last_measurement.timestamp

    # Nothing has synchronized this node and nothing will: the clock still
    # advances (schedules, sampling and offline records need it) but every
    # stamp keeps saying so.
    for step in range(1, 4):
        sim.step(SITE, GRP1, "LAMP-01", sources=healthy_sources(light_level=10.0),
                 ticks=1000 * (step + 1))
        latest = node.last_measurement.timestamp
        assert latest.ticks > first.ticks, "local time keeps running"
        assert latest.uncertain, "unsynchronized time is never presented as valid"
    assert node.time.last_sync_ticks is None

    # The MCC, told that, repeats it: no upstream layer upgrades the claim.
    report(sim)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").time_sync_state.value == "UNCERTAIN"
