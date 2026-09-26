"""Fault lifecycle and notification-state tests (PR-FAULT-*).

Covers: fault confirmation, latching, acknowledgement, repair, successful and
failed verification, illegal transitions, and notification-state independence.
"""


import pytest

from sslv1.enums import (
    DiagnosticClassification,
    FaultState,
    FaultType,
    LampState,
    NotificationState,
    RepairStatus,
    VerificationStatus,
)
from sslv1.errors import IllegalTransitionError
from sslv1.fault import FaultEngine, FaultLifecycle
from sslv1.notification import NotificationLifecycle
from sslv1.diagnostics import Confidence, DiagnosticResult, DiagnosticEvidence
from sslv1.identity import Identifier

from conftest import SITE, GROUP, healthy_sources, make_lamp_config


def open_load_result():
    return DiagnosticResult(
        classification=DiagnosticClassification.POSSIBLE_OPEN_LOAD,
        fault_category=FaultType.UNDER_CURRENT,
        confidence=Confidence.HIGH,
        reason="commanded ON, current 0.0",
        evidence=DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.0,
            power=0.0,
            light_level=10.0,
        ),
    )


def normal_result():
    return DiagnosticResult(
        classification=DiagnosticClassification.NORMAL,
        fault_category=None,
        confidence=Confidence.HIGH,
        reason="normal",
        evidence=DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            light_level=10.0,
        ),
    )


def advance_notification(fault, target):
    """Walk the notification state machine to ``target`` legally."""
    order = [
        NotificationState.PENDING,
        NotificationState.SENT,
        NotificationState.ACK_PENDING,
        NotificationState.REMINDER_DUE,
        NotificationState.ESCALATED,
        NotificationState.DELIVERY_FAILED,
    ]
    if target not in order:
        raise AssertionError("unsupported target %s" % target)
    if fault.notification_state is NotificationState.NOT_REQUIRED:
        fault.notification_state = NotificationState.PENDING
    while fault.notification_state is not target:
        current = order.index(fault.notification_state)
        nxt = order[current + 1] if current + 1 < len(order) else order[current]
        NotificationLifecycle.transition(fault, nxt)
        if nxt is fault.notification_state:
            break


@pytest.fixture
def engine(lamp_identity):
    return FaultEngine(make_lamp_config(lamp_identity.lamp_id))


def lamp():
    return Identifier("LAMP-01")


# --------------------------------------------------------------------------
# 24. fault confirmation
# --------------------------------------------------------------------------
def test_fault_is_confirmed_only_after_configured_count(engine):
    for index in range(2):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    active = engine.active_faults
    assert len(active) == 1
    assert active[0].state is FaultState.SUSPECTED
    assert active[0].confirmation_count == 2

    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=3000)
    assert engine.active_faults[0].state is FaultState.CONFIRMED
    assert engine.active_faults[0].confirmed_ticks == 3000


def test_confirmation_count_is_configurable(lamp_identity):
    config = make_lamp_config(lamp_identity.lamp_id, fault_confirmation_count=1)
    engine = FaultEngine(config)
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000)
    assert engine.active_faults[0].state is FaultState.CONFIRMED


def test_observations_outside_the_window_reset_the_count(lamp_identity):
    config = make_lamp_config(
        lamp_identity.lamp_id,
        fault_confirmation_count=3,
        fault_confirmation_window_ticks=5000,
    )
    engine = FaultEngine(config)
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000)
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=2000)
    # Far outside the confirmation window: the count restarts.
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=50_000)
    fault = engine.active_faults[0]
    assert fault.confirmation_count == 1
    assert fault.state is FaultState.SUSPECTED


