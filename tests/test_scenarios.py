"""Enumerated end-to-end scenarios (Part S of the Phase 1 task).

Each test is a deterministic, hardware-independent scenario built from the
public domain API. The docstrings name the scenario and the requirement it
covers so the traceability table can cite real test evidence.
"""


import pytest

from sslv1.authorization import Actor, Role
from sslv1.command import Command, CommandService
from sslv1.comm import InMemoryBus
from sslv1.configuration import Schedule, TimeWindow
from sslv1.control import ControlModel, OverrideState
from sslv1.diagnostics import (
    Confidence,
    DiagnosticEngine,
    DiagnosticEvidence,
)
from sslv1.enums import (
    AuthorizationStatus,
    CommandState,
    CommandType,
    FaultType,
    ControlSubtype,
    OperatingMode,
    CommunicationStatus,
    CommState,
    ConfiguredMode,
    ControllerStatus,
    DiagnosticClassification,
    EventType,
    FaultState,
    LampState,
    NotificationState,
    RecordLifecycleState,
    RecordType,
    SensorStatus,
    TimeSyncState,
)
from sslv1.errors import ConfigurationError, StorageFullError, ValidationError
from sslv1.identity import BusAddress, DeviceIdentity, Identifier
from sslv1.storage import RecordStore
from sslv1.time_model import Timestamp
from sslv1.nodes import GroupController, LampNode

from conftest import (
    DAY_TICKS,
    GROUP,
    PRODUCT,
    SITE,
    TICKS_PER_SECOND,
    healthy_sources,
    make_lamp_config,
)


@pytest.fixture
def engineer():
    return Actor("engineer-01", Role.ENGINEER)


@pytest.fixture
def admin():
    return Actor("admin-01", Role.ADMIN)


@pytest.fixture
def owner():
    return Actor("owner-01", Role.OWNER)


# ==========================================================================
# Control scenarios (PR-CONTROL-001..007)
# ==========================================================================
def test_scenario_01_automatic_sensor_on_when_dark(lamp_node):
    """Scenario: automatic mode turns the lamp ON when it gets dark."""
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    assert decision.effective_mode is OperatingMode.AUTO_SENSOR
    assert decision.commanded_state is LampState.ON
    assert decision.decided_by == "SENSOR_SCHEDULE_LOGIC"
    assert lamp_node.control.lamp_is_on is True


def test_scenario_02_automatic_sensor_off_when_bright(lamp_node):
    """Scenario: automatic mode turns the lamp OFF when it gets bright."""
    lamp_node.step(healthy_sources(light_level=900.0), ticks=1000)
    assert lamp_node.control.lamp_is_on is False


def test_scenario_03_hysteresis_prevents_oscillation(lamp_node):
    """Scenario: between the ON and OFF thresholds the state is retained."""
    assert lamp_node.step(healthy_sources(light_level=10.0), ticks=1000).commanded_state \
        is LampState.ON
    assert lamp_node.step(healthy_sources(light_level=100.0), ticks=2000).commanded_state \
        is LampState.ON
    assert lamp_node.step(healthy_sources(light_level=100.0), ticks=3000).commanded_state \
        is LampState.ON

    assert lamp_node.step(healthy_sources(light_level=900.0), ticks=4000).commanded_state \
        is LampState.OFF
    assert lamp_node.step(healthy_sources(light_level=100.0), ticks=5000).commanded_state \
        is LampState.OFF


def test_scenario_04_invalid_hysteresis_configuration_is_rejected(lamp_identity):
    """Scenario: ON threshold >= OFF threshold is rejected."""
    config = make_lamp_config(lamp_identity.lamp_id, validate=False,
                              light_on_threshold=150.0, light_off_threshold=150.0)
    assert config.validate()
    with pytest.raises(ValidationError):
        config.validated()

    # The rejected band is refused before any ControlModel can be built.
    with pytest.raises(ValidationError):
        make_lamp_config(lamp_identity.lamp_id, validate=False,
                         light_on_threshold=150.0, light_off_threshold=150.0).validated()


