"""Phase 16 - full digital integration of the V1 subsystems.

Every test in this module drives the *whole* hierarchy in one deterministic
system: Master Control Center over Group Controller over Lamp Nodes, with the
real command, authorization, communication, measurement, fault, notification,
storage and time components. Nothing here replaces a subsystem with a mock; the
only stand-ins are the modelled field devices themselves (``tests/mcc_harness``
builds real ``LampNode``/``GroupController`` objects and pumps frames).

What an integration test in this file must be able to detect:

* a command that is reported as applied while the lamp never changed,
* an MCC view built from anything other than what the group actually reported,
* an offline record that is lost, duplicated or reordered on recovery,
* a restart that resurrects a transaction or presents pre-restart data as live,
* cross-site or cross-group contamination of identifiers, fault or state,
* authorization that can be bypassed by going through the MCC.

Scenarios A-D, the fault path, the offline/store-and-forward path, restart and
reconstruction, multi-group/multi-site operation, communication integrity,
configuration integration, time/freshness and the software-scale check are each
covered by an explicitly named section below.
"""

from __future__ import annotations

import time
from dataclasses import replace

import pytest

from conftest import healthy_sources
from fault_injection import ADMIN, ENGINEER, OPERATOR, VIEWER, under_current
from mcc_harness import MccSim, TICKS_PER_SECOND
from sslv1.comm import MessageType
from sslv1.enums import (
    AggregateHealth,
    CommState,
    CommandState,
    ConfiguredMode,
    ControlSubtype,
    EventType,
    FaultSeverity,
    FaultState,
    FaultType,
    Freshness,
    LampAvailability,
    LampState,
    NotificationState,
    OperatingMode,
    OverrideState,
    RecordLifecycleState,
    RecordType,
    TimeSyncState,
)
from sslv1.errors import AuthorizationError, ConfigurationError
from sslv1.identity import Identifier
from sslv1.mcc import MccUpstreamLink

SITE = "SITE-A"
SITE_B = "SITE-B"
GRP1 = "GRP-01"
GRP2 = "GRP-02"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
def off_sources(light_level=900.0):
    """An observation of a load that really is de-energised."""
    return healthy_sources(light_level=light_level, switching_feedback=LampState.OFF,
                           current=0.0, power=0.0)


def integrated(site_count=1, group_count=1, lamps_per_group=4, **kwargs):
    """A system whose Group Controllers upload into the MCC itself."""
    return MccSim(
        site_count=site_count,
        group_count=group_count,
        lamps_per_group=lamps_per_group,
        upstream_factory=lambda mcc, site, group: MccUpstreamLink(mcc, site, group),
        **kwargs,
    )


def measurement_view_is_current(sim, site=SITE, group=GRP1):
    """True when the group controller holds every lamp's newest reading.

    A pending record is answered one per poll, so a controller that is still
    replaying its node's buffered history is *behind*, not current.
    """
    controller = sim.gc(site, group)
    for node in sim.nodes(site, group):
        newest = node.last_measurement
        if newest is None:
            # A lamp that has never sampled has nothing to catch up with; the
            # "never reported" case is asserted on its own.
            continue
        registration = controller.registration_for(node.lamp_id)
        if registration.last_measurement is None:
            return False
        if registration.last_measurement.timestamp.ticks < newest.timestamp.ticks:
            return False
    return True


def report(sim, site=SITE, group=GRP1, max_rounds=100):
    """Report the field layer's current state to the MCC, never changing it.

    Use this after a deliberate field-layer action, so the observation under
    test is not overwritten by another control cycle. The poll exchange is
    repeated until the controller's measurement view has caught up with the
    nodes' own newest readings - a controller replaying a backed-up history
    must not be mistaken for a controller showing the current state - and the
    convergence is asserted, never skipped.
    """
    sim.rounds(1, MessageType.STATUS_REQUEST, site=site, group=group)
    for _ in range(max_rounds):
        if measurement_view_is_current(sim, site, group):
            break
        sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=site, group=group)
    else:
        raise AssertionError(
            "the group controller never reached the nodes' newest measurement"
        )
    sim.rounds(1, MessageType.FAULT_REPORT, site=site, group=group)
    sim.rounds(1, MessageType.EVENT_REPORT, site=site, group=group)


def observe(sim, ticks=None):
    """Run the field layer and report every lamp to the MCC (no upload)."""
    for site_registration in sim.mcc.sites:
        for group_registration in sim.mcc.groups(site_registration.site_id):
            sim.step_group(site_registration.site_id, group_registration.group_id, ticks=ticks)
    for site_registration in sim.mcc.sites:
        for group_registration in sim.mcc.groups(site_registration.site_id):
            report(sim, site_registration.site_id, group_registration.group_id)


# ===========================================================================
# SCENARIO A - NORMAL AUTOMATIC OPERATION
# ===========================================================================
def test_scenario_a_automatic_operation_from_registration_to_mcc_view():
    """Register -> auto decision -> switch -> report -> aggregate."""
    sim = integrated(lamps_per_group=3, status_max_age_ticks=50_000)

    # Registration: the MCC accepted the hierarchy and both implementations
    # agree about the inventory (the group controller has the nodes too).
    assert sim.mcc.site(SITE).lamp_count == 3
    assert sim.gc(SITE, GRP1).node_count == 3
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False, "documented restart default"

    # Automatic decision: a dark room switches the lamp on.
    decision = sim.step(SITE, GRP1, "LAMP-01",
                        sources=healthy_sources(light_level=10.0), ticks=1000)
    assert decision.effective_mode is OperatingMode.AUTO_SENSOR
    assert decision.commanded_state is LampState.ON
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True

    # Every lamp reports: the group controller receives the state and the MCC
    # derives its view from that report only.
    observe(sim)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.effective_mode is OperatingMode.AUTO_SENSOR
    assert status.commanded_state is LampState.ON
    assert status.actual_state is LampState.ON
    assert status.availability is LampAvailability.HEALTHY
    assert status.voltage == pytest.approx(230.0)
    group = sim.mcc.group_status(SITE, GRP1)
    assert group.health is AggregateHealth.HEALTHY
    assert group.total_lamps == 3 and group.healthy_lamps == 3
    assert sim.mcc.site_status(SITE).health is AggregateHealth.HEALTHY

    # Automatic decision: a bright room with a de-energised load switches the
    # lamp off, and the new state reaches the MCC on the next report.
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1000)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False
    report(sim)
    switched = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert switched.commanded_state is LampState.OFF
    assert switched.actual_state is LampState.OFF
    assert switched.availability is LampAvailability.HEALTHY
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.HEALTHY


def test_normal_operation_records_reach_the_mcc_upstream_end():
    """The measurement/history the field layer produced arrives at the MCC."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    sim.cycle(ticks=1000, forward=True)

    received = sim.mcc.upstream_records(SITE, GRP1)
    assert received, "records were uploaded through the existing link"
    assert {r.record_type for r in received} <= {RecordType.MEASUREMENT, RecordType.EVENT}
    assert sim.gc(SITE, GRP1).storage.pending_upload == ()
    assert sim.mcc.duplicate_uploads == 0

    # The records the MCC holds are the very objects the controller stored.
    stored = {id(record) for record in sim.gc(SITE, GRP1).storage.records}
    assert all(id(r.record) in stored for r in received)
    # Arrival order equals the controller's own sequence order.
    sequences = [r.sequence_number for r in received]
    assert sequences == sorted(sequences)


def test_a_lamp_step_alone_does_not_change_the_mcc_view():
    """The MCC reports what was *reported*, not what the simulation knows."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    before = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")

    # The node changes its state, but no exchange happens afterwards.
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False
    after = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert after.actual_state is before.actual_state is LampState.ON
    assert after.measured_ticks == before.measured_ticks

    # One report later the MCC shows the new truth.
    report(sim)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").actual_state is LampState.OFF