# --------------------------------------------------------------------------
# 25. fault latching
# --------------------------------------------------------------------------
def test_confirmed_fault_latches_against_a_single_normal_measurement(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    assert engine.active_faults[0].state is FaultState.CONFIRMED

    # One healthy-looking measurement must not clear a confirmed fault.
    engine.observe(SITE, GROUP, lamp(), normal_result(), ticks=10_000)
    fault = engine.active_faults[0]
    assert fault.state is FaultState.CONFIRMED


def oscillating_open_load_result(level):
    """The same fault with a measurement hovering around the threshold."""
    return DiagnosticResult(
        classification=DiagnosticClassification.POSSIBLE_OPEN_LOAD,
        fault_category=FaultType.UNDER_CURRENT,
        confidence=Confidence.HIGH,
        reason="current %.2f" % level,
        evidence=DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=level,
            power=level * 230.0,
            light_level=10.0,
        ),
    )


def test_threshold_oscillation_creates_one_fault_not_many(engine):
    """39/41/39/41 oscillation must not generate a stream of alerts."""
    for index in range(20):
        level = 0.039 if index % 2 == 0 else 0.041
        # All observations fall inside the confirmation window.
        engine.observe(SITE, GROUP, lamp(), oscillating_open_load_result(level),
                       ticks=1000 + 100 * index)
    assert len(engine.faults) == 1
    fault = engine.faults[0]
    assert fault.state is FaultState.CONFIRMED
    assert fault.confirmation_count == 20
    assert fault.is_confirmed is True


def test_unconfirmed_suspicion_clears_when_evidence_clears(engine):
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000)
    assert engine.active_faults[0].state is FaultState.SUSPECTED
    engine.observe(SITE, GROUP, lamp(), normal_result(), ticks=2000)
    assert engine.active_faults == ()
    assert engine.faults[0].state is FaultState.NORMAL


# --------------------------------------------------------------------------
# 26. fault acknowledgement
# --------------------------------------------------------------------------
def test_acknowledgement_moves_confirmed_to_acknowledged(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    engine.acknowledge(fault.fault_id, "operator-01", ticks=5000)
    assert fault.state is FaultState.ACKNOWLEDGED
    assert fault.acknowledged_ticks == 5000
    assert fault.actor == "operator-01"


def test_acknowledging_a_suspected_fault_is_rejected(engine):
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000)
    fault = engine.active_faults[0]
    with pytest.raises(IllegalTransitionError):
        engine.acknowledge(fault.fault_id, "operator-01", ticks=2000)


