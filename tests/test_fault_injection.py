"""Phase 14 - deterministic fault injection and system-level digital validation.

Every test in this module injects a defined fault (or a defined sequence of
faults) into the digital model, asserts the state *before* the injection, then
asserts the immediate response, the retry/deadline behaviour, the eventual
state, the audit evidence and the fact that unaffected components stayed
unaffected. Nothing here is a physical test: the module validates the digital
prototype only and makes no claim about electrical safety, EMC/RF behaviour or
hardware performance.

Coverage follows the Phase 14 scope:

1. lighting and sensor faults,
2. electrical measurement faults,
3. switching-feedback faults,
4. communication faults (silence, drops, corruption, malformed payloads,
   version/destination faults, duplicates, stale and delayed frames, retry
   exhaustion, recovery, 16-bit sequence wrap),
5. remote-command faults for all five control subtypes,
6. fault-lifecycle faults (confirmation, latching, repair, recurrence,
   illegal transitions, audit relationships),
7. notification faults (delivery, retry, reminder, escalation),
8. storage faults (corruption, incomplete records, power loss, capacity,
   confirmation versus deletion, retention, authorization),
9. time faults (unsynchronized time, threshold crossing, stale synchronization,
   deterministic logical ordering),
10. multi-node containment in a 16-node group,
11. store-and-forward failure sequences while the upstream link is gone,
12. the end-to-end scenarios A-J.

The harness lives in ``tests/fault_injection.py``. Traceability for every
scenario is recorded in ``docs/requirements_traceability.md`` section 7. The
scenarios in this module did not introduce product requirements; the defects
and open decisions they exposed are recorded in ``docs/09_digital_prototype_scope.md``
and ``docs/IMPLEMENTATION_REPORT.md``.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from conftest import healthy_sources
from fault_injection import (
    ADMIN,
    BRIGHT,
    DARK,
    ENGINEER,
    OPERATOR,
    VIEWER,
    FaultyUpstreamLink,
    GroupSim,
    commanded_off_calm,
    confirmed_fault,
    controller_fault,
    driven,
    electrical_missing,
    electrical_nonfinite,
    feedback_off_while_commanded_on,
    feedback_on_while_commanded_off,
    feedback_unknown,
    inconsistent_power,
    light_dead_band,
    light_invalid,
    light_missing,
    light_nonfinite,
    light_oscillating,
    light_out_of_range,
    open_load,
    over_current,
    supply_abnormal,
    under_current,
    unexpected_current,
)
from sslv1.comm import Frame, MessageType, PROTOCOL_VERSION, decode_frame, decode_payload, encode_payload
from sslv1.comm.crc import crc16_xmodem
from sslv1.comm.frame import MASTER_ADDRESS
from sslv1.diagnostics import Confidence, DiagnosticClassification
from sslv1.enums import (
    CommandState,
    CommState,
    ControlSubtype,
    ControllerStatus,
    EventSeverity,
    EventSource,
    EventType,
    FaultSeverity,
    FaultState,
    FaultType,
    LampState,
    NotificationState,
    OperatingMode,
    RecordLifecycleState,
    RecordType,
    SensorStatus,
    TimeSyncState,
)
from sslv1.errors import (
    AuthorizationError,
    IllegalTransitionError,
    ProtocolError,
    StorageError,
    StorageFullError,
)
from sslv1.identity import DeviceIdentity, Identifier
from sslv1.storage import StorageRecord


# ==========================================================================
# 1. LIGHTING / SENSOR FAULTS (PR-LIGHT-001..004, PR-FAULT-005/006)
# ==========================================================================
def test_sensor_missing_light_keeps_state_and_is_not_a_lamp_fault():
    """A missing light measurement must not change the automatic state."""
    sim = GroupSim(node_count=1)
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    assert node.control.lamp_is_on is True
    before = node.control.lamp_is_on

    decision = sim.step(node, sources=light_missing(), ticks=2000)
    assert decision.commanded_state is LampState.ON
    assert node.control.lamp_is_on is before
    assert "no valid light level" in decision.reason
    assert node.last_measurement.light_level is None
    assert node.faults.active_faults == ()
    assert node.faults.faults == ()


def test_nonfinite_light_is_rejected_as_evidence_and_is_a_sensor_fault():
    """A non-finite light level is never used as control evidence."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON

    decision = sim.step(node, sources=light_nonfinite(), ticks=2000)
    assert decision.commanded_state is LampState.ON
    assert "no valid light level" in decision.reason
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.SENSOR_ABNORMALITY
    assert diagnostic.fault_category is FaultType.LIGHT_SENSOR
    assert diagnostic.confidence is Confidence.MEDIUM


def test_out_of_range_light_is_classified_from_evidence_not_as_load_failure():
    """An impossible light level is a sensor observation, not a lamp failure."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    sim.step(node, sources=light_out_of_range(), ticks=2000)
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.SENSOR_ABNORMALITY
    assert diagnostic.fault_category is FaultType.LIGHT_SENSOR
    assert diagnostic.classification is not DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert node.faults.active_faults[0].fault_type is FaultType.LIGHT_SENSOR


def test_sensor_becoming_invalid_while_on_keeps_the_lamp_on_and_confirms():
    """A sensor failure while the lamp is ON never switches the lighting."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    assert node.control.lamp_is_on is True

    sim.step(node, sources=light_invalid(), ticks=2000)
    assert node.control.lamp_is_on is True
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.SUSPECTED
    assert fault.confirmation_count == 1
    assert fault.diagnostic_classification is DiagnosticClassification.SENSOR_ABNORMALITY

    sim.step(node, sources=light_invalid(), ticks=3000)
    sim.step(node, sources=light_invalid(), ticks=4000)
    assert fault.state is FaultState.CONFIRMED
    assert fault.confirmation_count == 3
    assert node.control.lamp_is_on is True
    # Confirmation initialises notification state and issues the notification;
    # it awaits acknowledgement without touching the lamp.
    assert fault.notification_state is NotificationState.ACK_PENDING
    assert fault.notification_reason


def test_sensor_recovery_before_confirmation_leaves_no_stale_fault():
    """Recovery before confirmation must clear the suspicion, not duplicate it."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=light_invalid(), ticks=2000)
    suspected = node.faults.active_faults[0]
    assert suspected.state is FaultState.SUSPECTED

    sim.step(node, sources=DARK, ticks=3000)
    assert node.faults.active_faults == ()
    assert suspected.state is FaultState.NORMAL
    assert suspected.confirmation_count == 1

    # A later recurrence is a new record, never a silent reuse of the old one.
    sim.step(node, sources=light_invalid(), ticks=4000)
    recurrence = node.faults.active_faults[0]
    assert recurrence.fault_id != suspected.fault_id
    assert recurrence.state is FaultState.SUSPECTED
    assert len(node.faults.active_faults) == 1


def test_confirmed_sensor_fault_latches_until_repair_not_until_recovery():
    """A confirmed sensor fault is not cleared by later valid evidence."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, light_invalid(), 3)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED

    sim.step(node, sources=DARK, ticks=4000)
    sim.step(node, sources=DARK, ticks=5000)
    assert fault.state is FaultState.CONFIRMED
    assert fault.is_active is True
    assert node.control.lamp_is_on is True


def test_threshold_oscillation_does_not_create_one_alert_per_crossing():
    """Oscillation around the threshold must not generate independent alerts."""
    sim = GroupSim()
    node = sim.node
    states = []
    for index, sources in enumerate(light_oscillating(), start=1):
        decision = sim.step(node, sources=sources, ticks=index * 1000)
        states.append(decision.commanded_state)
    # Alternating evidence alternates the commanded state (hysteresis is 0.0
    # in this configuration) but creates no *lamp-health* fault: classification
    # follows the evidence rather than the number of threshold crossings.
    assert states == [LampState.ON, LampState.OFF] * 3
    lamp_health = [f for f in node.faults.faults
                   if f.fault_type not in (FaultType.ENVIRONMENTAL,)]
    assert lamp_health == []
    assert not [e for e in node.events
                if e.event_type is EventType.FAULT_CONFIRMED
                and e.event_data.get("fault_type") != FaultType.ENVIRONMENTAL.value]


def test_oscillation_inside_the_dead_band_retains_one_state_and_no_fault():
    """Inside the configured dead band the state is retained, not re-decided."""
    sim = GroupSim(lamp_config_overrides={"light_hysteresis": 60.0})
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    for index in range(4):
        decision = sim.step(node, sources=light_dead_band(100.0), ticks=2000 + index * 1000)
        assert decision.commanded_state is LampState.ON
        assert "retaining state" in decision.reason
    assert node.faults.faults == ()


def test_sensor_health_is_classified_from_evidence_only():
    """Diagnostic classification follows the evidence, not the lamp state."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    assert node._last_diagnostic.classification is DiagnosticClassification.NORMAL
    assert node._last_assessment.physically_consistent is True

    # A DEGRADED sensor is not trusted as control evidence, but the healthy
    # signature of the lamp itself is still classified as normal.
    sim.step(node, sources=healthy_sources(sensor_status=SensorStatus.DEGRADED), ticks=2000)
    assert node._last_diagnostic.classification is DiagnosticClassification.NORMAL
    assert node.control.lamp_is_on is True

    sim.step(node, sources=light_invalid(), ticks=3000)
    assert node._last_assessment.has_issues
    assert node._last_diagnostic.classification is DiagnosticClassification.SENSOR_ABNORMALITY
    assert node._last_diagnostic.fault_category is FaultType.LIGHT_SENSOR


# ==========================================================================
# 2. ELECTRICAL MEASUREMENT FAULTS (PR-DIAG-001..003, PR-FAULT-005)
# ==========================================================================
def test_under_current_needs_consecutive_evidence_to_confirm():
    """One under-current sample must not confirm a persistent fault."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    assert node.faults.active_faults == ()

    sim.step(node, sources=under_current(), ticks=2000)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.SUSPECTED
    assert fault.confirmation_count == 1
    assert fault.diagnostic_classification is DiagnosticClassification.POSSIBLE_UNDER_CURRENT

    sim.step(node, sources=under_current(), ticks=3000)
    assert fault.state is FaultState.SUSPECTED
    assert fault.confirmation_count == 2

    sim.step(node, sources=under_current(), ticks=4000)
    assert fault.state is FaultState.CONFIRMED
    assert fault.confirmation_count == 3
    assert fault.severity is FaultSeverity.MINOR


def test_intervening_normal_evidence_breaks_consecutive_confirmation():
    """Normal evidence between abnormal samples must not count towards it."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=under_current(), ticks=2000)
    first = node.faults.active_faults[0]

    sim.step(node, sources=healthy_sources(), ticks=3000)
    assert node.faults.active_faults == ()
    assert first.state is FaultState.NORMAL

    sim.step(node, sources=under_current(), ticks=4000)
    sim.step(node, sources=under_current(), ticks=5000)
    second = node.faults.active_faults[0]
    assert second.fault_id != first.fault_id
    assert second.state is FaultState.SUSPECTED
    assert second.confirmation_count == 2

    sim.step(node, sources=under_current(), ticks=6000)
    assert second.state is FaultState.CONFIRMED


def test_zero_current_while_commanded_on_is_possible_open_load():
    """Zero current with the path ON is an open-load observation."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=open_load(), ticks=2000)
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert fault.fault_type is FaultType.UNDER_CURRENT
    assert fault.severity is FaultSeverity.MAJOR
    assert fault.evidence["current"] == 0.0
    assert fault.evidence["commanded_state"] == LampState.ON.value


def test_current_while_commanded_off_is_unexpected_current():
    """Current with the lamp commanded OFF is not silently accepted."""
    sim = GroupSim()
    node = sim.node
    record = node.force_off(OPERATOR, ticks=1)
    assert record.state is CommandState.ACKNOWLEDGED
    assert sim.step(node, sources=commanded_off_calm(), ticks=1000).commanded_state \
        is LampState.OFF
    assert node.faults.active_faults == ()

    sim.step(node, sources=unexpected_current(), ticks=2000)
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.UNEXPECTED_CURRENT
    assert fault.fault_type is FaultType.LAMP_LOAD
    assert fault.severity is FaultSeverity.MAJOR