# ===========================================================================
# SCENARIO B - FORCE ON
# ===========================================================================
def test_scenario_b_force_on_survives_the_automatic_decision():
    """MCC -> authorization -> group controller -> node -> MCC, forced on."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False

    record = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-force-on")
    assert record.command.actor == OPERATOR
    assert record.state is CommandState.RECEIVED, "delivery is not success"
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACKNOWLEDGED

    # The lamp really is on, and the automatic "bright room" logic cannot turn
    # it off while the operator override is active.
    sim.step(SITE, GRP1, "LAMP-01", sources=healthy_sources(light_level=900.0), ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True

    report(sim)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.effective_mode is OperatingMode.FORCE_ON
    assert status.active_override is OverrideState.FORCE_ON
    assert status.actual_state is LampState.ON
    assert status.commanded_state is LampState.ON

    # Audit: the command is audited where it was executed, with the actor, and
    # the MCC reads that existing trail.
    events = sim.mcc.events(SITE, GRP1)
    assert any(e.event_type is EventType.COMMAND_VERIFIED for e in events)
    assert sim.mcc.command(SITE, GRP1, "int-force-on") is record


def test_force_on_is_idempotent_and_never_reaches_a_second_lamp():
    sim = integrated(lamps_per_group=3, status_max_age_ticks=50_000)
    observe(sim)
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)
    transmitted = sim.bus(SITE, GRP1).stats.transmitted

    first = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-dup")
    assert sim.bus(SITE, GRP1).stats.transmitted > transmitted, "one transmission"
    after_first = sim.bus(SITE, GRP1).stats.transmitted
    second = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-dup")
    assert second is first
    assert sim.bus(SITE, GRP1).stats.transmitted == after_first, "no retransmission"

    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert sim.node(SITE, GRP1, "LAMP-02").control.active_override is OverrideState.NONE
    assert sim.node(SITE, GRP1, "LAMP-03").control.active_override is OverrideState.NONE


# ===========================================================================
# SCENARIO C - FORCE OFF
# ===========================================================================
def test_scenario_c_force_off_survives_the_automatic_decision():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is True

    record = sim.mcc.force_off(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-force-off")
    assert record.command.actor.actor_id == OPERATOR.actor_id
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED

    # A dark room now *would* switch the lamp on; the override holds it off,
    # and the load feedback confirms the lamp really is still de-energised.
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(light_level=10.0),
             ticks=sim.clock.ticks + 1)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False
    report(sim)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.effective_mode is OperatingMode.FORCE_OFF
    assert status.active_override is OverrideState.FORCE_OFF
    assert status.actual_state is LampState.OFF

    # The other lamp was never commanded and keeps its automatic behaviour.
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").active_override is OverrideState.NONE
    assert sim.node(SITE, GRP1, "LAMP-02").control.active_override is OverrideState.NONE


# ===========================================================================
# SCENARIO D - RETURN TO AUTO
# ===========================================================================
def test_scenario_d_return_to_auto_resumes_automatic_control():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-auto-on")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    sim.step(SITE, GRP1, "LAMP-01", ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    report(sim)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").active_override is OverrideState.FORCE_ON

    # RETURN_TO_AUTO is an action, not a mode: the override is released.
    record = sim.mcc.return_to_auto(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-auto")
    assert record.command.actor == OPERATOR
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED

    report(sim)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.active_override is OverrideState.NONE
    assert status.effective_mode is OperatingMode.AUTO_SENSOR
    assert status.actual_state is LampState.OFF, "the automatic decision took over"
    assert sim.node(SITE, GRP1, "LAMP-01").control.lamp_is_on is False


# ===========================================================================
# FAULT -> MCC END TO END
# ===========================================================================
def test_fault_path_from_measurement_to_mcc_and_back_to_clear():
    """Detect -> confirm -> retain -> group -> MCC -> repair -> clear."""
    sim = integrated(lamps_per_group=3, status_max_age_ticks=100_000)
    observe(sim)

    fault = sim.confirm_fault(SITE, GRP1, "LAMP-02", under_current())
    assert fault is not None and fault.state is FaultState.CONFIRMED

    # Retained locally before anything reaches the group: the node's fault
    # engine holds the confirmed fault, and its own event history carries the
    # detection linked to that fault identity. Nothing exists only in transit.
    node = sim.node(SITE, GRP1, "LAMP-02")
    assert fault in node.faults.active_faults
    detected = [e for e in node.events if e.event_type is EventType.FAULT_CONFIRMED]
    assert detected and detected[-1].related_fault_id == fault.fault_id

    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    group_records = [r for r in sim.gc(SITE, GRP1).storage.records
                     if r.record_type is RecordType.FAULT]
    assert group_records, "the group controller retained the report"

    visible = sim.mcc.active_faults(SITE, GRP1)
    assert len(visible) == 1
    summary = visible[0]
    assert str(summary.site_id) == SITE
    assert str(summary.group_id) == GRP1
    assert str(summary.lamp_id) == "LAMP-02"
    assert summary.fault_id == fault.fault_id
    assert summary.fault_type is FaultType.UNDER_CURRENT
    assert summary.state is FaultState.CONFIRMED
    assert summary.severity is FaultSeverity.MINOR
    assert summary.notification_state is NotificationState.ACK_PENDING
    assert summary.first_reported_ticks <= summary.latest_reported_ticks

    # The group aggregate names the faulted lamp without hiding the others.
    group = sim.mcc.group_status(SITE, GRP1)
    assert group.health is AggregateHealth.DEGRADED
    assert group.faulted_lamps == (Identifier("LAMP-02"),)
    assert group.active_faults == 1
    assert sim.mcc.site_status(SITE).active_faults == 1
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").availability is LampAvailability.DEGRADED
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability is LampAvailability.HEALTHY

    # Repair through the existing lifecycle and verification.
    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=sim.clock.ticks + 1)
    node.start_repair(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 2)
    node.report_repaired(fault.fault_id, ENGINEER, ticks=sim.clock.ticks + 3)
    node.step(healthy_sources(), ticks=sim.clock.ticks + 4)
    node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=sim.clock.ticks + 5)
    assert fault.state is FaultState.CLOSED

    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert sim.mcc.active_faults(SITE, GRP1) == ()
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.HEALTHY
    assert sim.mcc.site_status(SITE).active_faults == 0

    # History kept, nothing invented: the fault records remain readable.
    history = sim.mcc.fault_records(SITE, GRP1, "LAMP-02")
    assert [r.payload["fault_id"] for r in history] == [fault.fault_id, fault.fault_id]
    assert history[-1].payload.get("cleared") is True


def test_fault_records_reach_the_mcc_upstream_end_after_recovery():
    """A fault raised while the upstream link is down still arrives later."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)
    sim.upstream(SITE, GRP1).set_available(False)

    fault = sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    sim.mcc.forward_upstream(SITE, GRP1)
    # The live view reads the controller, so the fault is already visible - but
    # its record has not reached the MCC's own history, and the link is the
    # reason why.
    assert sim.mcc.upstream_records(SITE, GRP1) == (), "nothing was delivered"
    assert len(sim.mcc.active_faults(SITE, GRP1)) == 1
    buffered = [r for r in sim.gc(SITE, GRP1).storage.pending_upload
                if r.record_type is RecordType.FAULT]
    assert buffered and buffered[0].payload["fault_id"] == fault.fault_id

    sim.upstream(SITE, GRP1).set_available(True)
    report = sim.mcc.recover_upstream(SITE, GRP1)[(Identifier(SITE), Identifier(GRP1))]
    assert report["recovered"] is True and report["remaining"] == []

    delivered = [r for r in sim.mcc.upstream_records(SITE, GRP1)
                 if r.record_type is RecordType.FAULT]
    assert delivered and all(r.lamp_id == Identifier("LAMP-01") for r in delivered)
    assert any(r.record.payload["fault_id"] == fault.fault_id for r in delivered)
    # The delivered record is the controller's own record object, unchanged:
    # the MCC neither copies nor re-stamps what it received.
    assert any(delivered[0].record is record
               for record in sim.gc(SITE, GRP1).storage.retained)
    assert delivered[0].record is buffered[0]
    # The record keeps the controller's own logical stamp: not earlier than the
    # fault it reports, and never in the future of the clock.
    assert fault.created_ticks <= delivered[0].timestamp_ticks <= sim.clock.ticks
    # The MCC view is now the same as if the link had never failed.
    assert len(sim.mcc.active_faults(SITE, GRP1)) == 1