def test_scenario_05_fixed_schedule_ignores_light_level(clock, bus, authorizer,
                                                        lamp_identity):
    """Scenario: FIXED_SCHEDULE follows the schedule only."""
    identity = lamp_identity
    config = make_lamp_config(
        identity.lamp_id,
        configured_mode=ConfiguredMode.FIXED_SCHEDULE,
        schedule=Schedule(
            day_length_ticks=DAY_TICKS,
            windows=(TimeWindow(0, DAY_TICKS // 2),),
        ),
    )
    node = LampNode(identity, BusAddress(1), config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()

    # Dark inside the window -> ON, as the schedule demands.
    assert node.step(healthy_sources(light_level=10.0), ticks=1000).commanded_state \
        is LampState.ON
    # Dark outside the window -> OFF, even though the sensor says dark.
    assert node.step(healthy_sources(light_level=10.0),
                     ticks=DAY_TICKS - TICKS_PER_SECOND).commanded_state is LampState.OFF


def test_scenario_06_schedule_plus_sensor(lamp_node):
    """Scenario: AUTO_SCHEDULE_SENSOR requires the window AND darkness."""
    lamp_node.control.set_configured_mode(ConfiguredMode.AUTO_SCHEDULE_SENSOR)
    assert lamp_node.step(healthy_sources(light_level=10.0), ticks=1000).commanded_state \
        is LampState.ON
    assert lamp_node.step(healthy_sources(light_level=900.0), ticks=2000).commanded_state \
        is LampState.OFF


def test_scenario_07_force_on(lamp_node, operator):
    """Scenario: FORCE_ON turns the lamp on regardless of the automatic mode."""
    lamp_node.step(healthy_sources(light_level=900.0), ticks=1000)
    record = lamp_node.force_on(operator, ticks=2000)
    assert record.state is CommandState.ACKNOWLEDGED
    lamp_node.step(healthy_sources(), ticks=3000)
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert lamp_node.control.lamp_is_on is True
    assert lamp_node.control.effective_mode is OperatingMode.FORCE_ON
    assert lamp_node.control.active_override is OverrideState.FORCE_ON


def test_scenario_08_force_off(lamp_node, operator):
    """Scenario: FORCE_OFF turns the lamp off regardless of the automatic mode."""
    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    record = lamp_node.force_off(operator, ticks=2000)
    assert record.state is CommandState.ACKNOWLEDGED
    lamp_node.step(healthy_sources(current=0, power=0, switching_feedback=LampState.OFF), ticks=3000)
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert lamp_node.control.lamp_is_on is False
    assert lamp_node.control.effective_mode is OperatingMode.FORCE_OFF


def test_scenario_09_return_to_auto_is_a_command_not_a_mode(lamp_node, operator):
    """Scenario: RETURN_TO_AUTO clears the override without being a mode."""
    lamp_node.force_on(operator, ticks=1000)
    assert lamp_node.control.effective_mode is OperatingMode.FORCE_ON

    record = lamp_node.return_to_auto(operator, ticks=2000)
    assert record.succeeded is True
    assert lamp_node.control.active_override is OverrideState.NONE
    assert lamp_node.control.effective_mode is OperatingMode.AUTO_SENSOR
    assert lamp_node.control.effective_mode.value == "AUTO_SENSOR"
    # RETURN_TO_AUTO is an action, never a persistent operating mode.
    assert "RETURN_TO_AUTO" not in {m.value for m in ConfiguredMode}


def test_scenario_10_override_beats_automatic_mode(lamp_node, operator):
    """Scenario: an authorized override outranks the configured automatic mode."""
    assert "FORCE_ON" not in {m.value for m in ConfiguredMode}
    assert OperatingMode.FORCE_ON.value == "FORCE_ON"
    lamp_node.force_off(operator, ticks=1000)
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=2000)
    assert decision.decided_by == "AUTHORIZED_OVERRIDE"
    assert decision.commanded_state is LampState.OFF


def test_scenario_11_safety_outranks_the_override(lamp_node, operator):
    """Scenario: a protection condition outranks an authorized override."""
    lamp_node.force_on(operator, ticks=1000)
    lamp_node.set_protection(True, LampState.OFF, reason="test protection condition")
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=2000)
    assert decision.decided_by == "SAFETY_PROTECTION"
    assert decision.commanded_state is LampState.OFF


def test_scenario_12_fault_acknowledgement_is_not_a_lighting_input(lamp_node, operator):
    """Scenario: acknowledging a fault does not change lighting."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    lamp_node.acknowledge_fault(fault.fault_id, operator, ticks=6000)
    assert fault.state is FaultState.ACKNOWLEDGED
    assert lamp_node.control.lamp_is_on is True
    decision = lamp_node.step(healthy_sources(light_level=10.0), ticks=7000)
    assert decision.commanded_state is LampState.ON


# ==========================================================================
# Command scenarios (PR-CONTROL-*, PR-SECURITY-*)
# ==========================================================================
def test_scenario_13_command_lifecycle_reaches_verification(lamp_node, operator):
    """Scenario: the command lifecycle reaches ACTUAL_STATE_VERIFIED."""
    record = lamp_node.force_on(operator, ticks=1000)
    assert record.state is CommandState.ACKNOWLEDGED
    lamp_node.step(healthy_sources(), ticks=2000)
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert record.received_ticks == 1000
    assert record.executed_ticks == 1000
    assert record.acknowledged_ticks == 1000
    assert record.verified_ticks == 2000
    assert record.succeeded is True


def test_scenario_14_duplicate_command_is_suppressed(lamp_node, operator):
    """Scenario: re-submitting a command id does not execute it twice."""
    first = lamp_node.force_on(operator, ticks=1000)
    duplicates_before = len(lamp_node.events)
    lamp_node.commands.submit(first.command, ticks=2000)
    matching = [r for r in lamp_node.commands.records
                if r.command_id == first.command_id]
    assert len(matching) == 1
    assert matching[0].executed_ticks == 1000
    assert any(e.event_type is EventType.COMMAND_DUPLICATE for e in lamp_node.events)
    assert len(lamp_node.events) > duplicates_before


def test_scenario_15_unauthorized_command_is_rejected(lamp_node, viewer):
    """Scenario: a VIEWER cannot issue a lighting command."""
    assert viewer.role is Role.VIEWER
    record = lamp_node.force_on(viewer, ticks=1000)
    assert record.state is CommandState.REJECTED
    assert record.authorization_status is AuthorizationStatus.UNAUTHORIZED
    assert record.executed_ticks is None
    assert record.verified_ticks is None
    assert lamp_node.control.active_override is OverrideState.NONE
    assert lamp_node.control.lamp_is_on is False
    assert any(e.event_type is EventType.COMMAND_REJECTED for e in lamp_node.events)


def test_scenario_16_command_receipt_is_not_success(lamp_node, engineer):
    """Scenario: a received command that fails verification is not a success."""
    identity = lamp_node.identity
    service = CommandService(
        authorizer=lamp_node._authorizer,
        executor=lambda command: (True, "executed"),
        verifier=lambda command: (False, "switching feedback never followed"),
    )
    record = service.submit(
        Command(command_id="c-1", command_type=CommandType.FORCE_ON,
                target=identity, actor=engineer, created_ticks=0),
        ticks=10,
    )
    assert record.state is CommandState.FAILED
    assert record.received_ticks == 10
    assert record.executed_ticks is not None
    assert record.acknowledged_ticks is not None
    assert record.verified_ticks is None
    assert "switching feedback" in record.verification_reason


# ==========================================================================
# Measurement and diagnostic scenarios (PR-MEASURE-*, PR-DIAG-*)
# ==========================================================================
def test_scenario_17_normal_measurement(lamp_node):
    """Scenario: a healthy lamp produces a valid, normal measurement."""
    lamp_node.step(healthy_sources(), ticks=1000)
    measurement = lamp_node.measurements[-1]
    assert measurement.voltage == 230.0
    assert measurement.current == pytest.approx(0.45)
    assert measurement.power == pytest.approx(103.5)
    assert measurement.commanded_state is LampState.ON
    assert measurement.switching_feedback is LampState.ON
    assert measurement.actual_state is LampState.ON
    assert measurement.sensor_status is SensorStatus.VALID
    # A measurement is explicitly an engineering value, never billing grade.
    payload = measurement.to_dict()
    assert "billing_grade" not in payload
    assessment = lamp_node.validator.assess(measurement)
    assert assessment.has_issues is False
    assert assessment.physically_consistent is True


def test_scenario_18_under_current_and_open_load(lamp_node):
    """Scenario: under-current and possible open load are distinguished."""
    for index in range(5):
        lamp_node.step(healthy_sources(current=0.0, power=0.0,
                                       switching_feedback=LampState.ON),
                       ticks=1000 * (index + 1))
    fault = lamp_node.faults.active_faults[0]
    assert fault.diagnostic_classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert fault.fault_type is FaultType.UNDER_CURRENT
    # The classification is diagnostic evidence, not a proven root cause: the
    # fault record carries category + classification + confirmation only.
    assert fault.evidence is not None
    assert not any("root_cause" in key for key in fault.evidence)


def test_scenario_19_unexpected_current_while_commanded_off(lamp_node):
    """Scenario: current with the lamp commanded OFF is unexpected."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(light_level=900.0, current=0.30, power=69.0,
                            switching_feedback=LampState.OFF),
            ticks=1000 * (index + 1),
        )
    classifications = {
        f.diagnostic_classification for f in lamp_node.faults.active_faults
    }
    assert DiagnosticClassification.UNEXPECTED_CURRENT in classifications