def test_over_current_is_classified_from_evidence():
    """Over-current is confirmed from repeated evidence, not a single sample."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=over_current(), ticks=2000)
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.POSSIBLE_OVER_CURRENT
    assert fault.fault_type is FaultType.OVER_CURRENT
    assert fault.state is FaultState.SUSPECTED


def test_inconsistent_voltage_current_power_is_measurement_abnormality():
    """Voltage, current and power that cannot coexist are flagged as such."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=inconsistent_power(), ticks=2000)
    assert node._last_assessment.physically_consistent is False
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.MEASUREMENT_ABNORMALITY
    assert fault.fault_type is FaultType.UNKNOWN


def test_missing_voltage_while_commanded_on_is_a_supply_observation():
    """No voltage at all while commanded ON is a supply classification."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=electrical_missing(), ticks=2000)
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.SUPPLY_ABNORMALITY
    assert diagnostic.classification is not DiagnosticClassification.POSSIBLE_OPEN_LOAD
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.SUSPECTED
    assert fault.fault_type is FaultType.SUPPLY_VOLTAGE


def test_missing_current_and_power_are_insufficient_evidence_not_a_load_fault():
    """Missing load readings must not be turned into a lamp-failure claim."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    sim.step(node, sources=healthy_sources(current=None, power=None), ticks=2000)
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.INSUFFICIENT_EVIDENCE
    assert diagnostic.fault_category is FaultType.INSPECTION_REQUIRED
    assert diagnostic.classification is not DiagnosticClassification.POSSIBLE_OPEN_LOAD
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.SUSPECTED
    assert fault.severity is FaultSeverity.INFO


def test_nonfinite_electrical_evidence_is_abnormal_and_not_over_current():
    """A non-finite reading is evidence failure, not a load classification."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=electrical_nonfinite(), ticks=2000)
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.MEASUREMENT_ABNORMALITY
    assert diagnostic.classification is not DiagnosticClassification.POSSIBLE_OVER_CURRENT
    assert diagnostic.confidence is Confidence.LOW


def test_abnormal_supply_voltage_is_supply_abnormality():
    """A supply outside the configured band while commanded ON is a supply fault."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=supply_abnormal(), ticks=2000)
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.SUPPLY_ABNORMALITY
    assert fault.fault_type is FaultType.SUPPLY_VOLTAGE
    assert fault.severity is FaultSeverity.MAJOR


def test_original_and_latest_evidence_are_kept_distinct():
    """The confirmation evidence is retained while latest observations update."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    driven(sim, node, under_current(), 3, step_ticks=1000)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED
    original = dict(fault.evidence)
    assert original["current"] == 0.10

    # A later abnormal observation updates the latest evidence while the
    # original confirmation evidence is preserved unchanged.
    node.step(healthy_sources(current=0.08, power=18.4), ticks=5000)
    assert fault.evidence == original
    assert fault.latest_evidence["current"] == 0.08
    assert fault.latest_evidence != fault.evidence
    assert fault.state is FaultState.CONFIRMED

    # A normal observation changes neither: the fault is latched, not cleared.
    node.step(healthy_sources(current=0.45, power=103.5), ticks=6000)
    assert fault.evidence == original
    assert fault.latest_evidence["current"] == 0.08


# ==========================================================================
# 3. SWITCHING FEEDBACK FAULTS (PR-CONTROL-002, PR-DIAG-002)
# ==========================================================================
def test_commanded_state_is_never_confused_with_actual_state():
    """Commanded ON with feedback OFF keeps both observations separate."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    sim.step(node, sources=feedback_off_while_commanded_on(), ticks=2000)

    measurement = node.last_measurement
    assert measurement.commanded_state is LampState.ON
    assert measurement.switching_feedback is LampState.OFF
    assert measurement.actual_state is LampState.OFF
    assert measurement.commanded_state is not measurement.actual_state
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.SWITCHING_PATH_INCONSISTENCY
    assert fault.severity is FaultSeverity.MINOR


def test_feedback_on_while_commanded_off_is_not_a_silent_success():
    """Commanded OFF with the path still ON is reported as an inconsistency."""
    sim = GroupSim()
    node = sim.node
    record = node.force_off(OPERATOR, ticks=1)
    assert record.state is CommandState.ACKNOWLEDGED
    sim.step(node, sources=commanded_off_calm(), ticks=1000)
    assert record.succeeded is True
    assert node.last_measurement.commanded_state is LampState.OFF
    assert node.last_measurement.actual_state is LampState.OFF
    sim.step(node, sources=feedback_on_while_commanded_off(), ticks=2000)
    measurement = node.last_measurement
    assert measurement.commanded_state is LampState.OFF
    assert measurement.switching_feedback is LampState.ON
    assert measurement.actual_state is LampState.ON
    fault = node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.SWITCHING_PATH_INCONSISTENCY


def test_unknown_feedback_is_insufficient_evidence_not_a_fault_claim():
    """Unreadable feedback must not be turned into a load-failure claim."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=feedback_unknown(), ticks=2000)
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.INSUFFICIENT_EVIDENCE
    assert node.last_measurement.actual_state is LampState.UNKNOWN
    assert diagnostic.fault_category is FaultType.INSPECTION_REQUIRED


def test_switching_recovery_clears_a_suspected_inconsistency():
    """Matching feedback after a single inconsistency clears the suspicion."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=feedback_off_while_commanded_on(), ticks=2000)
    suspected = node.faults.active_faults[0]
    assert suspected.state is FaultState.SUSPECTED

    sim.step(node, sources=DARK, ticks=3000)
    assert node.faults.active_faults == ()
    assert suspected.state is FaultState.NORMAL


def test_confirmed_switching_inconsistency_latches_until_repair():
    """A confirmed inconsistency is not cleared by later matching feedback."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    driven(sim, node, feedback_off_while_commanded_on(), 3, step_ticks=1000)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED

    sim.step(node, sources=DARK, ticks=5000)
    assert fault.state is FaultState.CONFIRMED
    assert node.control.lamp_is_on is True


def test_diagnostic_result_is_advisory_and_never_drives_the_switch():
    """The diagnostic engine reports; the control model decides."""
    sim = GroupSim()
    node = sim.node
    decision = sim.step(node, sources=DARK, ticks=1000)
    assert decision.commanded_state is LampState.ON
    sim.step(node, sources=feedback_off_while_commanded_on(), ticks=2000)
    assert node._last_diagnostic.requires_attention is True
    # The lamp was not switched off, and not switched on, by the diagnosis.
    assert node.control.lamp_is_on is True
    assert node.last_measurement.commanded_state is LampState.ON


# ==========================================================================
# 4. COMMUNICATION FAULTS (PR-COMM-003/005/006/008, PR-FAULT-012)
# ==========================================================================
def test_silent_node_retries_then_comm_fault_does_not_affect_others():
    """A silent node degrades alone; the rest of the group stays healthy."""
    sim = GroupSim(node_count=3)
    sim.step_all(ticks=1000)
    sim.rounds(1)
    assert [sim.comm_state(node) for node in sim.nodes] == [CommState.COMM_HEALTHY] * 3

    sim.silence(2)
    before_drop = sim.bus.stats.dropped
    try:
        sim.rounds(3, ticks_per_round=1000)
    finally:
        sim.silence(2, silent=False)

    assert sim.bus.stats.dropped > before_drop, "the fault was never injected"
    assert sim.comm_state(sim.node_for(2)) is CommState.COMM_FAULT
    assert sim.comm_state(sim.node_for(1)) is CommState.COMM_HEALTHY
    assert sim.comm_state(sim.node_for(3)) is CommState.COMM_HEALTHY
    assert sim.gc.degraded_nodes() == (sim.node_for(2).lamp_id,)
    assert [node.control.lamp_is_on for node in sim.nodes] == [True, True, True]


def test_dropped_request_is_retried_only_within_the_absolute_deadline():
    """Retries are bounded by the configured count and the absolute expiry."""
    sim = GroupSim()
    reg = sim.registration(sim.node)
    assert sim.poll(MessageType.STATUS_REQUEST, drop_request_to=1) == {1: False}
    assert sim.injections.requests_dropped == 1
    assert reg.awaiting_response is True
    transmitted = sim.bus.stats.transmitted
    pending = next(iter(sim.gc._pending.values()))
    expiry = pending["expires"]
    assert expiry - sim.clock.ticks == sim.gc.config.poll_timeout_ticks * (sim.gc.config.poll_retry_count + 1)

    sim.advance(sim.gc.config.poll_timeout_ticks)
    sim.service_timeouts()
    assert sim.bus.stats.transmitted == transmitted + 1
    assert reg.comm.state is CommState.RETRY

    sim.advance(sim.gc.config.poll_timeout_ticks)
    sim.service_timeouts()
    assert sim.bus.stats.transmitted == transmitted + 2

    sim.advance(sim.gc.config.poll_timeout_ticks)
    sim.service_timeouts()
    # The final deadline ends the transaction: no fourth transmission.
    assert sim.bus.stats.transmitted == transmitted + 2
    assert sim.gc._pending == {}


def test_dropped_response_is_reported_without_reexecuting_the_request():
    """A lost reply causes a retry, never a second execution of the action."""
    sim = GroupSim()
    node = sim.node
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="once-only")
    assert record.state is CommandState.RECEIVED
    sim.deliver(drop=1)
    assert sim.injections.responses_dropped == 1
    assert node.control.active_override.value == "FORCE_ON"
    applied = sim.events_of(node, EventType.OVERRIDE_APPLIED)
    assert len(applied) == 1

    sim.advance(sim.gc.config.poll_timeout_ticks)
    sim.service_timeouts()
    sim.deliver()
    # The retried request is a duplicate at the node: answered from the cache.
    assert len(sim.events_of(node, EventType.OVERRIDE_APPLIED)) == 1
    assert len(sim.events_of(node, EventType.DUPLICATE_FRAME_DETECTED)) == 1
    assert len(node.commands.records) == 1
    assert record.state is CommandState.ACKNOWLEDGED


def test_corrupted_response_is_excluded_counted_and_recovered():
    """A frame that fails its CRC is never delivered, and recovery is possible."""
    sim = GroupSim()
    reg = sim.registration(sim.node)
    assert sim.rounds(1) is None
    assert reg.last_seen_ticks is not None

    reg.last_seen_ticks = None
    sim.poll(MessageType.STATUS_REQUEST)
    sim.deliver(corrupt=1)
    assert sim.injections.corrupted_frames == 1
    assert reg.last_seen_ticks is None

    sim.advance(sim.gc.config.poll_timeout_ticks)
    sim.service_timeouts()
    sim.deliver()
    assert reg.last_seen_ticks is not None
    assert reg.comm.state in (CommState.RECOVERY, CommState.COMM_HEALTHY)


def test_malformed_payload_is_rejected_without_poisoning_receiver_state():
    """A decodable frame with an undecodable payload changes nothing."""
    sim = GroupSim()
    reg = sim.registration(sim.node)
    sim.step(sim.node, ticks=1000)
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    sim.deliver(malformed=1)
    assert sim.injections.malformed_frames == 1
    assert reg.last_measurement is None
    assert reg.sequences.newest is None
    rejected = [e for e in sim.gc.events if e.event_type is EventType.FRAME_REJECTED]
    assert rejected and "payload" in rejected[-1].reason

    # The same request answered properly still works.
    sim.advance(sim.gc.config.poll_timeout_ticks)
    sim.service_timeouts()
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    sim.deliver()
    assert reg.last_measurement is not None


def test_unsupported_version_wrong_destination_and_foreign_source_are_ignored():
    """Adressing/version faults are refused before any state change."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    before = node.snapshot()
    before.pop("events")

    wrong_destination = Frame(MASTER_ADDRESS, 2, MessageType.STATUS_REQUEST, b"", 11)
    node.receive(wrong_destination)
    assert node.process_incoming() == []

    foreign_source = Frame(7, 1, MessageType.STATUS_REQUEST, b"", 12)
    node.receive(foreign_source)
    assert node.process_incoming() == []

    wrong_version = Frame(MASTER_ADDRESS, 1, MessageType.STATUS_REQUEST, b"", 13,
                          protocol_version=PROTOCOL_VERSION + 1)
    node.receive(wrong_version)
    assert node.process_incoming() == []

    after = node.snapshot()
    after.pop("events")
    assert after == before, "a rejected frame must not mutate node state"
    reasons = [e.reason for e in node.events if e.event_type is EventType.FRAME_REJECTED]
    assert len(reasons) == 3
    assert all("invalid version, destination or master source" in reason for reason in reasons)

    # A wire-level version fault cannot even be decoded.
    wire = bytearray(Frame(1, MASTER_ADDRESS, MessageType.STATUS_RESPONSE).encode())
    wire[1] = PROTOCOL_VERSION + 1
    wire[-2:] = crc16_xmodem(wire[:-2]).to_bytes(2, "big")
    with pytest.raises(ProtocolError):
        decode_frame(bytes(wire))