# --------------------------------------------------------------------------
# 27. repair
# --------------------------------------------------------------------------
def test_repair_workflow(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    engine.acknowledge(fault.fault_id, "operator-01", ticks=4000)
    engine.start_repair(fault.fault_id, "engineer-01", ticks=5000)
    assert fault.state is FaultState.UNDER_REPAIR
    assert fault.repair_status is RepairStatus.IN_PROGRESS

    engine.report_repaired(fault.fault_id, "engineer-01", ticks=6000)
    assert fault.state is FaultState.VERIFYING
    assert fault.verification_status is VerificationStatus.VERIFYING


def test_repair_cannot_start_before_acknowledgement(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    with pytest.raises(IllegalTransitionError):
        engine.start_repair(fault.fault_id, "engineer-01", ticks=4000)


# --------------------------------------------------------------------------
# 28. successful verification
# --------------------------------------------------------------------------
def test_successful_verification_closes_the_fault(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    engine.acknowledge(fault.fault_id, "operator-01", ticks=4000)
    engine.start_repair(fault.fault_id, "engineer-01", ticks=5000)
    engine.report_repaired(fault.fault_id, "engineer-01", ticks=6000)
    engine.verify(fault.fault_id, "engineer-01", ticks=7000, verified=True,
                  evidence={"current": 0.45})
    assert fault.state is FaultState.CLOSED
    assert fault.closed_ticks == 7000
    assert fault.closed_actor == "engineer-01"
    assert fault.verification_status is VerificationStatus.VERIFIED
    assert fault.verification_evidence == {"current": 0.45}


# --------------------------------------------------------------------------
# 29. failed verification
# --------------------------------------------------------------------------
def test_failed_verification_returns_to_an_active_fault_state(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    engine.acknowledge(fault.fault_id, "operator-01", ticks=4000)
    engine.start_repair(fault.fault_id, "engineer-01", ticks=5000)
    engine.report_repaired(fault.fault_id, "engineer-01", ticks=6000)
    engine.verify(fault.fault_id, "engineer-01", ticks=7000, verified=False)

    assert fault.state is FaultState.UNDER_REPAIR
    assert fault.state is not FaultState.CLOSED
    assert fault.verification_status is VerificationStatus.VERIFICATION_FAILED
    assert fault.repair_status is RepairStatus.NOT_REPAIRED


def test_verification_compares_against_original_evidence(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    original = dict(fault.evidence)
    engine.acknowledge(fault.fault_id, "operator-01", ticks=4000)
    engine.start_repair(fault.fault_id, "engineer-01", ticks=5000)
    engine.report_repaired(fault.fault_id, "engineer-01", ticks=6000)
    engine.verify(fault.fault_id, "engineer-01", ticks=7000, verified=True)
    # The original evidence snapshot is retained for the audit trail.
    assert fault.evidence["classification"] == original["classification"]


# --------------------------------------------------------------------------
# illegal transitions
# --------------------------------------------------------------------------
def test_illegal_fault_transitions_are_rejected():
    illegal = [
        (FaultState.NORMAL, FaultState.CLOSED),
        (FaultState.SUSPECTED, FaultState.ACKNOWLEDGED),
        (FaultState.CONFIRMED, FaultState.CLOSED),
        (FaultState.VERIFYING, FaultState.NORMAL),
        (FaultState.CLOSED, FaultState.UNDER_REPAIR),
    ]
    for current, target in illegal:
        assert FaultLifecycle.can_transition(current, target) is False


def test_legal_fault_transitions_are_permitted():
    legal = [
        (FaultState.NORMAL, FaultState.SUSPECTED),
        (FaultState.SUSPECTED, FaultState.CONFIRMED),
        (FaultState.CONFIRMED, FaultState.ACKNOWLEDGED),
        (FaultState.ACKNOWLEDGED, FaultState.UNDER_REPAIR),
        (FaultState.UNDER_REPAIR, FaultState.VERIFYING),
        (FaultState.VERIFYING, FaultState.CLOSED),
        (FaultState.VERIFYING, FaultState.UNDER_REPAIR),
    ]
    for current, target in legal:
        assert FaultLifecycle.can_transition(current, target) is True


def test_notified_is_not_a_fault_lifecycle_state():
    states = [s.value for s in FaultState]
    assert "NOTIFIED" not in states
    assert "ESCALATED" not in states
    assert states == [
        "NORMAL", "SUSPECTED", "CONFIRMED", "ACKNOWLEDGED",
        "UNDER_REPAIR", "VERIFYING", "CLOSED",
    ]


# --------------------------------------------------------------------------
# 30. notification state independent from fault lifecycle
# --------------------------------------------------------------------------
def test_notification_state_is_independent_of_fault_lifecycle(lamp_node, operator):
    """A fault stays CONFIRMED while notification state advances."""

    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED
    assert fault.notification_state in (
        NotificationState.PENDING,
        NotificationState.SENT,
        NotificationState.ACK_PENDING,
    )

    # Advance notification state only.
    advance_notification(fault, NotificationState.REMINDER_DUE)
    assert fault.state is FaultState.CONFIRMED
    assert fault.notification_state is NotificationState.REMINDER_DUE

    advance_notification(fault, NotificationState.ESCALATED)
    assert fault.state is FaultState.CONFIRMED
    assert fault.notification_state is NotificationState.ESCALATED


def test_reminder_and_escalation_do_not_change_fault_state(lamp_node, operator):
    from sslv1.enums import NotificationState as NS

    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    last_step = 1000 * 5
    fault = lamp_node.faults.active_faults[0]
    advance_notification(fault, NS.ACK_PENDING)

    interval = lamp_node.config.ack_reminder_interval_ticks
    escalation = lamp_node.config.escalation_timeout_ticks
    assert escalation > interval

    # Past the reminder interval but before the escalation timeout.
    action = lamp_node.notifications.tick(fault, ticks=last_step + interval + 1)
    assert action == "reminder_due"
    assert fault.state is FaultState.CONFIRMED

    # Past the escalation timeout.
    action = lamp_node.notifications.tick(fault, ticks=last_step + escalation + 1)
    assert action == "escalated"
    assert fault.state is FaultState.CONFIRMED
    assert fault.notification_state is NotificationState.ESCALATED


def test_notification_failure_is_retried_then_reported(lamp_node, operator):
    from sslv1.enums import NotificationState as NS

    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    advance_notification(fault, NS.ACK_PENDING)

    for _ in range(lamp_node.config.notification_retry_count + 1):
        lamp_node.notifications.delivery_failed(fault, ticks=5000)

    assert fault.notification_state is NotificationState.DELIVERY_FAILED
    assert any(
        e.event_type.value == "FAULT_NOTIFICATION_FAILED" for e in lamp_node.events
    )
    assert fault.state is FaultState.CONFIRMED


def test_not_required_when_ack_not_configured(clock, bus, authorizer, lamp_identity):
    from sslv1.nodes import LampNode

    config = make_lamp_config(lamp_identity.lamp_id, ack_required=False)
    node = LampNode(lamp_identity, config.bus_address, config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    for index in range(5):
        node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = node.faults.active_faults[0]
    assert fault.notification_state is NotificationState.NOT_REQUIRED


def test_illegal_notification_transition_is_rejected(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    fault = engine.active_faults[0]
    fault.notification_state = NotificationState.PENDING
    with pytest.raises(IllegalTransitionError):
        from sslv1.notification import NotificationLifecycle

        NotificationLifecycle.transition(fault, NotificationState.ESCALATED)


def test_recurring_condition_creates_a_new_linked_fault(engine):
    for index in range(3):
        engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=1000 * (index + 1))
    first = engine.active_faults[0]
    engine.acknowledge(first.fault_id, "operator-01", ticks=4000)
    engine.start_repair(first.fault_id, "engineer-01", ticks=5000)
    engine.report_repaired(first.fault_id, "engineer-01", ticks=6000)
    engine.verify(first.fault_id, "engineer-01", ticks=7000, verified=True)
    assert first.state is FaultState.CLOSED

    # The condition comes back: a new fault record is raised.
    engine.observe(SITE, GROUP, lamp(), open_load_result(), ticks=20_000)
    assert len(engine.faults) == 2
    assert engine.active_faults[0].fault_id != first.fault_id


# --------------------------------------------------------------------------
# failure containment
# --------------------------------------------------------------------------
def test_one_nodes_fault_does_not_affect_another_node(clock, bus, authorizer,
                                                      lamp_identity):
    from sslv1.identity import BusAddress, DeviceIdentity, Identifier
    from sslv1.nodes import LampNode

    second_identity = DeviceIdentity(
        product_id=lamp_identity.product_id,
        site_id=lamp_identity.site_id,
        group_id=lamp_identity.group_id,
        lamp_id=Identifier("LAMP-02"),
    )
    config_a = make_lamp_config(lamp_identity.lamp_id, bus_address=1)
    config_b = make_lamp_config(second_identity.lamp_id, bus_address=2)
    node_a = LampNode(lamp_identity, BusAddress(1), config_a, clock=clock, bus=bus,
                      authorizer=authorizer)
    node_b = LampNode(second_identity, BusAddress(2), config_b, clock=clock, bus=bus,
                      authorizer=authorizer)
    node_a.start()
    node_b.start()

    for index in range(5):
        node_a.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
        node_b.step(healthy_sources(), ticks=1000 * (index + 1))

    assert node_a.faults.active_faults
    assert node_b.faults.active_faults == ()
    assert node_b.control.lamp_is_on is True
    assert node_b.snapshot()["effective_mode"] == "AUTO_SENSOR"


# --------------------------------------------------------------------------
# fault -> event association is real, not just declared
# --------------------------------------------------------------------------
def test_fault_records_its_related_event_ids(lamp_node):
    """The association documented in 03_data_model.md section 5 is populated."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    assert fault.related_event_ids, "fault must reference its own events"

    recorded = {e.event_id for e in lamp_node.events}
    assert set(fault.related_event_ids).issubset(recorded)

    related = [e for e in lamp_node.events if e.related_fault_id == fault.fault_id]
    assert related
    assert {e.event_id for e in related} >= set(fault.related_event_ids)


def test_related_event_ids_are_not_duplicated(lamp_node):
    """Re-observing the same fault must not append the same event twice."""
    for index in range(8):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    assert len(fault.related_event_ids) == len(set(fault.related_event_ids))


# --------------------------------------------------------------------------
# notification tick() must never attempt an illegal transition
#
# Regression: a fault left unacknowledged past the reminder interval but
# before the escalation timeout made NotificationEngine.tick() re-enter
# REMINDER_DUE, which the state machine forbids. LampNode.step() calls tick()
# for every active confirmed fault on every cycle, so the run crashed with
# IllegalTransitionError. The suite passed because no test stepped far enough
# past the reminder interval without acknowledging or escalating.
# --------------------------------------------------------------------------
def test_notification_reminder_is_idempotent(lamp_node):
    """Stepping repeatedly inside the reminder window must not crash."""
    for index in range(6):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    assert fault.notification_state.value == "ACK_PENDING"

    # Cross the reminder interval, then keep stepping well inside the
    # escalation window. Every one of these used to raise.
    for ticks in range(40_000, 120_000, 5_000):
        lamp_node.step(healthy_sources(light_level=10.0), ticks=ticks)

    assert fault.notification_state.value == "REMINDER_DUE"
    assert lamp_node.control.lamp_is_on is True
    assert fault.state.value == "CONFIRMED"


def test_notification_reminder_does_not_spam_events(lamp_node):
    """A repeated reminder window must not emit a reminder per tick."""
    for index in range(6):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    assert lamp_node.faults.active_faults, "expected an active fault"
    for ticks in range(40_000, 120_000, 5_000):
        lamp_node.step(healthy_sources(light_level=10.0), ticks=ticks)

    reminders = [
        e for e in lamp_node.events
        if e.event_type.value == "FAULT_REMINDER_DUE"
    ]
    assert len(reminders) == 1, "reminder emitted %d times" % len(reminders)


def test_notification_escalates_after_timeout_without_crash(lamp_node):
    """A long unacknowledged run must escalate, not crash."""
    for index in range(6):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    for ticks in range(20_000, 400_000, 10_000):
        lamp_node.step(healthy_sources(light_level=10.0), ticks=ticks)

    assert fault.notification_state.value == "ESCALATED"
    assert fault.state.value == "CONFIRMED"
    assert lamp_node.control.lamp_is_on is True


def test_notification_tick_is_legal_from_every_resting_state(lamp_node):
    """tick() must never raise for any state the engine can rest in."""
    from sslv1.enums import NotificationState
    from sslv1.notification import NotificationEngine

    for index in range(6):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]

    for resting in NotificationState:
        if resting is NotificationState.NOT_REQUIRED:
            continue
        engine = NotificationEngine(lamp_node.config)
        fault.notification_state = resting
        for elapsed in (0, 1, 30_000, 120_000, 500_000):
            engine._last_notified[fault.fault_id] = 0
            engine.tick(fault, ticks=elapsed)  # must not raise