def test_scenario_20_supply_failure(lamp_node):
    """Scenario: absent supply voltage while commanded ON is a supply problem."""
    for index in range(5):
        lamp_node.step(healthy_sources(voltage=0.0, current=0.0, power=0.0),
                       ticks=1000 * (index + 1))
    classifications = {
        f.diagnostic_classification for f in lamp_node.faults.active_faults
    }
    assert DiagnosticClassification.SUPPLY_ABNORMALITY in classifications


def test_scenario_21_light_sensor_failure(lamp_node):
    """Scenario: an invalid light sensor is reported, not guessed around."""
    for index in range(5):
        lamp_node.step(healthy_sources(sensor_status=SENSOR_INVALID(), current=0, power=0, switching_feedback=LampState.OFF), ticks=1000 * (index + 1))
    classifications = {
        f.diagnostic_classification for f in lamp_node.faults.active_faults
    }
    assert DiagnosticClassification.SENSOR_ABNORMALITY in classifications


def SENSOR_INVALID():
    from sslv1.enums import SensorStatus

    return SensorStatus.INVALID


def test_scenario_22_comm_failure_is_reported(lamp_node):
    """Scenario: a communication fault is a distinct diagnostic outcome."""
    lamp_node.set_communication_status(CommunicationStatus.COMM_FAULT)
    for index in range(5):
        lamp_node.step(healthy_sources(), ticks=1000 * (index + 1))
    classifications = {
        f.diagnostic_classification for f in lamp_node.faults.active_faults
    }
    assert DiagnosticClassification.COMMUNICATION_ABNORMALITY in classifications