def test_duplicate_and_stale_frames_do_not_corrupt_receiver_state():
    """Duplicate delivery is answered from cache; replayed traffic is refused."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    request = Frame(MASTER_ADDRESS, 1, MessageType.STATUS_REQUEST, b"", 200)
    sim.bus.send(request)
    first = node.process_incoming()
    assert len(first) == 1
    newest = node._request_sequences.newest
    assert newest == 200

    sim.bus.send(request)
    repeated = node.process_incoming()
    assert len(repeated) == 1, "a duplicate request must still be answered"
    assert repeated[0].message_type is first[0].message_type
    assert node._request_sequences.newest == newest
    assert len(sim.events_of(node, EventType.DUPLICATE_FRAME_DETECTED)) == 1

    stale = Frame(MASTER_ADDRESS, 1, MessageType.STATUS_REQUEST, b"", (newest - 200) % 0x10000)
    sim.bus.send(stale)
    assert node.process_incoming() == []
    assert node._request_sequences.newest == newest
    assert len(sim.events_of(node, EventType.STALE_FRAME_DETECTED)) == 1


def test_delayed_response_after_the_final_deadline_is_refused():
    """A response that arrives too late cannot complete the transaction."""
    sim = GroupSim()
    reg = sim.registration(sim.node)
    sim.step(sim.node, ticks=1000)
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    captured = sim.capture()
    assert len(captured) == 1
    assert reg.last_measurement is None

    sim.advance(sim.gc.config.poll_timeout_ticks * (sim.gc.config.poll_retry_count + 1) + 1)
    sim.service_timeouts()
    assert reg.comm.state is CommState.COMM_FAULT
    assert sim.gc._pending == {}

    sim.replay(captured)
    assert reg.last_measurement is None
    rejected = [e for e in sim.gc.events if e.event_type is EventType.FRAME_REJECTED]
    assert rejected, "the late response must be reported, not silently dropped"


def test_retry_exhaustion_does_not_invent_extra_missed_exchanges():
    """Exhaustion finishes the request without fabricating further failures."""
    sim = GroupSim()
    reg = sim.registration(sim.node)
    sim.poll(MessageType.STATUS_REQUEST, drop_request_to=1)
    for _ in range(sim.gc.config.poll_retry_count + 1):
        sim.advance(sim.gc.config.poll_timeout_ticks)
        sim.service_timeouts()
    assert reg.comm.state is CommState.COMM_FAULT
    assert reg.comm.consecutive_failures == sim.gc.config.poll_retry_count + 1
    fault_events = [e for e in sim.gc.events if e.event_type is EventType.COMM_FAULT_DETECTED]
    assert len(fault_events) == 1

    sim.advance(sim.gc.config.poll_timeout_ticks * 10)
    sim.service_timeouts()
    assert reg.comm.consecutive_failures == sim.gc.config.poll_retry_count + 1


def test_recovery_needs_fresh_valid_exchanges_not_the_old_state():
    """COMM_FAULT -> RECOVERY -> COMM_HEALTHY requires real replies."""
    sim = GroupSim()
    reg = sim.registration(sim.node)
    sim.silence(1)
    sim.rounds(3)
    sim.silence(1, silent=False)
    assert reg.comm.state is CommState.COMM_FAULT

    # Let the in-flight lost transaction finish before offering traffic again.
    sim.advance(sim.gc.config.poll_timeout_ticks * (sim.gc.config.poll_retry_count + 1))
    sim.service_timeouts()
    assert sim.gc._pending == {}

    # A recovered link does not flap straight back to healthy: the first valid
    # exchange only moves it through RECOVERY.
    sim.rounds(1)
    assert reg.comm.state is CommState.RECOVERY
    assert reg.last_poll_success is True

    sim.rounds(1)
    assert reg.comm.state is CommState.COMM_HEALTHY


def test_sequence_wrap_keeps_new_traffic_valid_and_replay_detected():
    """After the 16-bit wrap, new traffic is processed and old traffic refused."""
    sim = GroupSim(node_count=2)
    sim.gc._sequence = 0xFFFF - 2
    sim.rounds(2)
    reg = sim.registration(sim.node_for(1))
    assert reg.last_seen_ticks is not None
    assert reg.duplicate_frames == 0
    assert reg.stale_frames == 0
    assert sim.comm_state(sim.node_for(1)) is CommState.COMM_HEALTHY

    newest = reg.sequences.newest
    assert newest is not None
    cached_response = list(sim.node_for(1)._request_cache.values())[-1][1]
    stale = replace(cached_response, sequence=(newest - 500) % 0x10000)
    sim.bus.send(stale)
    sim.gc.collect_responses()
    assert reg.stale_frames == 1
    assert reg.sequences.newest == newest
    assert sim.comm_state(sim.node_for(1)) is CommState.COMM_HEALTHY


# ==========================================================================
# 5. REMOTE COMMAND FAULTS (PR-CONTROL-002/003, PR-COMM-007, PR-SECURITY-*)
# ==========================================================================
def test_remote_force_on_lifecycle_is_ordered_and_evidence_based():
    """The full documented lifecycle, with fresh evidence at the end."""
    sim = GroupSim()
    node = sim.node
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="lifecycle-1")
    assert record.state is CommandState.RECEIVED
    assert record.executed_ticks is None and record.verified_ticks is None

    sim.deliver()
    assert record.state is CommandState.ACKNOWLEDGED
    assert not record.succeeded, "an execution ACK is not verification"

    sim.step(node, ticks=sim.clock.ticks + 1000)
    sim.deliver()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert record.succeeded is True
    assert record.evidence["command_id"] == record.command_id
    assert record.transmitted_ticks is not None

    stamps = [record.received_ticks, record.executed_ticks,
              record.acknowledged_ticks, record.verified_ticks]
    assert all(stamp is not None for stamp in stamps)
    assert stamps == sorted(stamps)
    kinds = [e.event_type for e in sim.gc.events]
    assert kinds.index(EventType.COMMAND_RECEIVED) < kinds.index(EventType.COMMAND_VERIFIED)


@pytest.mark.parametrize("subtype, observation, final_state", [
    (ControlSubtype.LAMP_ON, dict(light_level=10.0), LampState.ON),
    (ControlSubtype.LAMP_OFF, dict(light_level=10.0, switching_feedback=LampState.OFF,
                                   current=0.0, power=0.0), LampState.OFF),
    (ControlSubtype.RETURN_TO_AUTO, None, None),
    (ControlSubtype.SET_MODE, None, None),
    (ControlSubtype.RESET_ENERGY, None, None),
])
def test_every_remote_subtype_is_verified_from_node_evidence(subtype, observation,
                                                             final_state):
    """Each control subtype either verifies or fails, never by delivery alone."""
    sim = GroupSim()
    node = sim.node
    if subtype in (ControlSubtype.LAMP_OFF, ControlSubtype.RETURN_TO_AUTO):
        sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="pre-override")
        sim.deliver()
        sim.step(node, ticks=1000)
        sim.deliver()

    parameter = 1 if subtype is ControlSubtype.SET_MODE else 0  # FIXED_SCHEDULE
    record = sim.forward(subtype, ENGINEER, command_id="remote-" + subtype.value,
                         parameter=parameter)
    sim.deliver()
    # Override and mode commands are verifiable from the node's own state, so
    # they verify in the same exchange. Physical ON/OFF still needs a fresh
    # post-command observation before it can be verified.
    if subtype in (ControlSubtype.LAMP_ON, ControlSubtype.LAMP_OFF):
        assert record.state is CommandState.ACKNOWLEDGED, record.result
        assert not record.succeeded
    else:
        assert record.state is CommandState.ACTUAL_STATE_VERIFIED

    if observation is not None:
        sim.step(node, ticks=sim.clock.ticks + 1000, **observation)
        sim.deliver()

    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    if final_state is not None:
        assert node.control.lamp_is_on is (final_state is LampState.ON)
        assert node.last_measurement.actual_state is final_state


def test_remote_command_to_an_unreachable_node_fails_without_side_effects():
    """An unreachable node fails the command and never executes it."""
    sim = GroupSim()
    node = sim.node
    sim.silence(1)
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="unreachable")
    for _ in range(sim.gc.config.poll_retry_count + 1):
        sim.advance(sim.gc.config.poll_timeout_ticks)
        sim.service_timeouts()
    assert record.state is CommandState.FAILED
    assert record.executed_ticks is None
    assert node.control.active_override.value == "NONE"
    assert node.control.lamp_is_on is False
    assert sim.gc._pending_commands == {}
    assert sim.comm_state(node) is CommState.COMM_FAULT


def test_lost_ack_times_out_to_failed_and_a_late_ack_cannot_resurrect_it():
    """Delivery alone must never become success (scenario D)."""
    sim = GroupSim()
    node = sim.node
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="lost-ack")
    captured = sim.capture()
    assert captured, "the node must have answered for the ACK to be lost"
    assert node.control.active_override.value == "FORCE_ON"

    seen = []
    for _ in range(sim.gc.config.poll_retry_count + 1):
        sim.advance(sim.gc.config.poll_timeout_ticks)
        sim.service_timeouts()
        seen.append(record.state)
    # The master never saw an execution ACK, so it never claims one.
    assert CommandState.ACKNOWLEDGED not in seen
    assert record.state is CommandState.FAILED
    assert record.verified_ticks is None

    sim.replay(captured)
    assert record.state is CommandState.FAILED
    assert record.succeeded is False
    assert [e for e in sim.gc.events if e.event_type is EventType.FRAME_REJECTED]


def test_node_side_rejection_is_reported_and_never_changes_the_lamp():
    """A node that refuses the asserted actor reports the refusal."""
    sim = GroupSim()
    node = sim.node
    payload = encode_payload(MessageType.CONTROL_COMMAND, {
        "subtype": ControlSubtype.RESET_ENERGY, "target_state": LampState.UNKNOWN,
        "command_id": "forged-privilege", "parameter": 0, "actor": VIEWER})
    before = node.snapshot()
    before.pop("events")
    energy_before = node._energy
    sim.bus.send(Frame(MASTER_ADDRESS, 1, MessageType.CONTROL_COMMAND, payload, 900))
    ack = node.process_incoming()[0]
    fields = decode_payload(MessageType.CONTROL_ACK, ack.payload)
    assert fields["execution_status"] is CommandState.REJECTED
    after = node.snapshot()
    after.pop("events")
    assert after == before, "a forged privileged command must change nothing"
    assert node._energy == energy_before, "the energy accumulator must not be reset"
    assert node.control.active_override.value == "NONE"
    assert node.commands.records[0].state is CommandState.REJECTED
    reasons = [e.reason for e in node.events if e.event_type is EventType.COMMAND_REJECTED]
    assert reasons and "viewer-01" in reasons[0]


def test_actual_state_mismatch_fails_instead_of_claiming_success():
    """A lamp that did not switch must fail verification."""
    sim = GroupSim()
    node = sim.node
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="no-switch")
    sim.deliver()
    assert record.state is CommandState.ACKNOWLEDGED

    sim.step(node, ticks=sim.clock.ticks + 1000,
             light_level=10.0, switching_feedback=LampState.OFF, current=0.0, power=0.0)
    sim.deliver()
    assert record.state is CommandState.FAILED
    assert record.succeeded is False
    assert record.verified_ticks is None
    assert node.control.lamp_is_on is True, "failure must not silently switch lighting off"


def test_stale_pre_command_observation_cannot_verify_a_command():
    """Only a measurement taken after execution can verify."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)  # a matching observation, but before the command
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="stale-evidence")
    sim.deliver()
    assert record.state is CommandState.ACKNOWLEDGED
    for _ in range(3):
        sim.deliver()
    assert record.state is CommandState.ACKNOWLEDGED
    assert record.verified_ticks is None

    sim.step(node, ticks=sim.clock.ticks + 1000)
    sim.deliver()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED


def test_duplicate_command_id_is_idempotent_and_conflicting_reuse_is_rejected():
    """Identical reuse does not re-execute; conflicting reuse is rejected."""
    sim = GroupSim()
    node = sim.node
    first = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="stable-id")
    sim.deliver()
    transmitted = sim.bus.stats.transmitted
    duplicate = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="stable-id")
    assert duplicate is first
    assert sim.bus.stats.transmitted == transmitted

    conflict = sim.forward(ControlSubtype.LAMP_OFF, OPERATOR, command_id="stable-id")
    assert conflict is not first
    assert conflict.state is CommandState.REJECTED
    assert "conflicts with an existing request" in conflict.result
    assert first.state is CommandState.ACKNOWLEDGED
    assert node.control.active_override.value == "FORCE_ON"


def test_unauthorized_remote_command_never_reaches_the_bus():
    """A VIEWER command is rejected before transmission and audited."""
    sim = GroupSim()
    node = sim.node
    transmitted = sim.bus.stats.transmitted
    record = sim.forward(ControlSubtype.LAMP_ON, VIEWER, command_id="viewer-attempt")
    assert record.state is CommandState.REJECTED
    assert sim.bus.stats.transmitted == transmitted
    assert node.process_incoming() == []
    assert node.control.active_override.value == "NONE"
    assert sim.gc.events.events[-1].actor == VIEWER.actor_id
    assert sim.gc.events.events[-1].event_type is EventType.COMMAND_REJECTED


def test_command_failure_on_one_node_does_not_block_the_others():
    """Independent nodes keep working while one command fails."""
    sim = GroupSim(node_count=4)
    for node in sim.nodes:
        sim.step(node, ticks=1000)
    sim.silence(3)
    try:
        failed = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, node=sim.node_for(3),
                             command_id="isolated-failure")
        records = [sim.forward(ControlSubtype.LAMP_ON, OPERATOR, node=node,
                               command_id="peer-%d" % index)
                   for index, node in enumerate((sim.node_for(1), sim.node_for(2),
                                                 sim.node_for(4)), start=1)]
        sim.deliver()
        moment = sim.clock.ticks + sim.node.config.measurement_interval_ticks
        for node in (sim.node_for(1), sim.node_for(2), sim.node_for(4)):
            sim.step(node, ticks=moment)
        sim.deliver()
        for _ in range(4):
            sim.advance(sim.gc.config.poll_timeout_ticks)
            sim.service_timeouts()
    finally:
        sim.silence(3, silent=False)

    assert failed.state is CommandState.FAILED
    assert all(record.succeeded for record in records)
    assert sim.node_for(1).control.lamp_is_on is True
    assert sim.node_for(4).control.lamp_is_on is True
    assert sim.comm_state(sim.node_for(3)) is CommState.COMM_FAULT
    assert sim.comm_state(sim.node_for(1)) is CommState.COMM_HEALTHY


def test_command_deadline_shorter_than_a_measurement_cycle_is_an_open_decision():
    """Pin the documented consequence of a deadline below one measurement cycle.

    Phase 14 finding OPEN-14-02: nothing in ``LampConfiguration.validate()``
    relates ``comm_timeout_ticks * (comm_retry_count + 1)`` to
    ``measurement_interval_ticks``. A configuration whose absolute command
    deadline is shorter than one local measurement cycle therefore executes the
    action but can never verify it, so every physical ON/OFF command ends
    FAILED. Whether the configuration must be rejected or the deadline derived
    is an open engineering decision; this test pins the current behaviour so a
    future decision cannot change silently.
    """
    sim = GroupSim(lamp_config_overrides={
        "measurement_interval_ticks": 5000,
        "comm_timeout_ticks": 100,
        "comm_retry_count": 1,
    })
    node = sim.node
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="too-tight")
    sim.deliver()
    assert record.state is CommandState.ACKNOWLEDGED
    assert node.control.active_override.value == "FORCE_ON", "the action really executed"

    for _ in range(sim.gc.config.poll_retry_count + 1):
        sim.advance(sim.gc.config.poll_timeout_ticks)
        sim.service_timeouts()
    assert record.state is CommandState.FAILED
    assert record.verified_ticks is None
    assert node.control.lamp_is_on is True, "no lighting safety consequence"


# ==========================================================================
# 6. FAULT LIFECYCLE FAULTS (PR-FAULT-003..011)
# ==========================================================================
def test_first_observation_is_only_suspected():
    """A single observation never confirms anything."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    sim.step(node, sources=open_load(), ticks=2000)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.SUSPECTED
    assert fault.confirmation_count == 1
    assert fault.confirmed_ticks is None
    assert fault.first_observation_ticks == fault.last_observation_ticks == 2000
    assert node.faults.faults[0].is_confirmed is False


def test_confirmation_threshold_confirms_once_per_condition():
    """Reaching the threshold confirms the existing record exactly once."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, sources=DARK, ticks=1000)
    for index in range(5):
        sim.step(node, sources=open_load(), ticks=2000 + index * 500)
    confirmed = [e for e in node.events if e.event_type is EventType.FAULT_CONFIRMED]
    assert len(confirmed) == 1
    assert len(node.faults.faults) == 1
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED
    assert fault.confirmation_count == 5
    assert fault.confirmed_ticks == 3000


def test_persistent_fault_latches_and_temporary_normal_evidence_does_not_close():
    """A confirmed fault survives normal evidence and stays managed."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED
    closed_events = [e for e in node.events if e.event_type is EventType.FAULT_CLOSED]

    for index in range(3):
        sim.step(node, sources=healthy_sources(current=0.45, power=103.5),
                 ticks=4000 + index * 1000)
    assert fault.state is FaultState.CONFIRMED
    assert fault.closed_ticks is None
    assert len(node.events.filter(event_type=EventType.FAULT_CLOSED)) == len(closed_events)
    assert fault.is_active is True


def test_recurrence_after_closure_creates_a_linked_new_record():
    """Recurrence is a new fault linked to the closed one."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    first = node.faults.active_faults[0]
    node.acknowledge_fault(first.fault_id, OPERATOR, ticks=4000)
    node.start_repair(first.fault_id, ENGINEER, ticks=5000)
    node.report_repaired(first.fault_id, ENGINEER, ticks=6000)
    node.verify_repair(first.fault_id, ENGINEER, verified=True, ticks=7000)
    assert first.state is FaultState.CLOSED
    assert node.faults.active_faults == ()

    driven(sim, node, open_load(), 3, step_ticks=1000, start_ticks=7000)
    recurrence = node.faults.active_faults[0]
    assert recurrence.fault_id != first.fault_id
    assert recurrence.previous_fault_id == first.fault_id
    assert recurrence.state is FaultState.CONFIRMED
    assert len(node.faults.active_faults) == 1


@pytest.mark.parametrize("operation, from_state", [
    ("start_repair", FaultState.CONFIRMED),
    ("report_repaired", FaultState.CONFIRMED),
    ("verify", FaultState.ACKNOWLEDGED),
    ("acknowledge", FaultState.UNDER_REPAIR),
])
def test_illegal_fault_transitions_do_not_mutate_state(operation, from_state):
    """An illegal transition raises, is audited, and changes nothing."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    if from_state is FaultState.ACKNOWLEDGED:
        node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=4000)
    elif from_state is FaultState.UNDER_REPAIR:
        node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=4000)
        node.start_repair(fault.fault_id, ENGINEER, ticks=5000)
    assert fault.state is from_state
    before = (fault.state, fault.repair_status, fault.verification_status,
              fault.acknowledged_ticks, fault.closed_ticks)

    with pytest.raises(IllegalTransitionError):
        if operation == "start_repair":
            node.start_repair(fault.fault_id, ENGINEER, ticks=6000)
        elif operation == "report_repaired":
            node.report_repaired(fault.fault_id, ENGINEER, ticks=6000)
        elif operation == "verify":
            node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=6000)
        else:
            node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=6000)

    after = (fault.state, fault.repair_status, fault.verification_status,
             fault.acknowledged_ticks, fault.closed_ticks)
    assert after == before
    rejected = [e for e in node.events
                if e.event_type is EventType.FAULT_TRANSITION_REJECTED]
    assert rejected, "the rejected transition must be audited"


def test_acknowledgement_repair_and_verification_close_the_fault():
    """The full repair workflow closes the fault with actors and time."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]

    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=4000)
    assert fault.state is FaultState.ACKNOWLEDGED
    assert fault.acknowledged_ticks == 4000
    assert fault.actor == OPERATOR.actor_id

    node.start_repair(fault.fault_id, ENGINEER, ticks=5000)
    assert fault.state is FaultState.UNDER_REPAIR
    assert fault.repair_status.value == "IN_PROGRESS"

    node.report_repaired(fault.fault_id, ENGINEER, ticks=6000)
    assert fault.state is FaultState.VERIFYING
    assert fault.verification_status.value == "VERIFYING"

    node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=7000,
                       evidence={"checked": "replaced driver"})
    assert fault.state is FaultState.CLOSED
    assert fault.closed_ticks == 7000
    assert fault.closed_actor == ENGINEER.actor_id
    assert fault.verification_evidence == {"checked": "replaced driver"}
    assert fault.is_active is False
    assert node.faults.active_faults == ()


def test_failed_verification_reactivates_the_fault():
    """A failed repair verification returns the fault to active repair."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=4000)
    node.start_repair(fault.fault_id, ENGINEER, ticks=5000)
    node.report_repaired(fault.fault_id, ENGINEER, ticks=6000)

    node.verify_repair(fault.fault_id, ENGINEER, verified=False, ticks=7000,
                       evidence={"still": "dim"})
    assert fault.state is FaultState.UNDER_REPAIR
    assert fault.is_active is True
    assert fault.closed_ticks is None
    assert fault.repair_status.value == "NOT_REPAIRED"
    assert fault.verification_status.value == "VERIFICATION_FAILED"
    assert node.faults.active_faults == (fault,)

    node.report_repaired(fault.fault_id, ENGINEER, ticks=8000)
    node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=9000)
    assert fault.state is FaultState.CLOSED


def test_fault_events_preserve_actor_time_and_fault_relationship():
    """Audit events carry the actor, supplied tick and fault identity."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=4000)
    node.start_repair(fault.fault_id, ENGINEER, ticks=5000)

    related = node.events.filter(related_fault_id=fault.fault_id)
    assert related, "fault events must be linked back to the fault"
    acknowledged = [e for e in related if e.event_type is EventType.FAULT_ACKNOWLEDGED][0]
    assert acknowledged.actor == OPERATOR.actor_id
    assert acknowledged.timestamp.ticks == 4000
    repaired = [e for e in related if e.event_type is EventType.FAULT_REPAIR_STARTED][0]
    assert repaired.actor == ENGINEER.actor_id
    assert repaired.timestamp.ticks == 5000
    assert repaired.source is EventSource.FAULT
    assert set(fault.related_event_ids) >= {e.event_id for e in related[:3]}


