"""Measurement model and measurement validity.

Measurements are **engineering monitoring values**, never billing-grade
metering (``PR-MEASURE-005``, ``D-029``). Every measurement carries explicit
validity information; a number is never silently treated as trustworthy
(``PR-MEASURE-004``).

The model uses ``switching_feedback`` - an abstraction for the observed state
of the switching path whose physical realisation is a hardware-design
decision (``D-032``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Tuple

from .configuration import LampConfiguration
from .enums import (
    CommunicationStatus,
    ControllerStatus,
    LampState,
    OperatingMode,
    SensorStatus,
)
from .identity import Identifier
from .time_model import Timestamp


@dataclass(frozen=True)
class Measurement:
    """A per-lamp measurement snapshot.

    ``effective_mode`` is the **effective** mode - the mode actually in
    force when the snapshot was taken, including any active override. It is
    not the persistent configured mode and it is not an override. The
    three-valued model is ``configured_mode`` / ``active_override`` /
    ``effective_mode`` (``PR-CONTROL-007``, ``D-031``); ``RETURN_TO_AUTO``
    is a command, never a mode.
    """

    timestamp: Timestamp
    site_id: Identifier
    group_id: Identifier
    lamp_id: Identifier
    effective_mode: OperatingMode
    commanded_state: LampState
    switching_feedback: LampState
    actual_state: LampState
    voltage: Optional[float]
    current: Optional[float]
    power: Optional[float]
    energy: Optional[float]
    light_level: Optional[float]
    sensor_status: SensorStatus
    communication_status: CommunicationStatus
    controller_status: ControllerStatus
    sequence_number: int = 0

    # -- convenience -------------------------------------------------------
    @property
    def voltage_present(self) -> bool:
        return self.voltage is not None

    @property
    def switching_path_on(self) -> bool:
        return self.switching_feedback is LampState.ON

    def to_dict(self) -> dict:
        return {
            "timestamp_ticks": self.timestamp.ticks,
            "time_sync_state": self.timestamp.sync_state.value,
            "site_id": str(self.site_id),
            "group_id": str(self.group_id),
            "lamp_id": str(self.lamp_id),
            "effective_mode": self.effective_mode.value,
            "commanded_state": self.commanded_state.value,
            "switching_feedback": self.switching_feedback.value,
            "actual_state": self.actual_state.value,
            "voltage": self.voltage,
            "current": self.current,
            "power": self.power,
            "energy": self.energy,
            "light_level": self.light_level,
            "sensor_status": self.sensor_status.value,
            "communication_status": self.communication_status.value,
            "controller_status": self.controller_status.value,
            "sequence_number": self.sequence_number,
        }


@dataclass(frozen=True)
class MeasurementAssessment:
    """Result of validating a measurement against configuration."""

    issues: Tuple[str, ...]
    physically_consistent: bool

    @property
    def has_issues(self) -> bool:
        return bool(self.issues)


class MeasurementValidator:
    """Validates measurements against configuration thresholds."""

    def __init__(self, config: LampConfiguration) -> None:
        self._config = config

    def assess(self, measurement: Measurement) -> MeasurementAssessment:
        cfg = self._config
        issues = []

        voltage = measurement.voltage
        current = measurement.current
        power = measurement.power
        light = measurement.light_level

        if voltage is None:
            issues.append("voltage unavailable")
        elif not (cfg.voltage_min <= voltage <= cfg.voltage_max):
            issues.append(
                "voltage %s outside configured band [%s, %s]"
                % (voltage, cfg.voltage_min, cfg.voltage_max)
            )

        if current is not None and current < 0:
            issues.append("current %s is negative" % current)

        if power is not None and power > cfg.power_max:
            issues.append(
                "power %s exceeds configured maximum %s" % (power, cfg.power_max)
            )

        if light is not None and not (cfg.light_level_min <= light <= cfg.light_level_max):
            issues.append(
                "light level %s outside configured range [%s, %s]"
                % (light, cfg.light_level_min, cfg.light_level_max)
            )

        # power ~= voltage * current consistency (physical sanity, not accuracy)
        from math import isfinite
        bad_numbers = any(v is not None and (not isfinite(v) or v < 0)
                          for v in (voltage, current, power, light))
        consistent = not bad_numbers
        if bad_numbers:
            issues.append("nonfinite or negative measurement")
        if voltage is not None and current is not None and power is not None:
            expected = voltage * current
            tolerance = max(abs(expected), 1.0) * cfg.power_consistency_tolerance
            if abs(power - expected) > tolerance:
                consistent = False
                issues.append(
                    "power %s inconsistent with voltage*current %s (tolerance %s)"
                    % (power, expected, tolerance)
                )

        if measurement.sensor_status is SensorStatus.INVALID:
            issues.append("sensor status INVALID")

        return MeasurementAssessment(issues=tuple(issues), physically_consistent=consistent)
