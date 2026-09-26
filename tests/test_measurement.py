"""Measurement model and validity tests (PR-MEASURE-*).

Covers: the per-lamp measurement set, sensor validity reporting, measurement
validity, and the explicit non-billing-grade character of the values.
"""

from __future__ import annotations

import pytest

from sslv1.diagnostics import DiagnosticEngine, evidence_from_measurement
from sslv1.enums import (
    CommunicationStatus,
    ControllerStatus,
    DiagnosticClassification,
    LampState,
    OperatingMode,
    SensorStatus,
    TimeSyncState,
)
from sslv1.identity import Identifier
from sslv1.measurement import Measurement, MeasurementValidator
from sslv1.time_model import Timestamp

from conftest import GROUP, SITE, healthy_sources


@pytest.fixture
def validator(lamp_config):
    return MeasurementValidator(lamp_config)


def make_measurement(**overrides):
    params = dict(
        timestamp=Timestamp(ticks=1000, sync_state=TimeSyncState.SYNCHRONIZED),
        site_id=SITE,
        group_id=GROUP,
        lamp_id=Identifier("LAMP-01"),
        effective_mode=OperatingMode.AUTO_SENSOR,
        commanded_state=LampState.ON,
        switching_feedback=LampState.ON,
        actual_state=LampState.ON,
        voltage=230.0,
        current=0.45,
        power=103.5,
        energy=120.0,
        light_level=10.0,
        sensor_status=SensorStatus.VALID,
        communication_status=CommunicationStatus.COMM_HEALTHY,
        controller_status=ControllerStatus.NORMAL,
    )
    params.update(overrides)
    return Measurement(**params)


# --------------------------------------------------------------------------
# the per-lamp measurement set
# --------------------------------------------------------------------------
def test_measurement_carries_the_documented_field_set():
    measurement = make_measurement()
    payload = measurement.to_dict()
    for key in (
        "timestamp_ticks", "time_sync_state", "site_id", "group_id", "lamp_id",
        "effective_mode", "commanded_state", "switching_feedback", "actual_state",
        "voltage", "current", "power", "energy", "light_level",
        "sensor_status", "communication_status", "controller_status",
        "sequence_number",
    ):
        assert key in payload, key


def test_measurement_is_a_value_object():
    a = make_measurement()
    b = make_measurement()
    assert a.to_dict() == b.to_dict()


def test_measurement_ordering_uses_the_sequence_number():
    first = make_measurement(sequence_number=1)
    second = make_measurement(sequence_number=2)
    assert first.sequence_number < second.sequence_number


# --------------------------------------------------------------------------
# validity
# --------------------------------------------------------------------------
def test_valid_measurement_has_no_issues(validator):
    assessment = validator.assess(make_measurement())
    assert assessment.has_issues is False
    assert assessment.physically_consistent is True
    assert assessment.issues == ()


def test_out_of_band_voltage_is_reported(validator):
    assessment = validator.assess(make_measurement(voltage=300.0))
    assert assessment.has_issues is True
    assert any("voltage" in issue for issue in assessment.issues)


def test_absent_supply_voltage_is_reported(validator):
    assessment = validator.assess(make_measurement(voltage=None))
    assert assessment.has_issues is True


def test_negative_current_is_reported(validator):
    assessment = validator.assess(make_measurement(current=-0.1))
    assert assessment.has_issues is True


def test_excess_power_is_reported(validator):
    assessment = validator.assess(make_measurement(power=10_000.0))
    assert assessment.has_issues is True


def test_impossible_light_level_is_reported(validator):
    assessment = validator.assess(make_measurement(light_level=-5.0))
    assert assessment.has_issues is True


def test_physically_inconsistent_power_is_reported(validator):
    # 230 V at 0.45 A is about 103.5 W, not 900 W.
    assessment = validator.assess(make_measurement(power=900.0))
    assert assessment.has_issues is True
    assert assessment.physically_consistent is False


def test_switching_feedback_is_an_abstraction_not_a_relay():
    """switching_feedback carries no relay-contact assumption."""
    payload = make_measurement().to_dict()
    assert "switching_feedback" in payload
    assert "relay" not in payload


# --------------------------------------------------------------------------
# sensor validity
# --------------------------------------------------------------------------
def test_invalid_sensor_is_reported_not_guessed_around(lamp_node):
    """An invalid light sensor is reported, never worked around silently."""
    from sslv1.enums import SensorStatus

    lamp_node.step(healthy_sources(sensor_status=SensorStatus.INVALID), ticks=1000)
    measurement = lamp_node.measurements[-1]
    assert measurement.sensor_status is SensorStatus.INVALID
    sensor_events = [e for e in lamp_node.events
                     if e.event_type.value in ("SENSOR_INVALID",
                                               "MEASUREMENT_OUT_OF_RANGE")]
    assert sensor_events