# ==========================================================================
# 7. NOTIFICATION FAULTS (PR-FAULT-007/008/009/013)
# ==========================================================================
def test_repeated_observations_do_not_reset_notification_timers():
    """Persistent evidence must not restart reminders or escalation."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    engine = node.notifications
    assert fault.notification_state is NotificationState.ACK_PENDING
    deadline = engine._last_notified[fault.fault_id]
    assert deadline == fault.confirmed_ticks

    for index in range(4):
        sim.step(node, sources=open_load(), ticks=4000 + index * 1000)
    assert engine._last_notified[fault.fault_id] == deadline
    assert fault.notification_state is NotificationState.ACK_PENDING
    assert len([e for e in node.events
                if e.event_type is EventType.FAULT_NOTIFIED]) == 1


def test_reminder_is_issued_once_and_does_not_spam():
    """The reminder interval produces exactly one reminder event."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    last = node.notifications._last_notified[fault.fault_id]
    interval = node.config.ack_reminder_interval_ticks

    sim.step(node, sources=open_load(), ticks=last + interval)
    assert fault.notification_state is NotificationState.REMINDER_DUE
    assert len(node.events.filter(event_type=EventType.FAULT_REMINDER_DUE)) == 1

    for offset in (1, 5, 50):
        sim.step(node, sources=open_load(), ticks=last + interval + offset * 1000)
        assert fault.notification_state is NotificationState.REMINDER_DUE
        assert len(node.events.filter(event_type=EventType.FAULT_REMINDER_DUE)) == 1


def test_escalation_happens_at_the_configured_deadline_not_before():
    """Escalation waits for the configured timeout and fires once."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    last = node.notifications._last_notified[fault.fault_id]
    timeout = node.config.escalation_timeout_ticks

    sim.step(node, sources=open_load(), ticks=last + timeout - 1000)
    assert fault.notification_state is NotificationState.REMINDER_DUE
    assert len(node.events.filter(event_type=EventType.FAULT_ESCALATED)) == 0

    sim.step(node, sources=open_load(), ticks=last + timeout)
    assert fault.notification_state is NotificationState.ESCALATED
    escalations = node.events.filter(event_type=EventType.FAULT_ESCALATED)
    assert len(escalations) == 1
    assert escalations[0].timestamp.ticks == last + timeout
    assert node.config.escalation_destination in escalations[0].reason


def test_delivery_failure_follows_the_configured_retry_path():
    """Delivery failures retry, then rest in DELIVERY_FAILED (OPEN-14-03).

    Phase 14 finding OPEN-14-03: ``docs/04_fault_management.md`` section 8.3
    documents that the notification "rests in DELIVERY_FAILED" after the
    configured retry count, while its transition table lists
    ``DELIVERY_FAILED -> ESCALATED`` as "retries exhausted". The engine
    implements the section 8.3 wording; whether an undeliverable notification
    must escalate is an open engineering decision. This test pins the current
    behaviour, including the fact that the failure is always audited.
    """
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    engine = node.notifications
    limit = node.config.notification_retry_count

    assert engine.notify(fault, ticks=4000, delivered=False) is NotificationState.PENDING
    assert engine.notify(fault, ticks=5000, delivered=False) is NotificationState.PENDING
    assert engine.notify(fault, ticks=6000, delivered=False) is NotificationState.DELIVERY_FAILED
    for extra in range(1, 4):
        state = engine.notify(fault, ticks=6000 + extra, delivered=False)
        assert state is NotificationState.DELIVERY_FAILED

    failures = node.events.filter(event_type=EventType.FAULT_NOTIFICATION_FAILED)
    assert len(failures) == limit + 4
    assert all(e.timestamp.ticks >= 4000 for e in failures)
    # Delivery failure never mutates the fault lifecycle or the lighting.
    assert fault.state is FaultState.CONFIRMED
    assert node.control.lamp_is_on is True


def test_notification_state_never_mutates_the_fault_lifecycle_or_lamp():
    """Reminders and escalation leave the fault and the lamp untouched."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    before = (fault.state, fault.confirmed_ticks, fault.closed_ticks)
    last = node.notifications._last_notified[fault.fault_id]

    sim.step(node, sources=open_load(), ticks=last + node.config.ack_reminder_interval_ticks)
    sim.step(node, sources=open_load(), ticks=last + node.config.escalation_timeout_ticks)
    assert fault.notification_state is NotificationState.ESCALATED
    assert (fault.state, fault.confirmed_ticks, fault.closed_ticks) == before
    assert node.control.lamp_is_on is True
    assert node.faults.active_faults == (fault,)


def test_acknowledgement_stops_reminders_without_closing_the_fault():
    """Acknowledgement records awareness; it is not a cure."""
    sim = GroupSim()
    node = sim.node
    driven(sim, node, open_load(), 3)
    fault = node.faults.active_faults[0]
    fault_events = len(node.events)

    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=4000)
    assert fault.state is FaultState.ACKNOWLEDGED
    assert node.notifications._acknowledged
    last = node.notifications._last_notified[fault.fault_id]

    for offset in (30_000, 120_000, 300_000):
        sim.step(node, sources=open_load(), ticks=last + offset)
    assert fault.notification_state is NotificationState.ACK_PENDING
    assert len(node.events.filter(event_type=EventType.FAULT_REMINDER_DUE)) == 0
    assert len(node.events.filter(event_type=EventType.FAULT_ESCALATED)) == 0
    assert node.control.lamp_is_on is True
    assert node.events.__len__() > fault_events


# ==========================================================================
# 8. STORAGE FAULTS (PR-STORAGE-003..010)
# ==========================================================================
def pull_measurements(sim: GroupSim) -> None:
    """One documented pull cycle: request, answer, ingest, confirm."""
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    sim.deliver()


def pull_until_confirmed(sim: GroupSim, node) -> None:
    """Run documented pull cycles until every valid measurement is confirmed.

    Records become ``RETAINED`` only after the Group Controller confirms the
    sequence number it received in the *next* request, so a stored measurement
    needs two exchange cycles: one to send it, one to confirm it.
    """
    for _ in range(len(node.storage.records) + 3):
        sim.poll(MessageType.MEASUREMENT_REQUEST)
        sim.deliver()
        if not [r for r in node.storage.pending_upload if r.is_valid()]:
            return
    raise AssertionError("stored measurements were never confirmed")


def test_corrupt_record_is_never_confirmed_or_uploaded_and_recovery_discards_it():
    """CRC failure -> flagged, excluded, audited; it is never confirmed."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    sim.step(node, ticks=2000)
    records = list(node.storage.pending_upload)
    assert [r.is_valid() for r in records] == [True, True]
    corrupt_record, intact_record = records

    node.storage.corrupt(corrupt_record.sequence_number)
    detected = node.storage.detect_corruption()
    assert corrupt_record.sequence_number in [r.sequence_number for r in detected]
    assert corrupt_record.integrity_ok() is False
    with pytest.raises(StorageError):
        node.storage.mark_confirmed(corrupt_record.sequence_number)
    assert corrupt_record.lifecycle_state is RecordLifecycleState.CORRUPT

    pull_until_confirmed(sim, node)
    corruption_events = node.events.filter(event_type=EventType.RECORD_CORRUPT)
    assert corruption_events, "corruption must be visible, never silent"
    assert all(e.severity is EventSeverity.ERROR for e in corruption_events)
    reg = sim.registration(node)
    assert reg.received_record_sequences == {intact_record.sequence_number}
    assert corrupt_record.sequence_number not in reg.received_record_sequences
    assert corrupt_record.sequence_number in [r.sequence_number
                                              for r in node.storage.pending_upload]
    assert corrupt_record.sequence_number not in [
        r.sequence_number for r in node.storage.retained]
    assert intact_record.lifecycle_state is RecordLifecycleState.RETAINED
    assert sim.gc.forward_upstream() == {"uploaded": 1, "confirmed": 1, "failed": 0}

    discarded = node.storage.recover()
    assert corrupt_record.sequence_number in [r.sequence_number for r in discarded]
    assert corrupt_record.sequence_number not in node.storage._records
    assert corrupt_record.sequence_number not in [r.sequence_number
                                                  for r in node.storage.pending_upload]


def test_incomplete_record_is_refused_discarded_and_audited():
    """A record without a commit marker is never trusted or uploaded."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    complete = node.storage.pending_upload[0]

    node.storage._sequence += 1
    partial = StorageRecord(
        sequence_number=node.storage._sequence,
        timestamp=complete.timestamp,
        record_type=RecordType.EVENT,
        payload={"partial": True},
        device_id=complete.device_id,
    )
    assert partial.is_valid() is False
    node.storage._records[partial.sequence_number] = partial
    node.storage._pending_upload.append(partial.sequence_number)

    incomplete = node.storage.simulate_power_loss()
    assert incomplete == (partial.sequence_number,)
    with pytest.raises(StorageError):
        node.storage.create(RecordType.MEASUREMENT, {}, complete.timestamp,
                            complete.device_id)
    with pytest.raises(StorageError):
        node.storage.mark_uploaded(partial.sequence_number)

    discarded = node.storage.recover()
    assert [r.sequence_number for r in discarded] == [partial.sequence_number]
    assert partial.sequence_number not in node.storage._records
    assert complete.sequence_number in node.storage._records
    assert node.storage.is_full is False, "full state must not be sticky after recovery"
    # The store keeps its own audit log; the discard is recorded there with
    # the record identity (see the Phase 14 storage-audit observation).
    recovered = [e for e in node.storage.events
                 if e.event_type is EventType.RECORD_CORRUPT
                 and e.event_data.get("sequence_number") == partial.sequence_number]
    assert recovered, "the discarded incomplete record must be audited"
    assert recovered[0].severity is EventSeverity.ERROR


def test_no_silent_loss_across_a_power_loss_cycle():
    """Committed records survive power loss and are uploaded afterwards."""
    sim = GroupSim()
    node = sim.node
    for index in range(3):
        sim.step(node, ticks=(index + 1) * 1000)
    sequences = [record.sequence_number for record in node.storage.pending_upload]
    assert sequences == [1, 2, 3]

    node.storage.simulate_power_loss()
    node.storage.recover()
    assert [r.sequence_number for r in node.storage.pending_upload] == sequences
    assert len(node.storage) == 3

    pull_until_confirmed(sim, node)
    assert sim.registration(node).received_record_sequences == set(sequences)
    result = sim.gc.forward_upstream()
    assert result == {"uploaded": 3, "confirmed": 3, "failed": 0}
    assert sorted(sim.upstream.received) == [1, 2, 3]
    assert [r.lifecycle_state for r in node.storage.retained] == \
        [RecordLifecycleState.RETAINED] * 3


def test_storage_full_is_explicit_and_capacity_returns_after_deletion():
    """Capacity exhaustion is visible, never silent, and never frees itself."""
    sim = GroupSim(storage_capacity=3)
    node = sim.node
    for index in range(3):
        sim.step(node, ticks=(index + 1) * 1000)
    assert node.storage.is_full is False
    assert len(node.storage) == 3
    assert node.snapshot()["storage_full"] is False

    sim.step(node, ticks=4000)
    assert node.storage.is_full is True
    assert node.snapshot()["storage_full"] is True
    assert len(node.storage) == 3, "refused writes must not overwrite old records"
    full_events = node.events.filter(event_type=EventType.STORAGE_FULL)
    assert len(full_events) == 1
    assert full_events[0].severity is EventSeverity.ERROR
    assert node.control.lamp_is_on is True, "storage pressure must not switch lighting off"

    pull_until_confirmed(sim, node)
    assert sim.gc.forward_upstream() == {"uploaded": 3, "confirmed": 3, "failed": 0}
    assert node.storage.is_full is True, "a full store does not free itself"

    node.storage.delete(1, ADMIN, ticks=5000)
    assert node.storage.is_full is False
    # Capacity counts live records; a deleted record leaves a tombstone in the
    # store's record map and identity list.
    live = [r for r in node.storage.records
            if r.lifecycle_state is not RecordLifecycleState.DELETED]
    assert len(live) == 2
    sim.step(node, ticks=6000)
    live = [r for r in node.storage.records
            if r.lifecycle_state is not RecordLifecycleState.DELETED]
    assert len(live) == 3, "a freed slot is usable again"
    assert node.storage.is_full is False