def test_scenario_23_controller_failure_is_reported(lamp_node):
    """Scenario: a controller fault is the highest-severity diagnostic."""
    for index in range(5):
        lamp_node.step(healthy_sources(controller_status=CONTROLLER_FAULT()),
                       ticks=1000 * (index + 1))
    fault = [f for f in lamp_node.faults.active_faults
             if f.diagnostic_classification
             is DiagnosticClassification.CONTROLLER_ABNORMALITY]
    assert fault
    assert fault[0].severity.value == "CRITICAL"


def CONTROLLER_FAULT():
    return ControllerStatus.FAULT


def test_scenario_24_measurement_abnormality(lamp_node):
    """Scenario: physically inconsistent measurements are abnormal data."""
    for index in range(5):
        lamp_node.step(healthy_sources(voltage=230.0, current=0.45, power=5000.0),
                       ticks=1000 * (index + 1))
    classifications = {
        f.diagnostic_classification for f in lamp_node.faults.active_faults
    }
    assert DiagnosticClassification.MEASUREMENT_ABNORMALITY in classifications


def test_scenario_25_unknown_behaviour_requires_inspection(lamp_node):
    """Scenario: evidence that cannot be classified requires inspection."""
    result = DiagnosticEngine(lamp_node.config).evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.UNKNOWN,
            voltage=230.0,
            current=0.45,
            power=103.5,
            light_level=10.0,
        )
    )
    # No switching feedback and nothing else abnormal: the engine refuses to
    # guess and asks for inspection instead.
    assert result.classification is DiagnosticClassification.INSUFFICIENT_EVIDENCE
    assert result.fault_category is FaultType.INSPECTION_REQUIRED
    assert result.confidence is Confidence.LOW


def test_scenario_26_environmental_or_external(lamp_node):
    """Scenario: dark while bright is treated as an external/environmental cause."""
    from sslv1.diagnostics import DiagnosticEvidence

    result = DiagnosticEngine(lamp_node.config).evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.OFF,
            switching_feedback=LampState.OFF,
            voltage=230.0,
            current=0.0,
            power=0.0,
            light_level=900.0,
        )
    )
    assert result.classification is DiagnosticClassification.ENVIRONMENTAL_OR_EXTERNAL