def test_invalid_sensor_retains_the_previous_lighting_decision(lamp_node):
    """A bad sensor never causes an uncommanded lamp transition."""
    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    assert lamp_node.control.lamp_is_on is True
    lamp_node.step(healthy_sources(sensor_status=SensorStatus.INVALID), ticks=2000)
    assert lamp_node.control.lamp_is_on is True


def test_evidence_can_be_built_from_a_measurement(lamp_node):
    lamp_node.step(healthy_sources(), ticks=1000)
    evidence = evidence_from_measurement(lamp_node.measurements[-1])
    assert evidence.commanded_state is LampState.ON
    assert evidence.switching_path_on is True
    assert evidence.voltage_valid is True


def test_evidence_from_an_invalid_sensor_measurement():
    evidence = evidence_from_measurement(make_measurement(sensor_status=SensorStatus.INVALID))
    assert evidence.sensor_status is SensorStatus.INVALID


# --------------------------------------------------------------------------
# engineering values, never billing grade
# --------------------------------------------------------------------------
def test_measurement_is_not_billing_grade():
    payload = make_measurement().to_dict()
    for banned in ("billing_grade", "billing", "tariff", "revenue", "metering_class"):
        assert banned not in payload


def test_measurement_round_trips_through_the_wire_codec():
    """The measurement crosses the bus without losing its meaning."""
    from sslv1.comm import MessageType, decode_payload, encode_payload

    measurement = make_measurement()
    payload = {
        "timestamp_ticks": measurement.timestamp.ticks,
        "voltage_mv": 230000,
        "current_ma": 450,
        "power_mw": 103500,
        "energy_mwh": 120000,
        "light_level": 10,
        "effective_mode": measurement.effective_mode,
        "commanded_state": measurement.commanded_state,
        "switching_feedback": measurement.switching_feedback,
        "actual_state": measurement.actual_state,
        "sensor_status": measurement.sensor_status,
        "communication_status": measurement.communication_status,
        "controller_status": measurement.controller_status,
    }
    decoded = decode_payload(MessageType.MEASUREMENT_RESPONSE,
                             encode_payload(MessageType.MEASUREMENT_RESPONSE, payload))
    assert decoded["voltage_mv"] == 230000
    assert decoded["switching_feedback"] is LampState.ON
    assert decoded["effective_mode"] is OperatingMode.AUTO_SENSOR


def test_diagnostic_engine_uses_measurement_evidence(lamp_node):
    engine = DiagnosticEngine(lamp_node.config)
    evidence = evidence_from_measurement(
        make_measurement(current=0.0, power=0.0)
    )
    result = engine.evaluate(evidence)
    assert result.classification is DiagnosticClassification.POSSIBLE_OPEN_LOAD


# --------------------------------------------------------------------------
# effective_mode semantics (D-031, PR-CONTROL-007)
#
# Regression: the field used to be called ``operating_mode``, which is
# ambiguous because it does not say *which* of configured_mode /
# active_override / effective_mode it carries. It carries the effective mode.
# --------------------------------------------------------------------------
def test_measurement_carries_effective_mode_not_configured_mode(lamp_node, operator):
    """The measurement records the mode in force, not the configured mode."""
    lamp_node.force_on(operator, ticks=1000)
    lamp_node.step(healthy_sources(light_level=10.0), ticks=2000)
    measurement = lamp_node.last_measurement

    assert measurement.effective_mode is OperatingMode.FORCE_ON
    assert lamp_node.control.configured_mode.value == "AUTO_SENSOR"


def test_measurement_effective_mode_returns_to_configured_after_override_clears(
    lamp_node, operator
):
    """Clearing the override restores the configured mode in the measurement."""
    lamp_node.force_off(operator, ticks=1000)
    lamp_node.step(healthy_sources(light_level=10.0), ticks=2000)
    assert lamp_node.last_measurement.effective_mode is OperatingMode.FORCE_OFF

    lamp_node.return_to_auto(operator, ticks=3000)
    lamp_node.step(healthy_sources(light_level=10.0), ticks=4000)
    assert lamp_node.last_measurement.effective_mode is OperatingMode.AUTO_SENSOR


def test_measurement_has_no_operating_mode_field():
    """The ambiguous legacy name must not survive on the domain entity."""
    assert not hasattr(make_measurement(), "operating_mode")
    assert "operating_mode" not in make_measurement().to_dict()
    assert "effective_mode" in make_measurement().to_dict()