def test_lost_upload_confirmation_keeps_the_record_and_resend_is_not_a_duplicate():
    """A lost confirmation is not a lost record and not a duplicate insert."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    pull_measurements(sim)
    record = sim.gc.storage.pending_upload[0]

    sim.upstream.lose_confirmations = 1
    assert sim.gc.forward_upstream() == {"uploaded": 0, "confirmed": 0, "failed": 1}
    assert sim.upstream.confirmations_lost == 1
    assert sim.upstream.received == [record.sequence_number], "received but unconfirmed"
    assert record.lifecycle_state is RecordLifecycleState.UPLOADED
    assert record.upload_attempts == 1
    assert record.sequence_number in [r.sequence_number
                                      for r in sim.gc.storage.pending_upload]

    assert sim.gc.forward_upstream() == {"uploaded": 1, "confirmed": 1, "failed": 0}
    assert sim.upstream.received == [record.sequence_number, record.sequence_number]
    assert record.lifecycle_state is RecordLifecycleState.RETAINED
    assert record.upload_attempts == 2

    assert sim.gc.forward_upstream() == {"uploaded": 0, "confirmed": 0, "failed": 0}
    assert len(sim.upstream.received) == 2, "a confirmed record is never re-sent"


def test_upload_confirmation_is_not_deletion():
    """Confirmation removes the record from the queue but keeps it retained."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    sim.step(node, ticks=2000)
    pull_until_confirmed(sim, node)
    assert sim.gc.forward_upstream() == {"uploaded": 2, "confirmed": 2, "failed": 0}

    assert sim.gc.storage.pending_upload == ()
    assert len(sim.gc.storage.retained) == 2
    assert sim.gc.storage.deleted_sequences == ()
    assert sim.gc.storage.records[0].lifecycle_state is RecordLifecycleState.RETAINED


def test_unauthorized_deletion_is_rejected_audited_and_deletes_nothing():
    """Deletion requires privilege; a refusal leaves the record intact."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    pull_until_confirmed(sim, node)
    record = node.storage.retained[0]

    with pytest.raises(AuthorizationError):
        node.storage.delete(record.sequence_number, VIEWER, ticks=2000)
    with pytest.raises(AuthorizationError):
        node.storage.delete(record.sequence_number, OPERATOR, ticks=2000)
    assert record.sequence_number in node.storage._records
    assert record.sequence_number not in node.storage.deleted_sequences
    denials = [e for e in node.storage.events if e.event_type is EventType.COMMAND_REJECTED
               and e.source is EventSource.SECURITY]
    assert len(denials) == 2
    assert denials[0].actor == VIEWER.actor_id
    assert denials[0].event_data["action"] == "DELETE_RECORD"

    assert node.storage.delete(record.sequence_number, ADMIN, ticks=3000).sequence_number \
        == record.sequence_number
    # The record leaves the live store (no longer counted against capacity and
    # no longer deletable twice) but the store keeps the tombstone identity.
    assert record.sequence_number in node.storage.deleted_sequences
    assert record.lifecycle_state is RecordLifecycleState.DELETED
    assert record.sequence_number not in [
        r.sequence_number for r in node.storage.records
        if r.lifecycle_state is not RecordLifecycleState.DELETED]
    assert len(node.storage.retained) == 0
    deletion = node.events.filter(event_type=EventType.RECORD_DELETED)[-1]
    assert deletion.actor == ADMIN.actor_id
    assert deletion.timestamp.ticks == 3000


def test_deletion_inside_minimum_retention_is_refused_and_outside_is_allowed():
    """Retention is a real barrier, not a comment."""
    sim = GroupSim(lamp_config_overrides={"minimum_retention_ticks": 10_000})
    node = sim.node
    sim.step(node, ticks=1000)
    pull_until_confirmed(sim, node)
    record = node.storage.retained[0]

    with pytest.raises(StorageError):
        node.storage.delete(record.sequence_number, ADMIN, ticks=5000)
    assert record.sequence_number in node.storage._records
    assert record.sequence_number not in node.storage.deleted_sequences

    node.storage.delete(record.sequence_number, ADMIN, ticks=20_000)
    assert record.sequence_number in node.storage.deleted_sequences


# ==========================================================================
# 9. TIME FAULTS (PR-TIME-001..005)
# ==========================================================================
def test_offline_node_never_claims_synchronized_time():
    """A node that never synchronized publishes uncertain timestamps."""
    sim = GroupSim()
    node = sim.node
    assert node.time.sync_state is TimeSyncState.UNSYNCHRONIZED
    assert node.time.last_sync_ticks is None

    sim.step(node, ticks=1000)
    assert node.last_measurement.timestamp.sync_state is not TimeSyncState.SYNCHRONIZED
    assert node.last_measurement.timestamp.uncertain is True
    assert node.time.seconds_since_sync() is None, "no sync has happened yet"

    pull_until_confirmed(sim, node)
    received = sim.registration(node).last_measurement
    assert received.timestamp.sync_state is not TimeSyncState.SYNCHRONIZED
    stored = [r for r in sim.gc.storage.records if r.record_type is RecordType.MEASUREMENT]
    assert stored[0].payload["time_sync_state"] != TimeSyncState.SYNCHRONIZED.value


def test_valid_synchronization_is_confirmed_audited_and_restores_the_state():
    """A valid master sync is verified from the node's own TIME_ACK."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)

    results = sim.gc.synchronize_time(actor=ADMIN)
    assert results == {1: False}
    sim.deliver()

    assert node.time.sync_state is TimeSyncState.SYNCHRONIZED
    assert node.time.last_sync_ticks == node.time.clock.ticks
    registration = sim.registration(node)
    assert registration.time_ack is not None
    assert registration.time_ack["master_ticks"] == registration.time_ack["local_ticks"]
    assert registration.awaiting_response is False
    assert registration.last_poll_success is True
    assert registration.comm.state is CommState.COMM_HEALTHY
    synchronized = sim.gc.events.filter(event_type=EventType.TIME_SYNCHRONIZED)
    assert len(synchronized) == 1
    assert synchronized[0].actor == ADMIN.actor_id
    assert synchronized[0].timestamp.ticks == sim.clock.ticks

    # A node whose time is no longer trusted says so, and a fresh sync restores it.
    sim.step(node, ticks=sim.clock.ticks + 1000)
    assert node.time.sync_state is TimeSyncState.UNCERTAIN
    assert node.last_measurement.timestamp.uncertain is True
    sim.gc.synchronize_time(actor=ADMIN)
    sim.deliver()
    assert node.time.sync_state is TimeSyncState.SYNCHRONIZED


def test_delayed_sync_never_moves_time_backwards_or_fakes_sync():
    """A stale master tick is refused; time is monotonic and honestly uncertain."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    local_before = node.time.clock.ticks
    stale = local_before - 500

    sim.gc.synchronize_time(master_ticks=stale, actor=ADMIN)
    sim.deliver()

    assert node.time.clock.ticks >= local_before, "time must never move backwards"
    assert node.time.sync_state is not TimeSyncState.SYNCHRONIZED
    assert node.last_measurement.timestamp.uncertain is True
    # The mismatch is reported, never silently accepted.
    rejected = sim.gc.events.filter(event_type=EventType.FRAME_REJECTED)
    assert rejected and "time ACK" in rejected[-1].reason
    assert sim.registration(node).time_ack is None

    # Recovery: a sync that matches the current master time is accepted.
    sim.gc.synchronize_time(actor=ADMIN)
    sim.deliver()
    assert node.time.sync_state is TimeSyncState.SYNCHRONIZED
    assert sim.registration(node).time_ack is not None


def test_time_distribution_requires_privilege_and_publishes_no_wall_clock():
    """Sync is authorized, audited and never a hidden physical RTC claim."""
    sim = GroupSim()
    node = sim.node
    transmitted = sim.bus.stats.transmitted

    with pytest.raises(AuthorizationError):
        sim.gc.synchronize_time(actor=VIEWER)
    assert sim.bus.stats.transmitted == transmitted
    assert node.time.sync_state is TimeSyncState.UNSYNCHRONIZED
    denied = sim.gc.events.filter(event_type=EventType.COMMAND_REJECTED)
    assert denied and denied[-1].actor == VIEWER.actor_id

    # Defensive node-side check for a forged TIME_SYNC arriving on the bus.
    from sslv1.comm.protocol import encode_payload as _encode
    payload = _encode(MessageType.TIME_SYNC, {"master_ticks": sim.clock.ticks + 100,
                                              "actor": VIEWER})
    sim.bus.send(Frame(MASTER_ADDRESS, 1, MessageType.TIME_SYNC, payload, 77))
    assert node.process_incoming() == []
    assert node.time.sync_state is TimeSyncState.UNSYNCHRONIZED
    rejection = [e for e in node.events if e.event_type is EventType.COMMAND_REJECTED]
    assert rejection and rejection[-1].reason == "time synchronization denied"

    # Time is logical: a wall-clock reading requires an explicit epoch and the
    # model never stores a datetime of its own.
    stamp = node.time.now()
    assert stamp.sync_state is TimeSyncState.UNSYNCHRONIZED
    assert stamp.as_datetime(sim.clock.epoch).year == 2026
    assert not hasattr(stamp, "isoformat") or callable(stamp.isoformat)


def test_offline_records_keep_their_original_time_validity_after_later_sync():
    """Synchronizing later must not rewrite the validity of stored history."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    pull_until_confirmed(sim, node)
    stored = [r for r in sim.gc.storage.records if r.record_type is RecordType.MEASUREMENT]
    original = stored[0].payload["time_sync_state"]
    assert original != TimeSyncState.SYNCHRONIZED.value

    sim.gc.synchronize_time(actor=ADMIN)
    sim.deliver()
    assert node.time.sync_state is TimeSyncState.SYNCHRONIZED
    sim.gc.forward_upstream()
    stored = [r for r in sim.gc.storage.records if r.record_type is RecordType.MEASUREMENT]
    assert stored[0].payload["time_sync_state"] == original, \
        "historical validity must not be rewritten by a later sync"
    assert stored[0].sequence_number in sim.upstream.received
    assert sim.gc.storage.pending_upload == ()


def test_logical_ordering_is_deterministic_and_reproducible():
    """The same scripted sequence produces the same tick-level ordering."""
    def run() -> list:
        sim = GroupSim(node_count=3)
        sim.step_all(ticks=1000)
        sim.rounds(2)
        sim.step_all(ticks=4000)
        sim.deliver()
        return [(e.timestamp.ticks, e.event_type.value, e.lamp_id and str(e.lamp_id))
                for e in sim.gc.events]

    first, second = run(), run()
    assert first == second
    assert first == sorted(first, key=lambda item: item[0]), \
        "events must be ordered by logical time"
    assert all(item[0] >= 0 for item in first)