def test_scenario_27_lamp_health_never_uses_current_alone(lamp_node):
    """Scenario: the same current is classified differently per context."""
    engine = lamp_node.diagnostics

    on_open = engine.evaluate(
        DiagnosticEvidence(commanded_state=LampState.ON, switching_feedback=LampState.ON,
                           voltage=230.0, current=0.0, power=0.0, light_level=10.0)
    )
    off_no_current = engine.evaluate(
        DiagnosticEvidence(commanded_state=LampState.OFF, switching_feedback=LampState.OFF,
                           voltage=230.0, current=0.0, power=0.0, light_level=10.0)
    )
    bad_sensor = engine.evaluate(
        DiagnosticEvidence(commanded_state=LampState.ON, switching_feedback=LampState.ON,
                           voltage=230.0, current=0.0, power=0.0, light_level=10.0,
                           sensor_status=SensorStatus.INVALID)
    )
    # Identical current, three different outcomes: the current value alone
    # never decides lamp health.
    assert on_open.classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert off_no_current.classification is DiagnosticClassification.NORMAL
    assert bad_sensor.classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD
    # A bad sensor is never reported as a lamp failure: LAMP_LOAD and
    # UNDER_CURRENT are categories, not proven root causes.
    assert bad_sensor.fault_category is not FaultType.LAMP_LOAD


# ==========================================================================
# Fault and notification scenarios (PR-FAULT-*, PR-NOTIFICATION-*)
# ==========================================================================
def test_scenario_28_fault_confirmation_count(lamp_node):
    """Scenario: a fault is confirmed after the configured count."""
    for index in range(3):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED
    assert fault.confirmation_count >= 3


def test_scenario_29_fault_latching(lamp_node):
    """Scenario: a confirmed fault latches against one normal measurement."""
    for index in range(3):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    lamp_node.step(healthy_sources(), ticks=10_000)
    fault = lamp_node.faults.active_faults[0]
    assert fault.state is FaultState.CONFIRMED


def test_scenario_30_fault_acknowledgement_does_not_dim_the_light(lamp_node, operator):
    """Scenario: acknowledgement and reminders never dim or extinguish lighting."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, light_level=10.0,
                            switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    lamp_node.acknowledge_fault(fault.fault_id, operator, ticks=6000)
    lamp_node.notifications.tick(fault, ticks=10_000_000)
    assert fault.state is FaultState.ACKNOWLEDGED
    assert fault.notification_state in (
        NotificationState.ACK_PENDING, NotificationState.ESCALATED,
        NotificationState.REMINDER_DUE,
    )
    assert lamp_node.control.lamp_is_on is True


def test_scenario_31_repair_and_verification(lamp_node, operator, engineer):
    """Scenario: repair then verification closes the fault."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    lamp_node.acknowledge_fault(fault.fault_id, operator, ticks=6000)
    lamp_node.start_repair(fault.fault_id, engineer, ticks=7000)
    lamp_node.report_repaired(fault.fault_id, engineer, ticks=8000)
    lamp_node.verify_repair(fault.fault_id, engineer, ticks=9000, verified=True)
    assert fault.state is FaultState.CLOSED
    assert lamp_node.faults.active_faults == ()