def test_fault_visibility_never_claims_a_fault_the_group_did_not_receive():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    assert node.faults.active_faults, "the node has confirmed the fault itself"

    assert sim.mcc.active_faults(SITE, GRP1) == ()
    assert sim.mcc.group_status(SITE, GRP1).active_faults == 0


def test_concurrent_confirmed_faults_are_bounded_by_the_single_fault_report_pull():
    """LIMITATION MARKER - the FAULT_REPORT pull carries one fault snapshot.

    ``docs/05`` defines the fault poll as a single "active fault snapshot", and
    ``docs/03`` records that a lamp may hold concurrent faults. This test *pins*
    that boundary with the real classes so the gap cannot be silently assumed
    away: it fails if the node starts holding more than one confirmed fault
    without the reporting path carrying them, and it fails if the MCC starts
    presenting a fault identity it was never told about. It also documents the
    consequence that the operator view can stay stale (the closed fault is no
    longer on the node but is still listed at the MCC) until the reporting
    contract is extended - which is a later phase, because a fault-set pull
    changes the wire payload, not a Phase 16 integration step.
    """
    sim = integrated(lamps_per_group=1, status_max_age_ticks=100_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")

    first = sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    reported = sim.mcc.active_faults(SITE, GRP1)
    assert [f.fault_id for f in reported] == [first.fault_id]

    # A second, different fault type reaches CONFIRMED on the same lamp while
    # the first one is still confirmed.
    for _ in range(node.config.fault_confirmation_count * 2):
        sim.step(SITE, GRP1, "LAMP-01", ticks=sim.clock.ticks + 1000,
                 sources=healthy_sources(voltage=500.0, current=5.0, power=2500.0))
    confirmed = [f for f in node.faults.active_faults if f.is_confirmed]
    assert len(confirmed) == 2, "the fault model really does hold concurrent faults"
    sim.rounds(2, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert [f.fault_id for f in sim.mcc.active_faults(SITE, GRP1)] == [first.fault_id], \
        "one snapshot per pull: the second confirmed fault is not propagated"
    assert {r.payload["fault_id"] for r in sim.mcc.fault_records(SITE, GRP1)} == {
        first.fault_id}, "and the MCC holds no record for a fault it was never told about"

    # Closing the first fault does not clear it at the MCC while the second one
    # is the one being reported.
    node.acknowledge_fault(first.fault_id, OPERATOR, ticks=sim.clock.ticks + 1)
    node.start_repair(first.fault_id, ENGINEER, ticks=sim.clock.ticks + 2)
    node.report_repaired(first.fault_id, ENGINEER, ticks=sim.clock.ticks + 3)
    node.step(healthy_sources(voltage=500.0, current=5.0, power=2500.0),
              ticks=sim.clock.ticks + 4)
    node.verify_repair(first.fault_id, ENGINEER, verified=True, ticks=sim.clock.ticks + 5)
    assert first.state is FaultState.CLOSED
    assert [f.fault_id for f in node.faults.active_faults] == [confirmed[1].fault_id]
    sim.rounds(2, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    active = sim.mcc.active_faults(SITE, GRP1)
    assert {f.fault_id for f in active} == {first.fault_id, confirmed[1].fault_id}
    assert all(f.fault_id in {f.fault_id for f in confirmed} for f in active), \
        "the escalation is stale information, not an invented identity"


def test_a_fault_clear_is_scoped_to_its_own_fault_and_keeps_history():
    """One lamp's repair must not clear another lamp's fault record."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)

    first = sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current())
    second = sim.confirm_fault(SITE, GRP1, "LAMP-02", under_current())
    # Fault ids are per-node counters: the identity that keeps them apart is the
    # lamp (inside its site and group), never the id string alone.
    assert (first.site_id, first.group_id, first.lamp_id) != (
        second.site_id, second.group_id, second.lamp_id)
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert {f.lamp_id for f in sim.mcc.active_faults(SITE, GRP1)} == {
        Identifier("LAMP-01"), Identifier("LAMP-02")}

    # Repair LAMP-01 only, through the existing lifecycle.
    node = sim.node(SITE, GRP1, "LAMP-01")
    node.acknowledge_fault(first.fault_id, OPERATOR, ticks=sim.clock.ticks + 1)
    node.start_repair(first.fault_id, ENGINEER, ticks=sim.clock.ticks + 2)
    node.report_repaired(first.fault_id, ENGINEER, ticks=sim.clock.ticks + 3)
    node.step(healthy_sources(), ticks=sim.clock.ticks + 4)
    node.verify_repair(first.fault_id, ENGINEER, verified=True, ticks=sim.clock.ticks + 5)
    assert first.state is FaultState.CLOSED
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)

    # Only LAMP-01's fault left the active view; the other lamp's fault and the
    # cleared one's history both survive.
    active = sim.mcc.active_faults(SITE, GRP1)
    assert [str(f.lamp_id) for f in active] == ["LAMP-02"]
    assert active[0].fault_id == second.fault_id
    assert sim.mcc.group_status(SITE, GRP1).faulted_lamps == (Identifier("LAMP-02"),)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability is LampAvailability.HEALTHY
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").availability is LampAvailability.DEGRADED
    history = sim.mcc.fault_records(SITE, GRP1, "LAMP-01")
    assert [r.payload["fault_id"] for r in history] == [first.fault_id, first.fault_id]
    assert history[0].payload.get("cleared") is None
    assert history[-1].payload["cleared"] is True
    assert history[-1].payload["lamp_id"] == "LAMP-01", "the clear names its lamp"


# ===========================================================================
# OFFLINE / STORE-AND-FORWARD INTEGRATION
# ===========================================================================
def test_offline_cycle_buffers_everything_and_replays_it_once():
    """A-H: loss -> local operation -> buffering -> recovery -> MCC -> no loss."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    sim.cycle(ticks=1000, forward=True)
    baseline_received = len(sim.mcc.upstream_records(SITE, GRP1))
    assert baseline_received > 0

    # A: the upstream link is lost before the new events happen.
    outage_tick = sim.clock.ticks
    sim.upstream(SITE, GRP1).set_available(False)

    # B: lamps keep working locally while offline (control is not dependent on
    # the MCC, and not on the upstream link either).
    sim.step(SITE, GRP1, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1000)
    assert sim.lamp_is_on(SITE, GRP1, "LAMP-01") is False
    sim.node(SITE, GRP1, "LAMP-02").force_on(OPERATOR, ticks=sim.clock.ticks + 1)

    # C: several cycles accumulate records, and failed uploads change nothing.
    sim.cycle(ticks=sim.clock.ticks + 2000)
    sim.cycle(ticks=sim.clock.ticks + 2000)
    forwarded = sim.mcc.forward_upstream(SITE, GRP1)[(Identifier(SITE), Identifier(GRP1))]
    assert forwarded["confirmed"] == 0 and forwarded["failed"] > 0
    pending = [r.sequence_number for r in sim.gc(SITE, GRP1).storage.pending_upload]
    assert len(pending) >= 6
    assert len(sim.mcc.upstream_records(SITE, GRP1)) == baseline_received, \
        "the MCC history did not grow while the link was down"
    assert sim.mcc.duplicate_uploads == 0

    # D/E: the link returns and the documented sequence runs.
    sim.upstream(SITE, GRP1).set_available(True)
    report = sim.mcc.recover_upstream(SITE, GRP1)[(Identifier(SITE), Identifier(GRP1))]
    assert report["recovered"] is True
    assert report["buffered"] == pending, "exactly the buffered records were replayed"
    assert report["remaining"] == []
    assert sim.gc(SITE, GRP1).storage.pending_upload == ()

    # F: the MCC received the previously retained information, in order.
    received = sim.mcc.upstream_records(SITE, GRP1)
    assert len(received) >= len(pending)
    sequences = [r.sequence_number for r in received]
    assert sequences == sorted(sequences), "arrival order follows sequence order"
    measurements = [r for r in received if r.record_type is RecordType.MEASUREMENT]
    assert {str(r.lamp_id) for r in measurements} == {"LAMP-01", "LAMP-02"}
    lamp_one = [r for r in measurements if r.lamp_id == Identifier("LAMP-01")]
    assert lamp_one, "the offline change was recorded and replayed"
    offline_samples = [r for r in lamp_one if r.record.timestamp.ticks >= outage_tick]
    assert offline_samples, "the samples taken while the link was down arrived"
    assert any(r.record.payload["actual_state"] == LampState.OFF.value
               for r in offline_samples), \
        "the state the lamp really reached offline is what the MCC received"

    # G: duplicate delivery must not corrupt or duplicate MCC state.
    controller = sim.gc(SITE, GRP1)
    already = sim.mcc.upstream_records(SITE, GRP1)[0].record
    assert sim.mcc.receive_upstream(SITE, GRP1, already) is True
    assert sim.mcc.duplicate_uploads == 1
    assert sim.mcc.upstream_records(SITE, GRP1) == received

    # H: nothing was lost - every record that was buffered is still readable in
    # the retained history, and the confirmation moved it out of the pending
    # queue without deleting it.
    stored = {r.sequence_number: r for r in controller.storage.records}
    assert set(pending) <= set(stored)
    for sequence_number in pending:
        record = stored[sequence_number]
        assert record.lifecycle_state is RecordLifecycleState.RETAINED, \
            "an uploaded record is retained, not discarded"
        assert record.upload_attempts >= 1, "it was really offered upstream"
    assert {r.sequence_number for r in controller.storage.retained} >= set(pending)
    assert controller.storage.pending_upload == (), "nothing is stuck unconfirmed"


def test_offline_upload_of_an_unidentifiable_record_stays_pending():
    """The MCC refuses what it cannot attribute; the sender keeps it visible."""
    sim = integrated(lamps_per_group=1, status_max_age_ticks=50_000)
    controller = sim.gc(SITE, GRP1)
    sim.cycle(ticks=1000)
    record = controller.storage.pending_upload[0]

    foreign = replace(record, device_id=Identifier("GROUP-OTHER"))
    assert sim.mcc.receive_upstream(SITE, GRP1, foreign) is False
    assert sim.mcc.upstream_records() == ()
    assert record in controller.storage.pending_upload, "nothing vanished"

    # The real record is still accepted afterwards.
    assert sim.mcc.receive_upstream(SITE, GRP1, record) is True
    assert len(sim.mcc.upstream_records(SITE, GRP1)) == 1


def test_lost_confirmation_replays_without_duplicating_mcc_history():
    """A confirmation lost in flight must not lose or duplicate the record."""
    sim = integrated(lamps_per_group=1, status_max_age_ticks=50_000)
    controller = sim.gc(SITE, GRP1)
    sim.cycle(ticks=1000)

    # Wrap the MCC link so the next upload reaches the MCC but reports failure.
    real_link = sim.upstream(SITE, GRP1)
    delivered = []
    original_upload = real_link.upload

    def unreliable(record):
        delivered.append(record.sequence_number)
        original_upload(record)
        return False

    real_link.upload = unreliable
    try:
        first = sim.mcc.forward_upstream(SITE, GRP1)[(Identifier(SITE), Identifier(GRP1))]
    finally:
        real_link.upload = original_upload
    assert first["confirmed"] == 0 and first["failed"] >= 1
    assert delivered, "the MCC really did receive the record"
    pending_after_loss = {r.sequence_number for r in controller.storage.pending_upload}
    assert pending_after_loss, "an unconfirmed record stays pending"

    second = sim.mcc.forward_upstream(SITE, GRP1)[(Identifier(SITE), Identifier(GRP1))]
    assert second["confirmed"] >= 1
    assert controller.storage.pending_upload == ()
    received = sim.mcc.upstream_records(SITE, GRP1)
    sequences = [r.sequence_number for r in received]
    assert len(sequences) == len(set(sequences)), "no duplicated history"
    assert set(delivered) <= set(sequences)


# ===========================================================================
# RESTART / RECONSTRUCTION INTEGRATION
# ===========================================================================
def test_controller_restart_drops_transient_state_and_keeps_persistence():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    sim.cycle(ticks=1000, forward=True)
    retained_before = len(sim.gc(SITE, GRP1).storage.retained)
    assert retained_before > 0

    # A command is executed and acknowledged, but its actual state is not yet
    # verified when the controller restarts.
    command = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-gc-restart")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert command.state is CommandState.ACKNOWLEDGED
    assert all(r.awaiting_response for r in sim.gc(SITE, GRP1).registrations if
               r.lamp_id == Identifier("LAMP-01"))

    restart_report = sim.restart_group(SITE, GRP1)
    assert restart_report == {"nodes": 2, "cleared_requests": 1, "failed_commands": 1}
    # The transaction died with the controller: it is failed, never left
    # waiting for evidence that no longer exists.
    assert command.state is CommandState.FAILED
    assert command.verified_ticks is None
    assert all(not r.awaiting_response for r in sim.gc(SITE, GRP1).registrations)
    # Identity and records survive; volatile views do not.
    assert sim.gc(SITE, GRP1).identity.site_id == Identifier(SITE)
    assert len(sim.gc(SITE, GRP1).storage.retained) == retained_before
    assert sim.gc(SITE, GRP1).registration_for(Identifier("LAMP-01")).last_measurement is None
    restarts = [e for e in sim.gc(SITE, GRP1).events
                if e.event_type is EventType.NODE_RESTARTED]
    assert restarts and restarts[-1].event_data == {
        "nodes": 2, "cleared_requests": 1, "failed_commands": 1}, \
        "the restart itself is audited with what it cleared"

    # The MCC must not present pre-restart data as current truth.
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.availability is LampAvailability.UNKNOWN
    assert status.freshness is Freshness.UNKNOWN
    assert status.voltage is None
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.UNKNOWN

    # A restarted controller can still poll and rebuild the whole view: no node
    # is stuck awaiting a response that no longer exists.
    sim.advance(1000)
    report(sim)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.availability is LampAvailability.HEALTHY
    assert status.voltage == pytest.approx(230.0)
    assert status.measured_ticks is not None


def test_node_restart_keeps_identity_and_configuration_and_fails_the_command():
    sim = integrated(lamps_per_group=1, status_max_age_ticks=50_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    identity_before, config_before = node.identity, node.config
    assert node.config_version == 0, "documented version-zero startup convention"

    # The command is delivered and executed, but its actual state is never
    # verified: the watchdog restart happens first.
    record = sim.mcc.force_on(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-restart")
    assert record.state is CommandState.RECEIVED
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert record.state is CommandState.ACKNOWLEDGED, \
        "execution acknowledged is not actual-state verification"

    node.restart(ticks=sim.clock.ticks + 1)
    # The node that restarted has no override, no old transaction and no
    # verification evidence; the failed ACK is what the controller can receive.
    assert node.control.active_override is OverrideState.NONE
    assert node.commands.get("int-restart").state is CommandState.FAILED
    assert record.state is CommandState.ACKNOWLEDGED, "still awaiting evidence"
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()

    assert record.state is CommandState.FAILED, "never reported as applied"
    assert record.verified_ticks is None
    assert node.identity == identity_before
    assert node.config == config_before
    assert node.config_version == 0
    assert node.control.lamp_is_on is False, "documented restart default"
    assert any(e.event_type is EventType.NODE_RESTARTED for e in node.events)


def test_mcc_reconstruction_from_the_same_controllers_reproduces_the_view():
    """A rebuilt MCC over unchanged controllers shows the same system state."""
    from sslv1.mcc import MasterControlCenter, MasterControlCenterConfig

    sim = integrated(lamps_per_group=3, status_max_age_ticks=100_000)
    sim.cycle(ticks=1000, forward=True)
    sim.confirm_fault(SITE, GRP1, "LAMP-03", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)

    before_group = sim.mcc.group_status(SITE, GRP1)
    before_faults = sim.mcc.active_faults(SITE, GRP1)

    # Restart = rebuild the data layer over the same (persisted) controllers.
    rebuilt = MasterControlCenter(
        config=MasterControlCenterConfig(status_max_age_ticks=100_000),
        clock=sim.clock,
    )
    for site_registration in sim.mcc.sites:
        rebuilt.create_site(site_registration.site_id)
    for site_registration in sim.mcc.sites:
        for group_registration in sim.mcc.groups(site_registration.site_id):
            rebuilt.register_group(site_registration.site_id, group_registration.group_id,
                                   group_registration.controller)
            for lamp in sim.mcc.lamps(site_registration.site_id, group_registration.group_id):
                rebuilt.register_lamp(site_registration.site_id, group_registration.group_id,
                                      sim.node(site_registration.site_id,
                                               group_registration.group_id, lamp.lamp_id))

    after_group = rebuilt.group_status(SITE, GRP1)
    assert after_group.health is before_group.health
    assert after_group.health is AggregateHealth.DEGRADED
    assert after_group.active_faults == before_group.active_faults == 1
    assert after_group.faulted_lamps == before_group.faulted_lamps
    assert after_group.aggregate_power == before_group.aggregate_power
    assert rebuilt.active_faults(SITE, GRP1)[0].fault_id == before_faults[0].fault_id
    assert rebuilt.site_status(SITE).total_lamps == sim.mcc.site_status(SITE).total_lamps
    # The reconstruction invents nothing: it holds only what it re-read.
    assert rebuilt.upstream_records() == ()


def test_record_recovery_discards_damage_without_faking_mcc_history():
    """A corrupt record is excluded by the existing store, never by the MCC."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    controller = sim.gc(SITE, GRP1)
    sim.cycle(ticks=1000)
    committed = len(controller.storage.records)
    victim = controller.storage.records[0]
    controller.storage.corrupt(victim.sequence_number)

    discarded = controller.storage.recover()
    assert victim.sequence_number in {r.sequence_number for r in discarded}
    assert len(controller.storage.records) == committed - 1

    # Nothing corrupt can be confirmed upstream, and it never appears in the
    # history the MCC received.
    report = sim.mcc.recover_upstream(SITE, GRP1)[(Identifier(SITE), Identifier(GRP1))]
    assert report["remaining"] == []
    assert victim.sequence_number not in {r.sequence_number for r in sim.mcc.upstream_records()}
    assert sim.mcc.group_status(SITE, GRP1).retained_records == len(controller.storage.retained)


# ===========================================================================
# MULTI-GROUP / MULTI-SITE INTEGRATION
# ===========================================================================
def test_commands_and_faults_reach_only_the_intended_group_and_lamp():
    sim = integrated(site_count=2, group_count=2, lamps_per_group=4,
                     status_max_age_ticks=100_000)
    observe(sim)

    # The same lamp id exists in four groups; only one is addressed.
    record = sim.mcc.force_off(SITE, GRP2, "LAMP-01", OPERATOR, command_id="int-route")
    sim.pump(SITE, GRP2)
    sim.gc(SITE, GRP2).collect_responses()
    sim.step(SITE, GRP2, "LAMP-01", sources=off_sources(), ticks=sim.clock.ticks + 1)
    sim.pump(SITE, GRP2)
    sim.gc(SITE, GRP2).collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED

    assert sim.node(SITE, GRP2, "LAMP-01").control.active_override is OverrideState.FORCE_OFF
    for other in ((SITE, GRP1), (SITE_B, GRP1), (SITE_B, GRP2)):
        node = sim.node(other[0], other[1], "LAMP-01")
        assert node.control.active_override is OverrideState.NONE, other
    # The other groups saw no traffic for that command.
    for other in ((SITE, GRP1), (SITE_B, GRP1), (SITE_B, GRP2)):
        assert sim.mcc.command(other[0], other[1], "int-route") is None

    # A fault stays with its own site/group/lamp.
    sim.confirm_fault(SITE_B, GRP2, "LAMP-02", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE_B, group=GRP2)
    faults = sim.mcc.active_faults()
    assert len(faults) == 1
    assert (str(faults[0].site_id), str(faults[0].group_id), str(faults[0].lamp_id)) == (
        SITE_B, GRP2, "LAMP-02")
    assert sim.mcc.active_faults(SITE, GRP2) == ()
    assert sim.mcc.active_faults(SITE_B, GRP1) == ()
    assert sim.mcc.site_status(SITE).active_faults == 0
    assert sim.mcc.site_status(SITE_B).active_faults == 1


def test_one_groups_link_failure_cannot_contaminate_another_group():
    sim = integrated(site_count=2, group_count=2, lamps_per_group=3,
                     status_max_age_ticks=100_000)
    observe(sim)
    before_group_2 = sim.mcc.group_status(SITE, GRP2)
    before_site = sim.mcc.site_status(SITE)
    before_other_site = sim.mcc.site_status(SITE_B)

    sim.silence_group(SITE, GRP1)
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP1)
        sim.gc(SITE, GRP1).service_timeouts()
        sim.gc(SITE, GRP1).collect_responses()

    group_1 = sim.mcc.group_status(SITE, GRP1)
    assert group_1.health is AggregateHealth.UNAVAILABLE
    assert set(str(lamp) for lamp in group_1.unavailable_lamps) == {"LAMP-01", "LAMP-02", "LAMP-03"}

    after_group_2 = sim.mcc.group_status(SITE, GRP2)
    assert after_group_2.health is before_group_2.health is AggregateHealth.HEALTHY
    assert after_group_2.healthy_lamps == before_group_2.healthy_lamps == 3
    assert after_group_2.latest_observation_ticks == before_group_2.latest_observation_ticks

    site = sim.mcc.site_status(SITE)
    assert site.health is AggregateHealth.DEGRADED
    assert site.unhealthy_groups == (Identifier(GRP1),)
    assert site.healthy_lamps == before_site.healthy_lamps - 3

    # The other site is a separate system: same outage, no visible change.
    after_other_site = sim.mcc.site_status(SITE_B)
    assert after_other_site.health is before_other_site.health is AggregateHealth.HEALTHY
    assert after_other_site.healthy_lamps == before_other_site.healthy_lamps
    assert after_other_site.active_faults == before_other_site.active_faults == 0

    # A site the MCC does not know cannot be queried into existence.
    with pytest.raises(ConfigurationError):
        sim.mcc.site_status("SITE-Z")


def test_same_identifier_in_two_sites_is_two_different_systems():
    sim = integrated(site_count=2, group_count=1, lamps_per_group=2,
                     status_max_age_ticks=100_000)
    observe(sim)
    sim.mcc.force_off(SITE, GRP1, "LAMP-01", OPERATOR, command_id="int-site-a")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert sim.node(SITE, GRP1, "LAMP-01").control.active_override is OverrideState.FORCE_OFF
    assert sim.node(SITE_B, GRP1, "LAMP-01").control.active_override is OverrideState.NONE

    sim.confirm_fault(SITE, GRP1, "LAMP-02", under_current())
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)
    assert sim.mcc.active_faults(SITE, GRP1) and sim.mcc.active_faults(SITE_B, GRP1) == ()

    # The MCC keeps both sites' aggregates separate and correct.
    assert sim.mcc.site_status(SITE).active_faults == 1
    assert sim.mcc.site_status(SITE_B).active_faults == 0
    assert sim.mcc.group_status(SITE_B, GRP1).health is AggregateHealth.HEALTHY


# ===========================================================================
# COMMUNICATION INTEGRATION
# ===========================================================================
def test_a_silent_node_is_unavailable_at_the_mcc_while_its_neighbours_report():
    sim = integrated(lamps_per_group=3, status_max_age_ticks=100_000)
    observe(sim)
    sim.silence_lamp(SITE, GRP1, "LAMP-02")
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP1)
        sim.gc(SITE, GRP1).service_timeouts()
        sim.gc(SITE, GRP1).collect_responses()

    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-02")
    assert status.comm_state is CommState.COMM_FAULT
    assert status.availability is LampAvailability.UNAVAILABLE
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability is LampAvailability.HEALTHY
    assert sim.mcc.group_status(SITE, GRP1).comm_summary["COMM_FAULT"] == 1
    # Communication failure is not a fault claim about the lamp itself.
    assert sim.mcc.active_faults(SITE, GRP1) == ()

    # Recovery is visible: state machine, MCC availability and the event trail.
    sim.silence_lamp(SITE, GRP1, "LAMP-02", False)
    sim.advance(1000)
    sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").availability is LampAvailability.RECOVERING
    sim.advance(1000)
    sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").availability is LampAvailability.HEALTHY
    recovered = [e for e in sim.mcc.events(SITE, GRP1)
                 if e.event_type is EventType.COMM_RECOVERED]
    assert recovered, "the end of the degradation is audited"
    assert recovered[-1].event_data["current"] == CommState.COMM_HEALTHY.value
    assert recovered[-1].event_data["previous"] == CommState.RECOVERY.value
    states = [t.to_state for t in sim.gc(SITE, GRP1).registration_for(
        Identifier("LAMP-02")).comm.history]
    assert CommState.COMM_FAULT in states, "the link really did reach COMM_FAULT"


def test_wrong_destination_wrong_version_and_duplicate_frames_are_contained():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)
    controller = sim.gc(SITE, GRP1)
    registration = controller.registration_for(Identifier("LAMP-01"))

    sim.advance(1000)
    controller.poll(MessageType.STATUS_REQUEST)
    valid = sim.node(SITE, GRP1, "LAMP-01").process_incoming()[0]
    newest_before = registration.sequences.newest

    for bad in (replace(valid, destination=3), replace(valid, protocol_version=99)):
        controller.receive(bad)
        controller.collect_responses()
    assert registration.sequences.newest == newest_before, "invalid frames changed nothing"
    assert any(e.event_type is EventType.FRAME_REJECTED for e in controller.events)

    sim.bus(SITE, GRP1).send(valid)
    controller.collect_responses()
    assert registration.sequences.newest == valid.sequence
    status_after_valid = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")

    # The same frame again is classified as a duplicate: reported, not applied.
    sim.bus(SITE, GRP1).send(valid)
    controller.collect_responses()
    assert registration.duplicate_frames == 1
    assert any(e.event_type is EventType.DUPLICATE_FRAME_DETECTED for e in controller.events)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").last_seen_ticks == \
        status_after_valid.last_seen_ticks, "a duplicate is not a new observation"


def test_a_command_to_a_missing_or_foreign_target_is_refused_locally():
    sim = integrated(group_count=1, lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    transmitted = sim.bus(SITE, GRP1).stats.transmitted

    with pytest.raises(ConfigurationError):
        sim.mcc.force_on(SITE, GRP1, "LAMP-99", OPERATOR, command_id="int-missing")
    with pytest.raises(ConfigurationError):
        sim.mcc.force_on(SITE, GRP2, "LAMP-01", OPERATOR, command_id="int-wrong-group")
    with pytest.raises(ConfigurationError):
        sim.mcc.force_on(SITE_B, GRP1, "LAMP-01", OPERATOR, command_id="int-wrong-site")
    assert sim.bus(SITE, GRP1).stats.transmitted == transmitted, "no traffic for unknown targets"


def test_mcc_polling_uses_the_existing_poll_and_timeout_paths():
    sim = integrated(group_count=2, lamps_per_group=2, status_max_age_ticks=100_000)
    results = sim.mcc.poll(MessageType.STATUS_REQUEST)
    assert set(results) == {(Identifier(SITE), Identifier(GRP1)),
                            (Identifier(SITE), Identifier(GRP2))}
    assert all(len(per_group) == 2 for per_group in results.values())

    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    sim.cycle(ticks=sim.clock.ticks + 1000)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").availability is LampAvailability.HEALTHY
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.HEALTHY


# ===========================================================================
# CONFIGURATION INTEGRATION
# ===========================================================================
def test_configuration_change_is_authorized_applied_and_verified_end_to_end():
    """Existing write path -> node applies -> readback -> MCC verification."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    assert node.config.configured_mode is ConfiguredMode.AUTO_SENSOR

    record = sim.gc(SITE, GRP1).distribute_configuration(
        Identifier("LAMP-01"),
        {"configured_mode": list(ConfiguredMode).index(ConfiguredMode.FIXED_SCHEDULE)},
        ENGINEER,
        config_version=2,
    )
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()

    # Applied at the node, versioned, and only then verified.
    assert node.config.configured_mode is ConfiguredMode.FIXED_SCHEDULE
    assert node.config_version == 2
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED, record.result
    readback = sim.mcc.configuration_snapshot(SITE, GRP1, "LAMP-01")
    assert readback["accepted"] is True
    assert readback["parameters"]["configured_mode"] == list(ConfiguredMode).index(
        ConfiguredMode.FIXED_SCHEDULE)
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").configured_mode is \
        ConfiguredMode.FIXED_SCHEDULE
    # The other lamp was not configured.
    assert sim.mcc.configuration_snapshot(SITE, GRP1, "LAMP-02") is None
    assert sim.node(SITE, GRP1, "LAMP-02").config_version == 0


def test_configuration_write_requires_privilege_and_a_newer_version():
    sim = integrated(lamps_per_group=1, status_max_age_ticks=100_000)
    observe(sim)
    controller = sim.gc(SITE, GRP1)
    unit = Identifier("LAMP-01")
    node = sim.node(SITE, GRP1, "LAMP-01")
    before = node.config

    denied = controller.distribute_configuration(
        unit, {"light_on_threshold": 20}, OPERATOR, config_version=2)
    assert denied.state is CommandState.REJECTED
    assert node.config == before and node.config_version == 0
    assert not any(e.event_type is EventType.CONFIG_CHANGED for e in node.events)

    # A version that is not newer than the one already in effect is refused by
    # the node, and the previous valid configuration stays in effect.
    stale = controller.distribute_configuration(
        unit, {"light_on_threshold": 20}, ENGINEER, config_version=0)
    sim.pump(SITE, GRP1)
    controller.collect_responses()
    assert stale.state is CommandState.FAILED
    assert node.config == before and node.config_version == 0
    assert any(e.event_type is EventType.CONFIG_REJECTED for e in node.events)


def test_configuration_accepted_is_not_configuration_applied():
    """A write whose values the node refuses must not verify as applied."""
    sim = integrated(lamps_per_group=1, status_max_age_ticks=100_000)
    observe(sim)
    controller = sim.gc(SITE, GRP1)
    node = sim.node(SITE, GRP1, "LAMP-01")
    before = node.config

    # The requested value is inside the wire subset but invalid as a mode.
    record = controller.distribute_configuration(
        Identifier("LAMP-01"), {"configured_mode": 99}, ENGINEER, config_version=2)
    sim.pump(SITE, GRP1)
    controller.collect_responses()

    assert record.state is CommandState.FAILED
    assert node.config == before, "the previous valid configuration stayed in effect"
    assert node.config_version == 0
    assert sim.mcc.configuration_snapshot(SITE, GRP1, "LAMP-01")["accepted"] is False


# ===========================================================================
# TIME / FRESHNESS INTEGRATION
# ===========================================================================
def test_time_synchronization_propagates_and_is_visible_per_lamp():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)

    # Nothing has synchronized anything yet. No layer may claim synchronized
    # time: the node stamps its own samples UNCERTAIN, the controller stamps
    # its own records UNCERTAIN, and the MCC repeats what it was told.
    node = sim.node(SITE, GRP1, "LAMP-01")
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").time_sync_state is TimeSyncState.UNCERTAIN
    assert {e.timestamp.sync_state for e in sim.gc(SITE, GRP1).events} == {TimeSyncState.UNCERTAIN}
    assert all(n.time.last_sync_ticks is None for n in sim.nodes(SITE, GRP1))

    # The staleness window a node tolerates is configuration; while it is the
    # zero default any elapsed tick invalidates the earlier synchronization.
    for n in sim.nodes(SITE, GRP1):
        n.time.uncertainty_threshold_ticks = 5_000

    # A viewer cannot distribute time, and a refused attempt changes nothing.
    with pytest.raises(AuthorizationError):
        sim.gc(SITE, GRP1).synchronize_time(master_ticks=sim.clock.ticks + 500, actor=VIEWER)
    assert all(n.time.last_sync_ticks is None for n in sim.nodes(SITE, GRP1))

    # The authorized distribution is verified by the node's acknowledgement.
    sim.gc(SITE, GRP1).synchronize_time(master_ticks=sim.clock.ticks + 500, actor=ADMIN)
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    synchronized = [e for e in node.events if e.event_type is EventType.TIME_SYNCHRONIZED]
    assert synchronized, "the node acknowledged the distribution"
    assert synchronized[-1].timestamp.sync_state is TimeSyncState.SYNCHRONIZED

    # The samples taken from here on carry that state, the MCC shows it per
    # lamp, and the earlier uncertain records were not rewritten.
    sim.step_group(SITE, GRP1, ticks=sim.clock.ticks + 1000)
    report(sim)
    status = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert status.time_sync_state is TimeSyncState.SYNCHRONIZED
    assert status.measured_ticks is not None and status.measured_ticks <= sim.clock.ticks
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-02").time_sync_state is TimeSyncState.SYNCHRONIZED
    assert TimeSyncState.SYNCHRONIZED in {e.timestamp.sync_state
                                          for e in sim.gc(SITE, GRP1).events}
    assert TimeSyncState.UNCERTAIN in {e.timestamp.sync_state
                                       for e in sim.gc(SITE, GRP1).events}, \
        "the earlier records keep their own validity"

    # The window is a bound, not a permanent claim: a node that is not
    # resynchronized falls out of it and the MCC stops presenting its time as
    # synchronized.
    sim.step_group(SITE, GRP1, ticks=node.time.ticks + 7_000)
    report(sim)
    assert node.time.sync_state is TimeSyncState.UNCERTAIN
    assert sim.mcc.lamp_status(SITE, GRP1, "LAMP-01").time_sync_state is TimeSyncState.UNCERTAIN


def test_stale_measurements_are_never_presented_as_current():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=2_000)
    observe(sim)
    fresh = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert fresh.freshness is Freshness.FRESH
    assert fresh.availability is LampAvailability.HEALTHY

    sim.advance(10_000)
    stale = sim.mcc.lamp_status(SITE, GRP1, "LAMP-01")
    assert stale.freshness is Freshness.STALE
    assert stale.availability is LampAvailability.UNKNOWN
    assert stale.voltage == fresh.voltage, "the value is unchanged, its currency is not"
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.UNKNOWN
    assert sim.mcc.site_status(SITE).health is AggregateHealth.UNKNOWN


def test_a_group_that_never_reported_is_unknown_not_healthy():
    """One observed group must not make an unobserved group look healthy."""
    sim = integrated(group_count=2, lamps_per_group=2, status_max_age_ticks=100_000)
    sim.step_group(SITE, GRP1, ticks=1000)
    sim.rounds(1, MessageType.STATUS_REQUEST, site=SITE, group=GRP1)
    sim.rounds(1, MessageType.MEASUREMENT_REQUEST, site=SITE, group=GRP1)

    observed = sim.mcc.group_status(SITE, GRP1)
    assert observed.health is AggregateHealth.HEALTHY
    unobserved = sim.mcc.group_status(SITE, GRP2)
    assert unobserved.health is AggregateHealth.UNKNOWN
    assert unobserved.healthy_lamps == 0
    assert len(unobserved.unknown_lamps) == 2

    unknown_lamp = sim.mcc.lamp_status(SITE, GRP2, "LAMP-01")
    assert unknown_lamp.availability is LampAvailability.UNKNOWN
    assert unknown_lamp.voltage is None and unknown_lamp.power is None
    assert unknown_lamp.energy is None and unknown_lamp.last_seen_ticks is None
    assert sim.mcc.site_status(SITE).health is AggregateHealth.DEGRADED


def test_event_and_fault_timestamps_come_from_the_logical_clock_only():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)
    moment = sim.clock.ticks + TICKS_PER_SECOND
    sim.confirm_fault(SITE, GRP1, "LAMP-01", under_current(), ticks=moment)
    sim.rounds(1, MessageType.FAULT_REPORT, site=SITE, group=GRP1)

    summary = sim.mcc.active_faults(SITE, GRP1)[0]
    assert moment <= summary.latest_reported_ticks <= sim.clock.ticks
    assert summary.first_reported_ticks <= summary.latest_reported_ticks
    node_fault = sim.node(SITE, GRP1, "LAMP-01").faults.active_faults[0]
    assert node_fault.first_observation_ticks <= summary.latest_reported_ticks, \
        "the node observed the condition before the MCC could be told about it"
    assert node_fault.created_ticks >= moment
    assert summary.time_sync_state is TimeSyncState.UNCERTAIN, \
        "no synchronization was claimed, and none was performed"
    events = sim.mcc.events(SITE, GRP1)
    assert [e.timestamp.ticks for e in events] == sorted(e.timestamp.ticks for e in events)


# ===========================================================================
# SCALE / SOFTWARE RESOURCE BOUNDS
# ===========================================================================
def test_two_sites_of_two_sixteen_lamp_groups_operate_deterministically():
    """Digital/software scale check - not a hardware resource validation."""
    sim = integrated(site_count=2, group_count=2, lamps_per_group=16,
                     status_max_age_ticks=100_000)
    assert len(sim.mcc.lamps()) == 64
    assert [sim.gc(s, g).node_count for s in (SITE, SITE_B) for g in (GRP1, GRP2)] == [16] * 4

    started = time.perf_counter()
    sim.cycle(ticks=1000, forward=True)
    elapsed = time.perf_counter() - started

    for site in (SITE, SITE_B):
        site_status = sim.mcc.site_status(site)
        assert site_status.health is AggregateHealth.HEALTHY
        assert site_status.total_groups == 2
        assert site_status.total_lamps == 32
        assert site_status.healthy_lamps == 32
        assert site_status.active_faults == 0
        for group in (GRP1, GRP2):
            group_status = sim.mcc.group_status(site, group)
            assert group_status.total_lamps == 16
            assert group_status.aggregate_power == pytest.approx(16 * 103.5)
            assert len(sim.mcc.lamp_statuses(site, group)) == 16

    # Isolation at scale: one group's nodes go silent, the rest is untouched.
    sim.silence_group(SITE, GRP1)
    for _ in range(sim.gc(SITE, GRP1).config.poll_retry_count + 2):
        sim.advance(1000)
        sim.gc(SITE, GRP1).poll(MessageType.MEASUREMENT_REQUEST)
        sim.pump(SITE, GRP1)
        sim.gc(SITE, GRP1).service_timeouts()
        sim.gc(SITE, GRP1).collect_responses()
    assert sim.mcc.group_status(SITE, GRP1).health is AggregateHealth.UNAVAILABLE
    assert sim.mcc.group_status(SITE, GRP2).health is AggregateHealth.HEALTHY
    assert sim.mcc.site_status(SITE_B).healthy_lamps == 32
    assert sim.mcc.site_status(SITE_B).health is AggregateHealth.HEALTHY

    # Command routing at scale: one of the 64 lamps is addressed, and exactly
    # that lamp changes - the other 63 keep their override state.
    target = "LAMP-16"
    record = sim.mcc.force_off(SITE_B, GRP2, target, OPERATOR, command_id="int-scale-route")
    sim.pump(SITE_B, GRP2)
    sim.gc(SITE_B, GRP2).collect_responses()
    sim.step(SITE_B, GRP2, target, sources=off_sources(), ticks=sim.clock.ticks + 1)
    sim.pump(SITE_B, GRP2)
    sim.gc(SITE_B, GRP2).collect_responses()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED, record.result
    assert sim.node(SITE_B, GRP2, target).control.active_override is OverrideState.FORCE_OFF
    for other_site in (SITE, SITE_B):
        for other_group in (GRP1, GRP2):
            for lamp in sim.lamp_ids(other_site, other_group):
                if (other_site, other_group, str(lamp)) == (SITE_B, GRP2, target):
                    continue
                assert sim.node(other_site, other_group, lamp).control.active_override \
                    is OverrideState.NONE, (other_site, other_group, lamp)

    # Determinism: the same cycle on an identical system yields identical state.
    twin = integrated(site_count=2, group_count=2, lamps_per_group=16,
                      status_max_age_ticks=100_000)
    twin.cycle(ticks=1000, forward=True)
    assert twin.mcc.site_status(SITE).aggregate_power == sim.mcc.site_status(SITE).aggregate_power
    assert (twin.mcc.upstream_records()[0].sequence_number
            == sim.mcc.upstream_records()[0].sequence_number)
    # A generous software guard only; no CPU/memory compliance is claimed.
    assert elapsed < 10.0, "one full integrated cycle stays interactive (%r s)" % elapsed


def test_scale_aggregation_keeps_every_lamp_addressable():
    sim = integrated(group_count=2, lamps_per_group=16, status_max_age_ticks=100_000)
    observe(sim)
    for group in (GRP1, GRP2):
        for lamp in sim.lamp_ids(SITE, group):
            status = sim.mcc.lamp_status(SITE, group, lamp)
            assert status.availability is LampAvailability.HEALTHY
            assert status.lamp_id == lamp and status.group_id == Identifier(group)
            assert status.voltage == pytest.approx(230.0)
    # Group-scoped identity: the same id in the two groups is two lamps.
    assert sim.mcc.lamp(SITE, GRP1, "LAMP-01") is not sim.mcc.lamp(SITE, GRP2, "LAMP-01")
    assert sim.mcc.lamp(SITE, GRP1, "LAMP-01").bus_address == \
        sim.mcc.lamp(SITE, GRP2, "LAMP-01").bus_address


# ===========================================================================
# NEGATIVE / AUTHORIZATION INTEGRATION
# ===========================================================================
def test_unauthorized_operator_actions_never_reach_the_field_layer():
    sim = integrated(group_count=2, lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    transmitted = {(SITE, GRP1): sim.bus(SITE, GRP1).stats.transmitted,
                   (SITE, GRP2): sim.bus(SITE, GRP2).stats.transmitted}
    before = [sim.mcc.lamp_status(SITE, g, "LAMP-01") for g in (GRP1, GRP2)]

    denied_on = sim.mcc.force_on(SITE, GRP1, "LAMP-01", VIEWER, command_id="int-denied-on")
    denied_off = sim.mcc.force_off(SITE, GRP2, "LAMP-01", VIEWER, command_id="int-denied-off")
    for record in (denied_on, denied_off):
        assert record.state is CommandState.REJECTED
        assert record.succeeded is False

    for key, count in transmitted.items():
        assert sim.bus(key[0], key[1]).stats.transmitted == count
    for group, status in zip((GRP1, GRP2), before):
        after = sim.mcc.lamp_status(SITE, group, "LAMP-01")
        assert after.active_override is status.active_override is OverrideState.NONE
        assert after.actual_state is status.actual_state
    denied = [e for e in sim.mcc.events()
              if e.event_type is EventType.COMMAND_REJECTED]
    assert denied and {e.actor for e in denied} == {VIEWER.actor_id}


def test_engineering_only_actions_stay_protected_through_the_whole_path():
    sim = integrated(lamps_per_group=2, status_max_age_ticks=50_000)
    observe(sim)
    node = sim.node(SITE, GRP1, "LAMP-01")
    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    energy_before = node.last_measurement.energy
    assert energy_before and energy_before > 0

    # An operator may control the lamp but may not reset its energy counter,
    # and the refusal happens before anything is transmitted.
    transmitted = sim.bus(SITE, GRP1).stats.transmitted
    denied = sim.mcc.request_control(
        SITE, GRP1, "LAMP-01", ControlSubtype.RESET_ENERGY, OPERATOR,
        command_id="int-reset")
    assert denied.state is CommandState.REJECTED
    assert "not authorized" in denied.result, "the refusal names its reason"
    assert sim.bus(SITE, GRP1).stats.transmitted == transmitted
    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    assert node.last_measurement.energy >= energy_before, "the counter was not reset"

    # The gate is privilege, not a blanket refusal: the same action is accepted
    # from an engineer, routed, executed and verified, and the counter really
    # does restart from zero.
    allowed = sim.mcc.request_control(
        SITE, GRP1, "LAMP-01", ControlSubtype.RESET_ENERGY, ENGINEER,
        command_id="int-reset-engineer")
    sim.pump(SITE, GRP1)
    sim.gc(SITE, GRP1).collect_responses()
    assert allowed.state is CommandState.ACTUAL_STATE_VERIFIED, allowed.result
    node.step(healthy_sources(), ticks=sim.clock.ticks + 1)
    assert node.last_measurement.energy < energy_before, "the counter restarted"

    # Time and configuration distribution are administration actions and are
    # not routed by the data layer at all.
    assert not any(name in ("synchronize_time", "write_configuration", "distribute_configuration")
                   for name in dir(sim.mcc))


def test_mcc_never_becomes_the_source_of_truth_for_lamp_state():
    """A view that disagrees with the field layer is a bug, not a feature."""
    sim = integrated(lamps_per_group=2, status_max_age_ticks=100_000)
    observe(sim)
    for group in (GRP1,):
        for lamp in sim.lamp_ids(SITE, group):
            status = sim.mcc.lamp_status(SITE, group, lamp)
            node = sim.node(SITE, group, lamp)
            assert status.effective_mode is node.control.effective_mode
            assert status.active_override is node.control.active_override
            assert status.commanded_state is node.last_measurement.commanded_state
            assert status.voltage == node.last_measurement.voltage
            assert status.power == node.last_measurement.power
            assert status.measured_ticks == node.last_measurement.timestamp.ticks