# ==========================================================================
# 10. MULTI-NODE CONTAINMENT (PR-SCALABILITY-001/002, PR-COMM-009)
# ==========================================================================
def test_sixteen_node_group_with_five_independent_failures_contains_them():
    """One node, several nodes and several subsystems fail independently."""
    sim = GroupSim(node_count=16, storage_capacity=4)
    for node in sim.nodes:
        sim.step(node, ticks=1000)
    sim.rounds(1)
    assert [sim.comm_state(node) for node in sim.nodes] == [CommState.COMM_HEALTHY] * 16
    assert all(node.control.lamp_is_on for node in sim.nodes)

    # (1) one node is unreachable, (2) one node has a failing light sensor,
    # (3) one node's storage is full, (4) one node receives a command while
    # unreachable, (5) one node develops a real lamp fault.
    sim.silence(2)
    sim.silence(8)
    for extra in range(4):
        sim.step(sim.node_for(6), ticks=3000 + extra * 1000)
    driven(sim, sim.node_for(4), light_invalid(), 3, step_ticks=1000,
           start_ticks=sim.clock.ticks)
    driven(sim, sim.node_for(10), open_load(), 3, step_ticks=1000,
           start_ticks=sim.clock.ticks)
    failed = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, node=sim.node_for(8),
                         command_id="unreachable-node")

    try:
        sim.rounds(3, ticks_per_round=1000)
    finally:
        sim.silence(2, silent=False)
        sim.silence(8, silent=False)
    for _ in range(sim.gc.config.poll_retry_count + 1):
        sim.advance(sim.gc.config.poll_timeout_ticks)
        sim.service_timeouts()

    assert failed.state is CommandState.FAILED
    assert sim.comm_state(sim.node_for(2)) is CommState.COMM_FAULT
    assert sim.comm_state(sim.node_for(8)) is CommState.COMM_FAULT
    sensor_fault = sim.node_for(4).faults.active_faults[0]
    assert sensor_fault.state is FaultState.CONFIRMED
    assert sensor_fault.fault_type is FaultType.LIGHT_SENSOR
    assert sim.node_for(4).control.lamp_is_on is True
    assert sim.node_for(6).storage.is_full is True
    assert len(sim.node_for(6).events.filter(event_type=EventType.STORAGE_FULL)) == 1
    lamp_fault = sim.node_for(10).faults.active_faults[0]
    assert lamp_fault.state is FaultState.CONFIRMED
    assert lamp_fault.fault_type is not FaultType.LIGHT_SENSOR

    # Every unaffected node is still healthy, still lit and still audited.
    affected = {2, 4, 6, 8, 10}
    for index in range(1, 17):
        node = sim.node_for(index)
        if index in affected:
            continue
        assert sim.comm_state(node) is CommState.COMM_HEALTHY, "node %d" % index
        assert node.control.lamp_is_on is True, "node %d" % index
        assert node.faults.active_faults == (), "node %d" % index
        assert node.storage.is_full is False, "node %d" % index
    assert set(sim.gc.degraded_nodes()) == {sim.node_for(2).lamp_id, sim.node_for(8).lamp_id}

    # A faulty neighbour never blocks a healthy node's record transfer.
    pull_until_confirmed(sim, sim.node_for(1))
    assert sim.gc.forward_upstream()["confirmed"] >= 1
    assert sim.node_for(1).control.lamp_is_on is True
    assert sim.node_for(10).control.lamp_is_on is True


# ==========================================================================
# 11. STORE-AND-FORWARD FAILURE SEQUENCES (PR-STORAGE-008, PR-OFFLINE-004/005)
# ==========================================================================
def test_upstream_outage_buffers_without_loss_or_local_impact():
    """STORE -> RECOVERY -> SYNCHRONIZE -> UPLOAD -> CONFIRM, end to end."""
    sim = GroupSim(node_count=3)
    sim.step_all(ticks=1000)
    sim.upstream_down()

    for round_index in range(3):
        sim.advance(1000)
        sim.poll(MessageType.MEASUREMENT_REQUEST)
        sim.deliver()
    outcome = sim.gc.forward_upstream()
    assert outcome["uploaded"] == 0 and outcome["confirmed"] == 0
    assert outcome["failed"] == 3, "all three records stay buffered"
    buffered = [r for r in sim.gc.storage.records if r.record_type is RecordType.MEASUREMENT]
    assert len(buffered) == 3
    assert all(r.lifecycle_state is not RecordLifecycleState.DELETED for r in buffered)

    # Local operation is unaffected while the upstream link is down.
    sim.step_all(ticks=sim.clock.ticks + 1000, light_level=900.0,
                 switching_feedback=LampState.OFF, current=0.0, power=0.0)
    assert [node.control.lamp_is_on for node in sim.nodes] == [False, False, False]

    sim.upstream_up()
    outcome = sim.gc.forward_upstream()
    assert outcome == {"uploaded": 3, "confirmed": 3, "failed": 0}
    assert len(sim.upstream.received) == len(set(sim.upstream.received)) == 3
    assert sim.gc.storage.pending_upload == ()
    assert len(sim.gc.storage.retained) == 3
    assert sim.gc.forward_upstream() == {"uploaded": 0, "confirmed": 0, "failed": 0}


def test_lost_confirmation_during_recovery_never_loses_or_duplicates_history():
    """A lost upload response keeps the record pending until it is confirmed."""
    sim = GroupSim()
    node = sim.node
    sim.upstream_down()
    sim.step(node, ticks=1000)
    sim.upstream_up()
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    sim.deliver()

    sim.upstream.lose_confirmations = 2
    for _ in range(2):
        outcome = sim.gc.forward_upstream()
        assert outcome == {"uploaded": 0, "confirmed": 0, "failed": 1}
    record = sim.gc.storage.records[0]
    assert record.lifecycle_state is RecordLifecycleState.UPLOADED
    assert record.sequence_number in [r.sequence_number
                                      for r in sim.gc.storage.pending_upload]
    measurements = [r for r in sim.gc.storage.records
                    if r.record_type is RecordType.MEASUREMENT]
    assert len(measurements) == 1, "the buffer holds one copy, not one per attempt"

    assert sim.gc.forward_upstream() == {"uploaded": 1, "confirmed": 1, "failed": 0}
    assert record.lifecycle_state is RecordLifecycleState.RETAINED
    assert record.upload_attempts == 3
    assert sim.upstream.confirmations_lost == 2
    # The node learns about the confirmation through the normal pull path.
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    sim.deliver()
    assert node.storage.pending_upload == ()
    assert [r.sequence_number for r in node.storage.retained] == [1]


def test_repeated_polling_during_an_outage_cannot_duplicate_history():
    """Idle polls must not accumulate copies of the same reading."""
    sim = GroupSim()
    node = sim.node
    sim.upstream_down()
    sim.step(node, ticks=1000)
    for _ in range(6):
        sim.poll(MessageType.MEASUREMENT_REQUEST)
        sim.deliver()
    measurements = [r for r in sim.gc.storage.records
                    if r.record_type is RecordType.MEASUREMENT]
    assert len(measurements) == 1
    assert sim.registration(node).received_record_sequences == {1}
    assert len(node.storage.retained) == 1, "confirmed exactly once at the node"


# ==========================================================================
# 12. END-TO-END SCENARIOS (A-J)
# ==========================================================================
def test_scenario_a_local_fault_from_detection_to_closure():
    """A: normal -> lamp fault -> confirm -> notify -> ack -> repair -> verify."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    assert node.faults.active_faults == ()
    assert node.control.lamp_is_on is True

    driven(sim, node, open_load(), 3, step_ticks=1000, start_ticks=1000)
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED
    assert fault.notification_state is NotificationState.ACK_PENDING
    assert fault.severity is FaultSeverity.MAJOR
    assert len(node.events.filter(event_type=EventType.FAULT_CONFIRMED)) == 1

    node.acknowledge_fault(fault.fault_id, OPERATOR, ticks=8000)
    node.start_repair(fault.fault_id, ENGINEER, ticks=9000)
    node.report_repaired(fault.fault_id, ENGINEER, ticks=10_000)
    node.verify_repair(fault.fault_id, ENGINEER, verified=True, ticks=11_000,
                       evidence={"action": "replaced driver"})
    assert fault.state is FaultState.CLOSED
    assert fault.closed_ticks == 11_000
    assert node.faults.active_faults == ()
    kinds = [e.event_type for e in node.events]
    for expected in (EventType.FAULT_CONFIRMED, EventType.FAULT_ACKNOWLEDGED,
                     EventType.FAULT_REPAIR_STARTED, EventType.FAULT_REPAIR_REPORTED,
                     EventType.FAULT_CLOSED):
        assert expected in kinds
    assert node.control.lamp_is_on is True, "repair and notification never darken a lamp"
    assert node.storage.records, "the node keeps its own audit history"
    assert fault.related_event_ids, "fault events are linked to the fault record"


def test_scenario_b_communication_loss_and_recovery_without_service_loss():
    """B: normal -> comm loss -> retries -> comm fault -> node + comm recovery."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    sim.rounds(1)
    registration = sim.registration(node)
    assert registration.comm.state is CommState.COMM_HEALTHY

    sim.silence(1)
    try:
        sim.rounds(3, ticks_per_round=1000)
        # Lighting still follows local evidence while the master is cut off.
        sim.step(node, ticks=sim.clock.ticks + 1000, light_level=900.0,
                 switching_feedback=LampState.OFF, current=0.0, power=0.0)
        assert node.control.lamp_is_on is False
    finally:
        sim.silence(1, silent=False)
    assert registration.comm.state is CommState.COMM_FAULT
    assert registration.comm.consecutive_failures >= sim.gc.config.poll_retry_count
    assert sim.gc.degraded_nodes() == (node.lamp_id,)

    sim.rounds(1)
    assert registration.comm.state is CommState.RECOVERY
    assert registration.last_poll_success is True
    sim.rounds(1)
    assert registration.comm.state is CommState.COMM_HEALTHY
    assert sim.gc.degraded_nodes() == ()
    assert node.control.lamp_is_on is False, "recovery does not re-light a lamp by itself"


def test_scenario_c_remote_command_is_verified_from_fresh_node_evidence():
    """C: FORCE_ON -> execution ACK -> fresh measurement -> verification."""
    sim = GroupSim()
    node = sim.node
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="scenario-c")
    assert record.state is CommandState.RECEIVED
    sim.deliver()
    assert record.state is CommandState.ACKNOWLEDGED
    assert record.succeeded is False

    sim.step(node, ticks=sim.clock.ticks + 1000)
    sim.deliver()
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert record.succeeded is True
    assert record.evidence["command_id"] == "scenario-c"
    assert node.last_measurement.actual_state is LampState.ON
    assert node.control.lamp_is_on is True


def test_scenario_d_lost_ack_ends_failed_and_a_late_ack_changes_nothing():
    """D: lost ACK -> timeout -> FAILED -> late ACK -> still FAILED."""
    sim = GroupSim()
    record = sim.forward(ControlSubtype.LAMP_ON, OPERATOR, command_id="scenario-d")
    captured = sim.capture()
    assert captured
    for _ in range(sim.gc.config.poll_retry_count + 1):
        sim.advance(sim.gc.config.poll_timeout_ticks)
        sim.service_timeouts()
    assert record.state is CommandState.FAILED
    assert record.succeeded is False
    assert sim.gc._pending_commands == {}

    sim.replay(captured)
    assert record.state is CommandState.FAILED
    assert record.verified_ticks is None
    assert sim.gc.events.filter(event_type=EventType.FRAME_REJECTED)


def test_scenario_e_upstream_outage_buffers_and_recovery_transfers_history():
    """E: outage -> buffer -> recovery -> confirmed historical transfer."""
    sim = GroupSim(node_count=2)
    sim.step_all(ticks=1000)
    sim.upstream_down()
    for _ in range(3):
        sim.poll(MessageType.MEASUREMENT_REQUEST)
        sim.deliver()
    assert sim.gc.forward_upstream()["failed"] == 2
    buffered = len(sim.gc.storage.pending_upload)
    assert buffered == 2

    sim.upstream_up()
    outcome = sim.gc.forward_upstream()
    assert outcome == {"uploaded": 2, "confirmed": 2, "failed": 0}
    assert sorted(sim.upstream.received) == [1, 2], "arrival order is deterministic"
    assert sim.gc.storage.pending_upload == ()
    assert len(sim.gc.storage.retained) == 2


def test_scenario_f_corrupted_history_is_excluded_and_audited():
    """F: corrupt record -> detected -> excluded -> audited, nothing silent."""
    sim = GroupSim()
    node = sim.node
    sim.step(node, ticks=1000)
    sim.step(node, ticks=2000)
    corrupt_record = node.storage.pending_upload[0]
    node.storage.corrupt(corrupt_record.sequence_number)

    pull_until_confirmed(sim, node)
    assert corrupt_record.sequence_number not in \
        sim.registration(node).received_record_sequences
    assert node.events.filter(event_type=EventType.RECORD_CORRUPT)
    assert sim.gc.forward_upstream() == {"uploaded": 1, "confirmed": 1, "failed": 0}
    group_measurements = [r for r in sim.gc.storage.records
                          if r.record_type is RecordType.MEASUREMENT]
    assert len(group_measurements) == 1
    assert group_measurements[0].payload["timestamp_ticks"] == 2000, \
        "only the intact record travelled"

    discarded = node.storage.recover()
    assert corrupt_record.sequence_number in [r.sequence_number for r in discarded]
    audited = [e for e in node.storage.events
               if e.event_type is EventType.RECORD_CORRUPT
               and e.event_data.get("sequence_number") == corrupt_record.sequence_number]
    assert audited, "discarding invalid history must be reported"
    assert node.storage.deleted_sequences == (), "exclusion is not deletion"


