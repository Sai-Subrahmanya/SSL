"""Diagnostic engine tests (PR-DIAG-*).

Covers all ten required diagnostic cases plus edge cases.
"""


import pytest

from sslv1.diagnostics import (
    Confidence,
    DiagnosticEngine,
    DiagnosticEvidence,
    evidence_from_measurement,
)
from sslv1.enums import (
    CommunicationStatus,
    ControllerStatus,
    DiagnosticClassification,
    FaultType,
    LampState,
    SensorStatus,
)


from conftest import make_lamp_config


@pytest.fixture
def config(lamp_identity):
    return make_lamp_config(lamp_identity.lamp_id)


@pytest.fixture
def engine(config):
    return DiagnosticEngine(config)


# --------------------------------------------------------------------------
# 1. NORMAL ON
# --------------------------------------------------------------------------
def test_normal_on_operation(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            light_level=10.0,
            sensor_status=SensorStatus.VALID,
        )
    )
    assert result.classification is DiagnosticClassification.NORMAL
    assert result.fault_category is None
    assert result.is_normal is True
    assert result.confidence is Confidence.HIGH


# --------------------------------------------------------------------------
# 2. POSSIBLE OPEN LOAD / UNDER-CURRENT
# --------------------------------------------------------------------------
def test_possible_open_load(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.0,
            power=0.0,
            light_level=10.0,
        )
    )
    assert result.classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert result.fault_category is FaultType.UNDER_CURRENT
    assert result.confidence is Confidence.HIGH
    assert result.requires_attention is True


def test_open_load_is_not_claimed_as_a_lamp_failure(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.01,
            power=0.0,
        )
    )
    # The classification is a possibility, never a confirmed root cause.
    assert "POSSIBLE" in result.classification.value
    assert "lamp failed" not in result.reason.lower()


# --------------------------------------------------------------------------
# 3. UNEXPECTED CURRENT
# --------------------------------------------------------------------------
def test_unexpected_current_while_commanded_off(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.OFF,
            switching_feedback=LampState.OFF,
            voltage=230.0,
            current=0.60,
            power=138.0,
        )
    )
    assert result.classification is DiagnosticClassification.UNEXPECTED_CURRENT
    assert result.fault_category is FaultType.LAMP_LOAD


# --------------------------------------------------------------------------
# 4. SUPPLY PROBLEM
# --------------------------------------------------------------------------
def test_supply_voltage_absent_while_commanded_on(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=None,
            current=None,
            power=None,
            voltage_valid=False,
        )
    )
    assert result.classification is DiagnosticClassification.SUPPLY_ABNORMALITY
    assert result.fault_category is FaultType.SUPPLY_VOLTAGE


def test_out_of_band_voltage_is_a_supply_abnormality(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=90.0,
            current=0.45,
            power=40.0,
            voltage_valid=False,
        )
    )
    assert result.fault_category is FaultType.SUPPLY_VOLTAGE


# --------------------------------------------------------------------------
# 5. LIGHT SENSOR PROBLEM
# --------------------------------------------------------------------------
def test_invalid_sensor_is_not_a_lamp_failure(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            light_level=-999.0,
            sensor_status=SensorStatus.INVALID,
        )
    )
    assert result.classification is DiagnosticClassification.SENSOR_ABNORMALITY
    assert result.fault_category is FaultType.LIGHT_SENSOR
    assert result.fault_category is not FaultType.LAMP_LOAD


def test_impossible_light_level_is_a_sensor_abnormality(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            light_level=10_000_000.0,
            sensor_status=SensorStatus.VALID,
        )
    )
    assert result.classification is DiagnosticClassification.SENSOR_ABNORMALITY


def test_supply_problem_takes_precedence_over_invalid_sensor(engine):
    """A bad sensor must never mask a clear supply fault."""
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=None,
            current=None,
            power=None,
            light_level=-1.0,
            sensor_status=SensorStatus.INVALID,
            voltage_valid=False,
        )
    )
    assert result.classification is DiagnosticClassification.SUPPLY_ABNORMALITY


# --------------------------------------------------------------------------
# 6. COMMUNICATION FAILURE
# --------------------------------------------------------------------------
def test_communication_fault_is_reported(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            communication_status=CommunicationStatus.COMM_FAULT,
        )
    )
    assert result.classification is DiagnosticClassification.COMMUNICATION_ABNORMALITY
    assert result.fault_category is FaultType.COMMUNICATION