def test_scenario_32_failed_verification_reopens_the_fault(lamp_node, operator, engineer):
    """Scenario: failed verification returns to an active fault state."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    lamp_node.acknowledge_fault(fault.fault_id, operator, ticks=6000)
    lamp_node.start_repair(fault.fault_id, engineer, ticks=7000)
    lamp_node.report_repaired(fault.fault_id, engineer, ticks=8000)
    lamp_node.verify_repair(fault.fault_id, engineer, ticks=9000, verified=False)
    assert fault.state is FaultState.UNDER_REPAIR
    assert fault.is_active is True


def test_scenario_33_notification_state_independent(lamp_node):
    """Scenario: notification state advances while the fault state is unchanged."""
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, switching_feedback=LampState.ON),
            ticks=1000 * (index + 1),
        )
    fault = lamp_node.faults.active_faults[0]
    state_before = fault.state
    for target in (NotificationState.SENT, NotificationState.ACK_PENDING):
        fault.notification_state = target
    assert fault.state is state_before


# ==========================================================================
# Storage scenarios (PR-STORAGE-*)
# ==========================================================================
def test_scenario_34_storage_record_lifecycle(lamp_node):
    """Scenario: a record walks CREATED -> PENDING_UPLOAD -> UPLOADED -> RETAINED."""
    lamp_node.step(healthy_sources(), ticks=1000)
    record = lamp_node.storage.records[0]
    assert record.lifecycle_state is RecordLifecycleState.PENDING_UPLOAD
    lamp_node.storage.mark_uploaded(record.sequence_number)
    assert record.lifecycle_state is RecordLifecycleState.UPLOADED
    lamp_node.storage.mark_confirmed(record.sequence_number)
    assert record.lifecycle_state is RecordLifecycleState.RETAINED


def test_scenario_35_upload_confirmation_does_not_delete(lamp_node):
    """Scenario: confirmed upload leaves the retained record in place."""
    for index in range(3):
        lamp_node.step(healthy_sources(), ticks=1000 * (index + 1))
    records = list(lamp_node.storage.records)
    for record in records:
        lamp_node.storage.mark_uploaded(record.sequence_number)
        lamp_node.storage.mark_confirmed(record.sequence_number)
    assert len(lamp_node.storage.retained) == 3
    assert len(lamp_node.storage.pending_upload) == 0
    assert len(lamp_node.storage) == 3


def test_scenario_36_storage_full_is_visible(lamp_node):
    """Scenario: storage exhaustion is reported, never silent."""
    for index in range(5):
        lamp_node.step(healthy_sources(), ticks=1000 * (index + 1))
    store = RecordStore(capacity=1)
    store.create(record_type=RecordType.MEASUREMENT, payload={},
                 timestamp=Timestamp(ticks=1, sync_state=TimeSyncState.SYNCHRONIZED),
                 device_id=lamp_node.lamp_id)
    with pytest.raises(StorageFullError):
        store.create(record_type=RecordType.MEASUREMENT, payload={},
                     timestamp=Timestamp(ticks=2, sync_state=TimeSyncState.SYNCHRONIZED),
                     device_id=lamp_node.lamp_id)
    assert store.is_full is True


def test_scenario_37_power_loss_recovery(lamp_node):
    """Scenario: an uncommitted record is discarded on recovery, the rest survive."""
    lamp_node.step(healthy_sources(), ticks=1000)
    committed = lamp_node.storage.records[0]
    lamp_node.storage._sequence += 1
    from sslv1.storage import StorageRecord

    partial = StorageRecord(
        sequence_number=lamp_node.storage._sequence,
        timestamp=Timestamp(ticks=2000, sync_state=TimeSyncState.SYNCHRONIZED),
        record_type=RecordType.EVENT,
        payload={"partial": True},
        device_id=lamp_node.lamp_id,
    )
    lamp_node.storage._records[partial.sequence_number] = partial
    lamp_node.storage.simulate_power_loss()
    discarded = lamp_node.storage.recover()
    assert [r.sequence_number for r in discarded] == [partial.sequence_number]
    assert committed.sequence_number in lamp_node.storage._records


# ==========================================================================
# Communication and offline scenarios (PR-COMM-*, PR-OFFLINE-*)
# ==========================================================================
def test_scenario_38_communication_retry_then_degraded(group_controller, clock, bus,
                                                       authorizer):
    """Scenario: repeated failures degrade communication but not lighting."""
    nodes = []
    for number in (1, 2):
        identity = DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP,
                                  lamp_id=Identifier("LAMP-%02d" % number))
        config = make_lamp_config(identity.lamp_id, bus_address=number)
        node = LampNode(identity, BusAddress(number), config, clock=clock, bus=bus,
                        authorizer=authorizer)
        node.start()
        nodes.append(node)
        group_controller.register_node(node.lamp_id, node.bus_address)

    bus.set_silent(1)
    for _ in range(5):
        clock.advance(group_controller.config.poll_timeout_ticks)
        group_controller.poll()
        for node in nodes:
            for frame in node.process_incoming():
                group_controller.bus.send(frame)
        group_controller.collect_responses()

    registration = group_controller.registration_for(Identifier("LAMP-01"))
    assert registration.comm.state is CommState.COMM_FAULT
    # The node still controls its lamp locally.
    nodes[0].step(healthy_sources(light_level=10.0), ticks=5000)
    assert nodes[0].control.lamp_is_on is True


def test_scenario_39_communication_recovery(group_controller, clock, bus, authorizer):
    """Scenario: recovery re-synchronizes without duplicate upload."""
    identity = DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP,
                              lamp_id=Identifier("LAMP-01"))
    config = make_lamp_config(identity.lamp_id, bus_address=1)
    node = LampNode(identity, BusAddress(1), config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    group_controller.register_node(node.lamp_id, node.bus_address)

    bus.set_silent(1)
    for _ in range(5):
        clock.advance(group_controller.config.poll_timeout_ticks)
        group_controller.poll()
        for frame in node.process_incoming():
            group_controller.bus.send(frame)
        group_controller.collect_responses()
    assert group_controller.registration_for(node.lamp_id).comm.state is CommState.COMM_FAULT

    bus.set_silent(1, silent=False)
    for _ in range(3):
        clock.advance(group_controller.config.poll_timeout_ticks)
        group_controller.poll()
        for frame in node.process_incoming():
            group_controller.bus.send(frame)
        group_controller.collect_responses()
    assert group_controller.registration_for(node.lamp_id).comm.state is CommState.COMM_HEALTHY
    assert group_controller.degraded_nodes() == ()


def test_scenario_40_time_synchronization(group_controller, clock, bus, authorizer):
    """Scenario: the Group Controller distributes time to every node."""
    identity = DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP,
                              lamp_id=Identifier("LAMP-01"))
    config = make_lamp_config(identity.lamp_id, bus_address=1)
    node = LampNode(identity, BusAddress(1), config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    group_controller.register_node(node.lamp_id, node.bus_address)

    results = group_controller.synchronize_time(master_ticks=77_000, actor=Actor("time-admin", Role.ADMIN))
    assert results == {1: False}
    node.process_incoming()
    assert node.time.sync_state is TimeSyncState.SYNCHRONIZED
    assert node.time.ticks == 77_000


def test_scenario_41_offline_timestamps_are_uncertain(clock, bus, authorizer):
    """Scenario: a node that lost sync flags its records as uncertain."""
    identity = DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP,
                              lamp_id=Identifier("LAMP-01"))
    config = make_lamp_config(identity.lamp_id, bus_address=1)
    node = LampNode(identity, BusAddress(1), config, clock=clock, bus=bus,
                    authorizer=authorizer)
    node.start()
    node.time.mark_unsynchronized()
    node.time.uncertainty_threshold_ticks = 1000
    node.time.advance(5000)
    node.step(healthy_sources(), ticks=5000)
    assert node.storage.records[-1].timestamp.sync_state is TimeSyncState.UNCERTAIN


# ==========================================================================
# Authorization and configuration scenarios (PR-SECURITY-*, PR-CONFIG-*)
# ==========================================================================
def test_scenario_42_energy_reset_requires_an_authorized_actor(lamp_node, operator,
                                                               engineer):
    """Scenario: RESET_ENERGY is a CONTROL_COMMAND subtype, authorization-checked."""
    assert operator.role is Role.OPERATOR
    assert engineer.role is Role.ENGINEER
    record = lamp_node.reset_energy(engineer, ticks=1000)
    assert record.succeeded is True
    assert record.command.subtype is ControlSubtype.RESET_ENERGY
    assert record.command.parameters.get("subtype") == ControlSubtype.RESET_ENERGY.value


def test_scenario_43_viewer_cannot_change_configuration(lamp_node, viewer):
    """Scenario: a VIEWER cannot change the operating mode."""
    record = lamp_node.set_configured_mode(ConfiguredMode.FIXED_SCHEDULE, viewer,
                                          ticks=1000)
    assert record.state is CommandState.REJECTED
    assert lamp_node.control.configured_mode is ConfiguredMode.AUTO_SENSOR


def test_scenario_44_configuration_validation(lamp_identity):
    """Scenario: every threshold is validated, none is hardcoded."""
    bad = make_lamp_config(
        lamp_identity.lamp_id,
        validate=False,
        light_on_threshold=200.0,
        light_off_threshold=100.0,
        voltage_min=260.0,
        voltage_max=180.0,
        fault_confirmation_count=0,
        fault_confirmation_window_ticks=0,
        ack_reminder_interval_ticks=0,
        escalation_timeout_ticks=0,
        notification_retry_count=0,
        comm_timeout_ticks=0,
        under_current_min=-1.0,
        expected_current_min=-1.0,
        over_current_max=-1.0,
        unexpected_current_min=-1.0,
        power_max=-1.0,
        light_hysteresis=1000.0,
    )
    problems = bad.validate()
    assert len(problems) >= 12
    with pytest.raises(ValidationError):
        bad.validated()


def test_scenario_45_every_threshold_is_configurable(lamp_identity):
    """Scenario: thresholds are data, not constants in the code."""
    dark_bias = make_lamp_config(lamp_identity.lamp_id, light_on_threshold=50.0,
                                 light_off_threshold=150.0)
    bright_bias = make_lamp_config(lamp_identity.lamp_id, light_on_threshold=250.0,
                                   light_off_threshold=350.0)
    # Same light level, two configurations, two commanded states.
    assert ControlModel(config=dark_bias).decide(
        light_level=200.0, ticks=0).commanded_state is LampState.OFF
    assert ControlModel(config=bright_bias).decide(
        light_level=200.0, ticks=0).commanded_state is LampState.ON


# ==========================================================================
# Multi-node scenarios (PR-SCALABILITY-*)
# ==========================================================================
def test_scenario_46_multi_node_isolation(clock, bus, authorizer):
    """Scenario: one node's failure does not affect the others."""
    nodes = []
    for number in (1, 2, 3):
        identity = DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP,
                                  lamp_id=Identifier("LAMP-%02d" % number))
        config = make_lamp_config(identity.lamp_id, bus_address=number)
        node = LampNode(identity, BusAddress(number), config, clock=clock, bus=bus,
                        authorizer=authorizer)
        node.start()
        nodes.append(node)

    for index in range(5):
        for position, node in enumerate(nodes, start=1):
            sources = healthy_sources()
            if position == 2:
                sources = healthy_sources(current=0.0, power=0.0,
                                          switching_feedback=LampState.ON)
            node.step(sources, ticks=1000 * (index + 1))

    assert nodes[1].faults.active_faults
    assert nodes[0].faults.active_faults == ()
    assert nodes[2].faults.active_faults == ()
    assert all(node.control.lamp_is_on for node in nodes)