def test_scenario_g_persistent_fault_reminds_and_escalates_once():
    """G: repeated observations -> one reminder and one escalation, no reset."""
    sim = GroupSim()
    node = sim.node
    fault = confirmed_fault(node)
    notified_at = node.notifications._last_notified[fault.fault_id]

    for _ in range(6):
        sim.step(node, sources=open_load(), ticks=node.time.ticks + 1000)
    assert node.notifications._last_notified[fault.fault_id] == notified_at
    assert len(node.events.filter(event_type=EventType.FAULT_NOTIFIED)) == 1

    sim.step(node, sources=open_load(),
             ticks=notified_at + node.config.ack_reminder_interval_ticks)
    sim.step(node, sources=open_load(),
             ticks=notified_at + node.config.escalation_timeout_ticks)
    sim.step(node, sources=open_load(),
             ticks=notified_at + node.config.escalation_timeout_ticks * 4)
    assert fault.notification_state is NotificationState.ESCALATED
    assert len(node.events.filter(event_type=EventType.FAULT_REMINDER_DUE)) == 1
    assert len(node.events.filter(event_type=EventType.FAULT_ESCALATED)) == 1
    assert fault.state is FaultState.CONFIRMED
    assert node.control.lamp_is_on is True


def test_scenario_h_sixteen_nodes_multiple_faults_leave_the_rest_running():
    """H: 16 nodes, several independent faults, unaffected nodes continue."""
    sim = GroupSim(node_count=16)
    sim.step_all(ticks=1000)
    sim.rounds(1)
    sim.silence(5)
    driven(sim, sim.node_for(9), light_invalid(), 3, step_ticks=1000,
           start_ticks=sim.clock.ticks)
    try:
        sim.rounds(3, ticks_per_round=1000)
    finally:
        sim.silence(5, silent=False)

    assert sim.comm_state(sim.node_for(5)) is CommState.COMM_FAULT
    assert sim.node_for(9).faults.active_faults[0].fault_type is FaultType.LIGHT_SENSOR
    healthy = [sim.node_for(index) for index in range(1, 17) if index not in (5, 9)]
    assert [sim.comm_state(node) for node in healthy] == [CommState.COMM_HEALTHY] * 14
    assert all(node.control.lamp_is_on for node in healthy)
    assert all(node.faults.active_faults == () for node in healthy)
    assert sim.gc.degraded_nodes() == (sim.node_for(5).lamp_id,)


def test_scenario_i_stale_configuration_replay_is_rejected_and_changes_nothing():
    """I: config change -> version update -> stale replay -> rejected."""
    sim = GroupSim()
    node = sim.node
    assert node.config_version == 0

    first = sim.gc.distribute_configuration(
        node.lamp_id, {"light_on_threshold": 40}, ADMIN, config_version=1)
    sim.deliver()
    assert first.state is CommandState.ACTUAL_STATE_VERIFIED
    assert node.config_version == 1
    assert node.config.light_on_threshold == 40

    second = sim.gc.distribute_configuration(
        node.lamp_id, {"light_on_threshold": 30}, ADMIN, config_version=2)
    sim.deliver()
    assert second.state is CommandState.ACTUAL_STATE_VERIFIED
    assert node.config_version == 2
    assert node.config.light_on_threshold == 30

    # A stale configuration replay arrives later as fresh traffic (a newer
    # frame sequence) carrying an old version: it must be refused and must
    # change nothing.
    newest = node._request_sequences.newest
    stale = Frame(
        MASTER_ADDRESS, 1, MessageType.CONFIG_WRITE,
        encode_payload(MessageType.CONFIG_WRITE, {
            "config_version": 1, "parameters": {"light_on_threshold": 999},
            "actor": ADMIN}),
        (newest + 1) % 0x10000)
    sim.bus.send(stale)
    ack = node.process_incoming()[0]
    fields = decode_payload(MessageType.CONFIG_ACK, ack.payload)
    assert ack.message_type is MessageType.CONFIG_ACK
    assert fields["accepted"] is False
    assert fields["config_version"] == 1
    assert "newer" in fields["reason"]
    assert node.config_version == 2
    assert node.config.light_on_threshold == 30, "a replayed configuration must not apply"
    rejected = node.events.filter(event_type=EventType.CONFIG_REJECTED)
    assert rejected and rejected[-1].actor == ADMIN.actor_id, "the refusal is audited"


def test_scenario_j_sequence_wrap_still_protects_against_replays():
    """J: wrap -> valid new traffic -> duplicate and stale traffic refused."""
    sim = GroupSim(node_count=2)
    sim.gc._sequence = 0xFFFF - 2
    sim.step_all(ticks=1000)
    sim.rounds(2)
    for node in sim.nodes:
        assert sim.comm_state(node) is CommState.COMM_HEALTHY
        assert sim.registration(node).duplicate_frames == 0
        assert sim.registration(node).stale_frames == 0

    registration = sim.registration(sim.node)
    newest = registration.sequences.newest
    cached = list(sim.node._request_cache.values())[-1][1]
    sim.bus.send(cached)
    sim.gc.collect_responses()
    assert registration.duplicate_frames == 1
    assert registration.sequences.newest == newest

    stale = replace(cached, sequence=(newest - 800) % 0x10000)
    sim.bus.send(stale)
    sim.gc.collect_responses()
    assert registration.stale_frames == 1
    assert registration.sequences.newest == newest
    assert sim.comm_state(sim.node) is CommState.COMM_HEALTHY


# ==========================================================================
# APPENDIX - additional injected-fault checks
# (bright ambient state, controller status, capacity exception, an upstream
# link that starts unavailable, and a wrongly targeted command)
# ==========================================================================
def test_bright_ambient_with_consistent_evidence_raises_no_fault():
    """The normal bright-ambient OFF state is an observation, not a fault."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    bright_off = healthy_sources(light_level=900.0, switching_feedback=LampState.OFF,
                                 current=0.0, power=0.0)
    assert sim.step(node, sources=bright_off, ticks=2000).commanded_state is LampState.OFF
    assert node.control.lamp_is_on is False
    assert node.faults.faults == ()
    assert node.faults.active_faults == ()
    # The external-illumination observation is retained, but it is not a fault:
    # confirming it would report the normal daylight state as a fault every day.
    assert node._last_diagnostic.classification is \
        DiagnosticClassification.ENVIRONMENTAL_OR_EXTERNAL
    assert node.last_measurement.effective_mode is OperatingMode.AUTO_SENSOR
    assert node.last_measurement.actual_state is LampState.OFF
    assert node.events.filter(event_type=EventType.FAULT_CONFIRMED) == ()
    assert node.events.filter(event_type=EventType.FAULT_NOTIFIED) == ()


def test_transition_with_stale_load_evidence_is_only_suspected_then_cleared():
    """Inconsistent evidence at a transition is flagged, never silently normal."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    sim.step(node, sources=BRIGHT, ticks=2000)
    assert node.control.lamp_is_on is False
    assert node._last_diagnostic.classification in (
        DiagnosticClassification.SWITCHING_PATH_INCONSISTENCY,
        DiagnosticClassification.UNEXPECTED_CURRENT,
    )
    suspected = node.faults.active_faults
    assert len(suspected) == 1
    assert suspected[0].state is FaultState.SUSPECTED

    # One consistent sample clears the suspicion: no stale fault survives.
    sim.step(node, sources=healthy_sources(light_level=900.0,
                                           switching_feedback=LampState.OFF,
                                           current=0.0, power=0.0), ticks=3000)
    assert node.faults.active_faults == ()
    assert suspected[0].state is FaultState.NORMAL
    assert node._last_diagnostic.classification is \
        DiagnosticClassification.ENVIRONMENTAL_OR_EXTERNAL
    assert node.faults.faults == (suspected[0],), "no new fault is raised"


def test_controller_fault_is_reported_without_faking_a_lamp_failure():
    """A controller that reports a fault is surfaced, not turned into a load fault."""
    sim = GroupSim()
    node = sim.node
    assert sim.step(node, sources=DARK, ticks=1000).commanded_state is LampState.ON
    sim.step(node, sources=controller_fault(), ticks=2000)

    measurement = node.last_measurement
    assert measurement.controller_status is ControllerStatus.FAULT
    diagnostic = node._last_diagnostic
    assert diagnostic.classification is DiagnosticClassification.CONTROLLER_ABNORMALITY
    assert diagnostic.fault_category is FaultType.CONTROLLER
    assert diagnostic.classification is not DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert node.control.lamp_is_on is True, "a controller fault must not force the lamp"
    fault = node.faults.active_faults[0]
    assert fault.state is FaultState.SUSPECTED, "one sample cannot confirm"
    assert fault.fault_type is FaultType.CONTROLLER


def test_full_store_raises_the_typed_error_when_written_directly():
    """The capacity refusal is typed, not an anonymous failure."""
    sim = GroupSim(storage_capacity=1)
    node = sim.node
    sim.step(node, ticks=1000)
    with pytest.raises(StorageFullError):
        node.storage.create(RecordType.MEASUREMENT, {}, node.last_measurement.timestamp,
                            node.identity)
    assert node.storage.is_full is True
    assert node.storage.retention.automatic_deletion is False


def test_upstream_link_that_starts_unavailable_buffers_then_transfers():
    """An upstream link can be born unavailable and recover later."""
    sim = GroupSim(upstream=FaultyUpstreamLink(available=False))
    node = sim.node
    sim.step(node, ticks=1000)
    sim.poll(MessageType.MEASUREMENT_REQUEST)
    sim.deliver()
    assert sim.gc.forward_upstream() == {"uploaded": 0, "confirmed": 0, "failed": 1}
    assert sim.gc.storage.pending_upload != ()

    sim.upstream_up()
    assert sim.gc.forward_upstream() == {"uploaded": 1, "confirmed": 1, "failed": 0}
    assert node.control.lamp_is_on is True


def test_command_targeted_at_another_lamp_is_refused_and_changes_nothing():
    """A command for a different device identity fails at the node."""
    from sslv1.command import Command
    from sslv1.enums import CommandType

    sim = GroupSim()
    node = sim.node
    foreign = DeviceIdentity(
        product_id=node.identity.product_id,
        site_id=node.identity.site_id,
        group_id=node.identity.group_id,
        lamp_id=Identifier("LAMP-99"),
    )
    record = node.commands.submit(
        Command(command_id="wrong-target", command_type=CommandType.FORCE_ON,
                target=foreign, actor=OPERATOR, created_ticks=sim.clock.ticks),
        sim.clock.ticks)
    assert record.state is CommandState.FAILED
    assert "target" in record.result
    assert node.control.active_override.value == "NONE"
    assert node.control.lamp_is_on is False


def test_event_records_are_forwarded_and_confirmed_without_duplication():
    """Category 11: events (not only measurements) survive an outage intact."""
    sim = GroupSim()
    node = sim.node
    sim.upstream_down()
    sim.step(node, ticks=1000)
    for _ in range(3):
        sim.poll(MessageType.EVENT_REPORT)
        sim.deliver()
    events = [r for r in sim.gc.storage.records if r.record_type is RecordType.EVENT]
    assert [r.payload["event_type"] for r in events] == \
        [event.event_type.value for event in node.events]
    assert events[0].payload["event_type"] == "NODE_STARTED"
    assert len({r.payload["event_id"] for r in events}) == len(events), "no duplicate event"
    assert sim.registration(node).confirmed_event_id == max(
        r.payload["event_id"] for r in events), "the node advances only on confirmation"

    assert sim.gc.forward_upstream()["confirmed"] == 0
    sim.upstream_up()
    outcome = sim.gc.forward_upstream()
    assert outcome["confirmed"] == len(events)
    assert len(sim.upstream.received) == len(events)
    assert sim.gc.forward_upstream() == {"uploaded": 0, "confirmed": 0, "failed": 0}
    assert len(sim.gc.storage.retained) == len(events)