# --------------------------------------------------------------------------
# 7. CONTROLLER FAILURE
# --------------------------------------------------------------------------
def test_controller_fault_is_reported(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            controller_status=ControllerStatus.FAULT,
        )
    )
    assert result.classification is DiagnosticClassification.CONTROLLER_ABNORMALITY
    assert result.fault_category is FaultType.CONTROLLER


def test_controller_restart_is_reported(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
            controller_status=ControllerStatus.RESTARTED,
        )
    )
    assert result.fault_category is FaultType.CONTROLLER


# --------------------------------------------------------------------------
# 8. MEASUREMENT ABNORMALITY
# --------------------------------------------------------------------------
def test_physically_inconsistent_measurement_set(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=5000.0,  # inconsistent with 230 * 0.45
            power_consistent=False,
        )
    )
    assert result.classification is DiagnosticClassification.MEASUREMENT_ABNORMALITY


def test_over_current_is_detected(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=3.0,
            power=690.0,
        )
    )
    assert result.classification is DiagnosticClassification.POSSIBLE_OVER_CURRENT
    assert result.fault_category is FaultType.OVER_CURRENT


def test_under_current_below_expected_band(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.10,  # above near-zero, below expected band
            power=23.0,
        )
    )
    assert result.classification is DiagnosticClassification.POSSIBLE_UNDER_CURRENT
    assert result.fault_category is FaultType.UNDER_CURRENT


def test_switching_path_inconsistent_with_command(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.OFF,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.45,
            power=103.5,
        )
    )
    assert (
        result.classification is DiagnosticClassification.SWITCHING_PATH_INCONSISTENCY
    )
    assert result.fault_category is FaultType.LAMP_LOAD


# --------------------------------------------------------------------------
# 9. ENVIRONMENTAL / EXTERNAL CONDITION
# --------------------------------------------------------------------------
def test_environmental_classification_pathway_exists():
    """The vocabulary must allow an external-condition classification."""
    assert (
        DiagnosticClassification.ENVIRONMENTAL_OR_EXTERNAL.value
        == "ENVIRONMENTAL_OR_EXTERNAL"
    )
    assert FaultType.ENVIRONMENTAL.value == "ENVIRONMENTAL"


# --------------------------------------------------------------------------
# 10. UNKNOWN / INSPECTION_REQUIRED
# --------------------------------------------------------------------------
def test_insufficient_evidence_when_switching_feedback_unknown(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.UNKNOWN,
            voltage=230.0,
            current=0.45,
            power=103.5,
        )
    )
    assert result.classification is DiagnosticClassification.INSUFFICIENT_EVIDENCE
    assert result.fault_category is FaultType.INSPECTION_REQUIRED
    assert result.confidence is Confidence.LOW


def test_unknown_category_is_available():
    assert FaultType.UNKNOWN.value == "UNKNOWN"


# --------------------------------------------------------------------------
# fault category vs diagnostic classification vs root cause
# --------------------------------------------------------------------------
def test_fault_category_and_classification_are_distinct(engine):
    result = engine.evaluate(
        DiagnosticEvidence(
            commanded_state=LampState.ON,
            switching_feedback=LampState.ON,
            voltage=230.0,
            current=0.0,
            power=0.0,
        )
    )
    # category: reporting bucket; classification: evidence interpretation
    assert result.fault_category is FaultType.UNDER_CURRENT
    assert result.classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD
    assert result.fault_category.value != result.classification.value


def test_evidence_can_be_built_from_a_measurement(lamp_node):
    from sslv1.enums import LampState as LS
    from sslv1.nodes import LampNodeSources

    lamp_node.step(
        LampNodeSources(
            voltage=230.0, current=0.45, power=103.5, light_level=10.0,
            switching_feedback=LS.ON,
        ),
        ticks=1000,
    )
    evidence = evidence_from_measurement(lamp_node._last_measurement)
    assert evidence.commanded_state is lamp_node._last_measurement.commanded_state
    assert evidence.switching_path_on is True


def test_engine_is_deterministic(engine):
    evidence = DiagnosticEvidence(
        commanded_state=LampState.ON,
        switching_feedback=LampState.ON,
        voltage=230.0,
        current=0.0,
        power=0.0,
    )
    results = [engine.evaluate(evidence) for _ in range(10)]
    assert len({r.classification for r in results}) == 1
    assert len({r.reason for r in results}) == 1


def test_no_ai_or_ml_is_used():
    """The diagnostic engine must remain rule-based and auditable."""
    import inspect

    from sslv1 import diagnostics

    source = inspect.getsource(diagnostics)
    for banned in ("sklearn", "tensorflow", "torch", "keras", "numpy", "random"):
        assert banned not in source
