"""Deterministic expected-versus-actual diagnostic engine.

The engine combines evidence (``PR-DIAG-001``)::

    commanded state, switching feedback, supply voltage, current, power,
    light level, sensor validity, communication state, controller state

Current alone is never used to classify lamp health.

The engine emits three distinct things (``PR-FAULT-014``, ``D-034``):

* a **fault category** - the controlled-vocabulary reporting bucket,
* a **diagnostic classification** - the evidence-based interpretation,
* a **confidence** - how strongly the evidence supports the classification.

It never asserts a confirmed physical root cause. No AI/ML is used or implied.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from .configuration import LampConfiguration
from .enums import (
    CommunicationStatus,
    ControllerStatus,
    DiagnosticClassification,
    FaultType,
    LampState,
    SensorStatus,
)

class Confidence(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value

@dataclass(frozen=True)
class DiagnosticEvidence:
    """All evidence available for one diagnostic evaluation."""

    commanded_state: LampState
    switching_feedback: LampState
    voltage: Optional[float]
    current: Optional[float]
    power: Optional[float]
    light_level: Optional[float] = None
    sensor_status: SensorStatus = SensorStatus.VALID
    communication_status: CommunicationStatus = CommunicationStatus.COMM_HEALTHY
    controller_status: ControllerStatus = ControllerStatus.NORMAL
    voltage_valid: bool = True
    power_consistent: bool = True

    @property
    def switching_path_on(self) -> bool:
        return self.switching_feedback is LampState.ON

    @property
    def switching_path_known(self) -> bool:
        return self.switching_feedback is not LampState.UNKNOWN

@dataclass(frozen=True)
class DiagnosticResult:
    """Outcome of one diagnostic evaluation."""

    classification: DiagnosticClassification
    fault_category: Optional[FaultType]
    confidence: Confidence
    reason: str
    evidence: DiagnosticEvidence

    @property
    def is_normal(self) -> bool:
        return self.classification is DiagnosticClassification.NORMAL

    @property
    def requires_attention(self) -> bool:
        return self.classification is not DiagnosticClassification.NORMAL

class DiagnosticEngine:
    """Applies the approved diagnostic rules deterministically.

    Rules are evaluated in a fixed order so that the same evidence always
    produces the same result.
    """

    def __init__(self, config: LampConfiguration) -> None:
        self._config = config

    # ------------------------------------------------------------------
    def evaluate(self, evidence: DiagnosticEvidence) -> DiagnosticResult:
        cfg = self._config

        # 1. Controller health is established by the node itself.
        if evidence.controller_status is not ControllerStatus.NORMAL:
            return self._result(
                DiagnosticClassification.CONTROLLER_ABNORMALITY,
                FaultType.CONTROLLER,
                Confidence.HIGH,
                "controller status is %s" % evidence.controller_status.value,
                evidence,
            )

        # 2. Communication fault means the evidence itself may be stale.
        if evidence.communication_status is CommunicationStatus.COMM_FAULT:
            return self._result(
                DiagnosticClassification.COMMUNICATION_ABNORMALITY,
                FaultType.COMMUNICATION,
                Confidence.HIGH,
                "communication fault; evidence may be stale",
                evidence,
            )

        from math import isfinite
        if any(v is not None and (not isfinite(v) or v < 0)
               for v in (evidence.voltage, evidence.current, evidence.power)):
            return self._result(DiagnosticClassification.MEASUREMENT_ABNORMALITY,
                                FaultType.UNKNOWN, Confidence.LOW,
                                "nonfinite or negative electrical evidence", evidence)

        # 3. Supply problem: commanded ON but no valid supply voltage.
        if evidence.commanded_state is LampState.ON and (not evidence.voltage_valid or evidence.voltage is None or not cfg.voltage_min <= evidence.voltage <= cfg.voltage_max):
            return self._result(
                DiagnosticClassification.SUPPLY_ABNORMALITY,
                FaultType.SUPPLY_VOLTAGE,
                Confidence.HIGH,
                "commanded ON but supply voltage is absent or invalid",
                evidence,
            )

        # 4. Open load: commanded ON, switching path ON, voltage present,
        #    current at or below the near-zero threshold.
        if (
            evidence.commanded_state is LampState.ON
            and evidence.switching_path_on
            and evidence.voltage_valid
            and evidence.current is not None
            and evidence.current <= cfg.under_current_min
        ):
            return self._result(
                DiagnosticClassification.POSSIBLE_OPEN_LOAD,
                FaultType.UNDER_CURRENT,
                Confidence.HIGH,
                "commanded ON, switching path ON, voltage present, current %s <= %s"
                % (evidence.current, cfg.under_current_min),
                evidence,
            )

        # 5. Over current.
        if (
            evidence.commanded_state is LampState.ON
            and evidence.current is not None
            and evidence.current > cfg.over_current_max
        ):
            return self._result(
                DiagnosticClassification.POSSIBLE_OVER_CURRENT,
                FaultType.OVER_CURRENT,
                Confidence.HIGH,
                "current %s exceeds configured maximum %s"
                % (evidence.current, cfg.over_current_max),
                evidence,
            )

        # 6. Unexpected current: commanded OFF, switching path OFF, current present.
        if (
            evidence.commanded_state is LampState.OFF
            and evidence.switching_feedback is LampState.OFF
            and evidence.current is not None
            and evidence.current >= cfg.unexpected_current_min
        ):
            return self._result(
                DiagnosticClassification.UNEXPECTED_CURRENT,
                FaultType.LAMP_LOAD,
                Confidence.HIGH,
                "commanded OFF, switching path OFF, but current %s >= %s"
                % (evidence.current, cfg.unexpected_current_min),
                evidence,
            )

        # 6b. External illumination: the lamp is commanded off and drawing no
        #      current, yet the measured light level is bright. The light comes
        #      from somewhere other than this lamp, so this is an
        #      environmental/external observation and not a lamp fault.
        if (
            evidence.commanded_state is LampState.OFF
            and evidence.switching_feedback is LampState.OFF
            and evidence.current is not None
            and evidence.current <= cfg.under_current_min
            and evidence.light_level is not None
            and evidence.sensor_status is SensorStatus.VALID
            and evidence.light_level >= cfg.light_off_threshold
        ):
            return self._result(
                DiagnosticClassification.ENVIRONMENTAL_OR_EXTERNAL,
                FaultType.ENVIRONMENTAL,
                Confidence.MEDIUM,
                "commanded OFF and drawing no current while light level %s is at or "
                "above the off threshold %s: consistent with external illumination"
                % (evidence.light_level, cfg.light_off_threshold),
                evidence,
            )

        # 7. Switching path inconsistent with the command.
        if (
            evidence.switching_path_known
            and evidence.switching_feedback is not evidence.commanded_state
        ):
            return self._result(
                DiagnosticClassification.SWITCHING_PATH_INCONSISTENCY,
                FaultType.LAMP_LOAD,
                Confidence.MEDIUM,
                "switching feedback %s does not match commanded state %s"
                % (evidence.switching_feedback.value, evidence.commanded_state.value),
                evidence,
            )

        # 8. Under current below the expected band but above the near-zero threshold.
        if (
            evidence.commanded_state is LampState.ON
            and evidence.current is not None
            and evidence.current < cfg.expected_current_min
        ):
            return self._result(
                DiagnosticClassification.POSSIBLE_UNDER_CURRENT,
                FaultType.UNDER_CURRENT,
                Confidence.MEDIUM,
                "current %s below expected band minimum %s"
                % (evidence.current, cfg.expected_current_min),
                evidence,
            )

        # 9. Sensor problem. Deliberately after the supply/load rules so that a
        #    bad sensor never masks a clear supply or load condition, and so
        #    that a bad sensor is never reported as a lamp failure.
        if evidence.sensor_status is SensorStatus.INVALID:
            return self._result(
                DiagnosticClassification.SENSOR_ABNORMALITY,
                FaultType.LIGHT_SENSOR,
                Confidence.LOW,
                "light sensor reports invalid data",
                evidence,
            )

        # 10. Light level impossible for the sensor's configured range.
        if evidence.light_level is not None and not (
            cfg.light_level_min <= evidence.light_level <= cfg.light_level_max
        ):
            return self._result(
                DiagnosticClassification.SENSOR_ABNORMALITY,
                FaultType.LIGHT_SENSOR,
                Confidence.MEDIUM,
                "light level %s outside configured range [%s, %s]"
                % (
                    evidence.light_level,
                    cfg.light_level_min,
                    cfg.light_level_max,
                ),
                evidence,
            )

        # 11. Physically inconsistent measurement set.
        if not evidence.power_consistent:
            return self._result(
                DiagnosticClassification.MEASUREMENT_ABNORMALITY,
                FaultType.UNKNOWN,
                Confidence.MEDIUM,
                "measurement set is physically inconsistent",
                evidence,
            )

        # 12. Evidence insufficient to classify (for example no switching feedback).
        if (not evidence.switching_path_known or evidence.commanded_state is LampState.UNKNOWN
                or evidence.current is None or evidence.voltage is None or evidence.power is None):
            return self._result(
                DiagnosticClassification.INSUFFICIENT_EVIDENCE,
                FaultType.INSPECTION_REQUIRED,
                Confidence.LOW,
                "switching feedback unavailable; evidence insufficient",
                evidence,
            )

        # 13. Normal operation.
        return self._result(
            DiagnosticClassification.NORMAL,
            None,
            Confidence.HIGH,
            "evidence consistent with normal operation",
            evidence,
        )

    # ------------------------------------------------------------------
    @staticmethod
    def _result(
        classification: DiagnosticClassification,
        fault_category: Optional[FaultType],
        confidence: Confidence,
        reason: str,
        evidence: DiagnosticEvidence,
    ) -> DiagnosticResult:
        return DiagnosticResult(
            classification=classification,
            fault_category=fault_category,
            confidence=confidence,
            reason=reason,
            evidence=evidence,
        )

def evidence_from_measurement(measurement, config=None) -> DiagnosticEvidence:
    """Build diagnostic evidence from a measurement.

    Kept as a free function so that the diagnostics layer never imports the
    measurement module's validator (avoids a circular dependency and keeps the
    engine testable in isolation).
    """
    from .measurement import MeasurementValidator
    valid_voltage = measurement.voltage_present
    consistent = False
    if config is not None:
        valid_voltage = valid_voltage and config.voltage_min <= measurement.voltage <= config.voltage_max
        consistent = MeasurementValidator(config).assess(measurement).physically_consistent
    return DiagnosticEvidence(
        commanded_state=measurement.commanded_state,
        switching_feedback=measurement.switching_feedback,
        voltage=measurement.voltage,
        current=measurement.current,
        power=measurement.power,
        light_level=measurement.light_level,
        sensor_status=measurement.sensor_status,
        communication_status=measurement.communication_status,
        controller_status=measurement.controller_status,
        voltage_valid=valid_voltage,
        power_consistent=consistent,
    )