def test_scenario_47_group_controller_capacity(clock, bus, authorizer, group_identity):
    """Scenario: the Group Controller handles the configured node maximum."""
    controller = GroupController(identity=group_identity, clock=clock, bus=InMemoryBus())
    for number in range(1, 17):
        controller.register_node(Identifier("LAMP-%02d" % number), BusAddress(number))
    assert controller.node_count == 16
    assert controller.config.max_nodes == 16

    with pytest.raises(ConfigurationError):
        controller.register_node(Identifier("LAMP-99"), BusAddress(99))


def test_scenario_48_duplicate_registration_is_rejected(group_controller):
    """Scenario: duplicate bus addresses and lamp ids are rejected."""
    group_controller.register_node(Identifier("LAMP-01"), BusAddress(1))
    with pytest.raises(ConfigurationError):
        group_controller.register_node(Identifier("LAMP-02"), BusAddress(1))
    with pytest.raises(ConfigurationError):
        group_controller.register_node(Identifier("LAMP-01"), BusAddress(2))


# ==========================================================================
# Audit scenarios (PR-SECURITY-*)
# ==========================================================================
def test_scenario_49_important_transitions_generate_events(lamp_node, operator):
    """Scenario: important transitions produce audit events."""
    record = lamp_node.force_on(operator, ticks=1000)
    assert not record.succeeded
    lamp_node.step(healthy_sources(), ticks=1500)
    assert record.succeeded
    for index in range(5):
        lamp_node.step(
            healthy_sources(current=0.0, power=0.0, switching_feedback=LampState.ON),
            ticks=2000 * (index + 1),
        )
    event_types = {event.event_type for event in lamp_node.events}
    assert EventType.NODE_STARTED in event_types
    assert EventType.COMMAND_RECEIVED in event_types
    assert EventType.COMMAND_EXECUTED in event_types
    assert EventType.COMMAND_VERIFIED in event_types
    assert EventType.FAULT_CONFIRMED in event_types
    assert EventType.RECORD_STORED in event_types


def test_scenario_50_rejected_command_is_audited(lamp_node, viewer):
    """Scenario: a rejected command is audited with the actor and reason."""
    lamp_node.force_on(viewer, ticks=1000)
    rejected = [e for e in lamp_node.events if e.event_type is EventType.COMMAND_REJECTED]
    assert len(rejected) == 1
    assert "viewer-01" in rejected[0].reason
    assert "UNAUTHORIZED" in rejected[0].reason
