"""Fault model, fault lifecycle state machine and the fault engine.

Fault lifecycle (``PR-FAULT-003``, ``D-011``)::

    NORMAL -> SUSPECTED -> CONFIRMED -> ACKNOWLEDGED -> UNDER_REPAIR -> VERIFYING -> CLOSED

``NOTIFIED`` is **not** a lifecycle state; notification progress lives in
:mod:`sslv1.notification` (``PR-FAULT-013``, ``D-033``).

Latching (``PR-FAULT-006``): a confirmed fault does not disappear because one
later measurement looks normal. Clearing requires the repair/verification
path, or (for an unconfirmed suspicion) the evidence clearing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Dict, List, Optional, Tuple

from .configuration import LampConfiguration

from .enums import (
    DiagnosticClassification,
    FaultSeverity,
    FaultState,
    FaultType,
    NotificationState,
    RepairStatus,
    VerificationStatus,
)
from .diagnostics import DiagnosticResult
from .errors import IllegalTransitionError
from .identity import Identifier

@dataclass
class Fault:
    """A managed fault record."""

    fault_id: str
    site_id: Identifier
    group_id: Identifier
    lamp_id: Identifier
    created_ticks: int
    fault_type: FaultType
    diagnostic_classification: DiagnosticClassification
    severity: FaultSeverity
    state: FaultState = FaultState.SUSPECTED
    confirmation_count: int = 0
    first_observation_ticks: int = 0
    last_observation_ticks: int = 0
    confirmed_ticks: Optional[int] = None
    acknowledged_ticks: Optional[int] = None
    closed_ticks: Optional[int] = None
    notification_state: NotificationState = NotificationState.PENDING
    repair_status: RepairStatus = RepairStatus.NOT_STARTED
    verification_status: VerificationStatus = VerificationStatus.NOT_VERIFIED
    evidence: Dict[str, object] = field(default_factory=dict)
    verification_evidence: Optional[Dict[str, object]] = None
    related_event_ids: List[int] = field(default_factory=list)
    actor: Optional[str] = None
    closed_actor: Optional[str] = None
    confirmation_reason: str = ""

    @property
    def is_active(self) -> bool:
        """A fault is active until it is closed."""
        return self.state is not FaultState.CLOSED and self.state is not FaultState.NORMAL

    @property
    def is_confirmed(self) -> bool:
        return self.state in (
            FaultState.CONFIRMED,
            FaultState.ACKNOWLEDGED,
            FaultState.UNDER_REPAIR,
            FaultState.VERIFYING,
        )

    def key(self) -> Tuple[str, FaultType, DiagnosticClassification]:
        return (str(self.lamp_id), self.fault_type, self.diagnostic_classification)

class FaultLifecycle:
    """Permitted fault lifecycle transitions (``PR-FAULT-004``)."""

    TRANSITIONS: ClassVar[Dict[FaultState, frozenset]] = {
        FaultState.NORMAL: frozenset({FaultState.SUSPECTED}),
        FaultState.SUSPECTED: frozenset({FaultState.CONFIRMED, FaultState.NORMAL}),
        FaultState.CONFIRMED: frozenset({FaultState.ACKNOWLEDGED}),
        FaultState.ACKNOWLEDGED: frozenset({FaultState.UNDER_REPAIR}),
        FaultState.UNDER_REPAIR: frozenset({FaultState.VERIFYING}),
        FaultState.VERIFYING: frozenset({FaultState.CLOSED, FaultState.UNDER_REPAIR}),
        FaultState.CLOSED: frozenset({FaultState.SUSPECTED}),
    }

    @classmethod
    def can_transition(cls, current: FaultState, target: FaultState) -> bool:
        return target in cls.TRANSITIONS[current]

    @classmethod
    def transition(
        cls,
        fault: Fault,
        target: FaultState,
        ticks: int,
        actor: Optional[str] = None,
        reason: str = "",
    ) -> None:
        if not cls.can_transition(fault.state, target):
            raise IllegalTransitionError(
                "illegal fault transition %s -> %s for fault %s"
                % (fault.state.value, target.value, fault.fault_id)
            )
        fault.state = target
        if target is FaultState.CONFIRMED:
            fault.confirmed_ticks = ticks
            fault.confirmation_reason = reason
        elif target is FaultState.ACKNOWLEDGED:
            fault.acknowledged_ticks = ticks
            fault.actor = actor
        elif target is FaultState.CLOSED:
            fault.closed_ticks = ticks
            fault.closed_actor = actor
        if reason and target is not FaultState.CONFIRMED:
            fault.confirmation_reason = reason

@dataclass(frozen=True)
class ConfirmationPolicy:
    """Configurable confirmation policy (``PR-FAULT-005``, ``PR-CONFIG-006``)."""

    count: int
    window_ticks: int

    @classmethod
    def from_config(cls, config: LampConfiguration) -> "ConfirmationPolicy":
        return cls(
            count=config.fault_confirmation_count,
            window_ticks=config.fault_confirmation_window_ticks,
        )

#: Maps a diagnostic classification to the severity used when a fault is raised.
_SEVERITY_BY_CLASSIFICATION: Dict[DiagnosticClassification, FaultSeverity] = {
    DiagnosticClassification.NORMAL: FaultSeverity.INFO,
    DiagnosticClassification.POSSIBLE_OPEN_LOAD: FaultSeverity.MAJOR,
    DiagnosticClassification.POSSIBLE_UNDER_CURRENT: FaultSeverity.MINOR,
    DiagnosticClassification.POSSIBLE_OVER_CURRENT: FaultSeverity.MAJOR,
    DiagnosticClassification.UNEXPECTED_CURRENT: FaultSeverity.MAJOR,
    DiagnosticClassification.SWITCHING_PATH_INCONSISTENCY: FaultSeverity.MINOR,
    DiagnosticClassification.SUPPLY_ABNORMALITY: FaultSeverity.MAJOR,
    DiagnosticClassification.SENSOR_ABNORMALITY: FaultSeverity.MINOR,
    DiagnosticClassification.MEASUREMENT_ABNORMALITY: FaultSeverity.MINOR,
    DiagnosticClassification.COMMUNICATION_ABNORMALITY: FaultSeverity.MAJOR,
    DiagnosticClassification.CONTROLLER_ABNORMALITY: FaultSeverity.CRITICAL,
    DiagnosticClassification.ENVIRONMENTAL_OR_EXTERNAL: FaultSeverity.MINOR,
    DiagnosticClassification.INSUFFICIENT_EVIDENCE: FaultSeverity.INFO,
}

class FaultEngine:
    """Raises, confirms, latches and closes faults.

    The engine is deterministic: the same sequence of diagnostic results always
    produces the same fault records.
    """

    def __init__(
        self,
        config: LampConfiguration,
        on_event=None,
    ) -> None:
        self._config = config
        self._policy = ConfirmationPolicy.from_config(config)
        self._on_event = on_event
        self._faults: Dict[str, Fault] = {}
        self._active_by_key: Dict[Tuple[str, FaultType, DiagnosticClassification], str] = {}
        self._sequence = 0

    # ------------------------------------------------------------------
    @property
    def faults(self) -> Tuple[Fault, ...]:
        return tuple(self._faults.values())

    @property
    def active_faults(self) -> Tuple[Fault, ...]:
        return tuple(f for f in self._faults.values() if f.is_active)

    def get(self, fault_id: str) -> Optional[Fault]:
        return self._faults.get(fault_id)

    def active_for_lamp(self, lamp_id: Identifier) -> Tuple[Fault, ...]:
        return tuple(f for f in self.active_faults if f.lamp_id == lamp_id)

    # ------------------------------------------------------------------
    def observe(
        self,
        site_id: Identifier,
        group_id: Identifier,
        lamp_id: Identifier,
        result: DiagnosticResult,
        ticks: int,
    ) -> Optional[Fault]:
        """Feed one diagnostic result into the fault engine.

        Returns the fault that was created, confirmed or cleared, if any.
        """
        if result.is_normal:
            return self._observe_normal(lamp_id, ticks)

        category = result.fault_category or FaultType.UNKNOWN
        classification = result.classification
        key = (str(lamp_id), category, classification)
        fault_id = self._active_by_key.get(key)

        if fault_id is None:
            return self._raise(lamp_id, site_id, group_id, result, ticks)

        fault = self._faults[fault_id]
        fault.last_observation_ticks = ticks
        fault.evidence = _evidence_snapshot(result)

        # Count consecutive observations inside the confirmation window. The
        # count keeps growing after confirmation so that oscillation is
        # visible in the record as one fault with many observations.
        if ticks - fault.first_observation_ticks > self._policy.window_ticks:
            fault.confirmation_count = 1
            fault.first_observation_ticks = ticks
        else:
            fault.confirmation_count += 1

        if fault.state is FaultState.SUSPECTED:
            if fault.confirmation_count >= self._policy.count:
                FaultLifecycle.transition(
                    fault,
                    FaultState.CONFIRMED,
                    ticks,
                    reason="confirmed after %d observations within %d ticks"
                    % (fault.confirmation_count, self._policy.window_ticks),
                )
                self._emit("FAULT_CONFIRMED", fault, fault.confirmation_reason)
            else:
                self._emit(
                    "FAULT_SUSPECTED",
                    fault,
                    "observation %d of %d"
                    % (fault.confirmation_count, self._policy.count),
                )
        # A confirmed fault latches: further abnormal observations update the
        # evidence but do not create a new fault or change the lifecycle state.
        return fault

    # ------------------------------------------------------------------
    def acknowledge(self, fault_id: str, actor: str, ticks: int) -> Fault:
        fault = self._require(fault_id)
        if fault.state is not FaultState.CONFIRMED:
            raise IllegalTransitionError(
                "fault %s cannot be acknowledged from state %s"
                % (fault_id, fault.state.value)
            )
        FaultLifecycle.transition(fault, FaultState.ACKNOWLEDGED, ticks, actor=actor)
        self._emit("FAULT_ACKNOWLEDGED", fault, "acknowledged by %s" % actor)
        return fault

    def start_repair(self, fault_id: str, actor: str, ticks: int) -> Fault:
        fault = self._require(fault_id)
        if fault.state is not FaultState.ACKNOWLEDGED:
            raise IllegalTransitionError(
                "fault %s cannot start repair from state %s"
                % (fault_id, fault.state.value)
            )
        fault.repair_status = RepairStatus.IN_PROGRESS
        FaultLifecycle.transition(fault, FaultState.UNDER_REPAIR, ticks, actor=actor)
        self._emit("FAULT_REPAIR_STARTED", fault, "repair started by %s" % actor)
        return fault

    def report_repaired(self, fault_id: str, actor: str, ticks: int) -> Fault:
        fault = self._require(fault_id)
        if fault.state is not FaultState.UNDER_REPAIR:
            raise IllegalTransitionError(
                "fault %s cannot be reported repaired from state %s"
                % (fault_id, fault.state.value)
            )
        fault.repair_status = RepairStatus.REPAIRED
        fault.verification_status = VerificationStatus.VERIFYING
        FaultLifecycle.transition(fault, FaultState.VERIFYING, ticks, actor=actor)
        return fault

    def verify(
        self,
        fault_id: str,
        actor: str,
        ticks: int,
        verified: bool,
        evidence: Optional[Dict[str, object]] = None,
    ) -> Fault:
        """Record a verification outcome.

        Successful verification closes the fault. Failed verification returns
        the fault to an active state (``UNDER_REPAIR``) rather than silently
        closing it (``PR-FAULT-011``).
        """
        fault = self._require(fault_id)
        if fault.state is not FaultState.VERIFYING:
            raise IllegalTransitionError(
                "fault %s cannot be verified from state %s"
                % (fault_id, fault.state.value)
            )
        fault.verification_evidence = dict(evidence or {})
        if verified:
            fault.verification_status = VerificationStatus.VERIFIED
            FaultLifecycle.transition(fault, FaultState.CLOSED, ticks, actor=actor)
            self._active_by_key.pop(fault.key(), None)
            self._emit("FAULT_CLOSED", fault, "verification passed; closed by %s" % actor)
        else:
            fault.verification_status = VerificationStatus.VERIFICATION_FAILED
            fault.repair_status = RepairStatus.NOT_REPAIRED
            FaultLifecycle.transition(
                fault, FaultState.UNDER_REPAIR, ticks, actor=actor,
                reason="verification failed; returned to UNDER_REPAIR",
            )
            self._emit(
                "FAULT_VERIFICATION_FAILED",
                fault,
                "verification failed; fault returned to UNDER_REPAIR",
            )
        return fault

    # ------------------------------------------------------------------
    def _observe_normal(self, lamp_id: Identifier, ticks: int) -> Optional[Fault]:
        cleared = None
        for fault in list(self._faults.values()):
            if fault.lamp_id != lamp_id or not fault.is_active:
                continue
            if fault.state is FaultState.SUSPECTED:
                # Unconfirmed suspicion: evidence cleared, no fault retained.
                FaultLifecycle.transition(
                    fault, FaultState.NORMAL, ticks, reason="evidence cleared before confirmation"
                )
                self._active_by_key.pop(fault.key(), None)
                cleared = fault
            # Confirmed faults latch: a single normal observation never clears them.
        return cleared

    def _raise(
        self,
        lamp_id: Identifier,
        site_id: Identifier,
        group_id: Identifier,
        result: DiagnosticResult,
        ticks: int,
    ) -> Fault:
        self._sequence += 1
        fault = Fault(
            fault_id="F-%04d" % self._sequence,
            site_id=site_id,
            group_id=group_id,
            lamp_id=lamp_id,
            created_ticks=ticks,
            fault_type=result.fault_category or FaultType.UNKNOWN,
            diagnostic_classification=result.classification,
            severity=_SEVERITY_BY_CLASSIFICATION.get(
                result.classification, FaultSeverity.MINOR
            ),
            confirmation_count=1,
            first_observation_ticks=ticks,
            last_observation_ticks=ticks,
            evidence=_evidence_snapshot(result),
        )
        self._faults[fault.fault_id] = fault
        self._active_by_key[fault.key()] = fault.fault_id
        if fault.confirmation_count >= self._policy.count:
            FaultLifecycle.transition(
                fault,
                FaultState.CONFIRMED,
                ticks,
                reason="confirmed after %d observation(s)" % fault.confirmation_count,
            )
            self._emit("FAULT_CONFIRMED", fault, fault.confirmation_reason)
        else:
            self._emit(
                "FAULT_SUSPECTED",
                fault,
                "observation %d of %d" % (fault.confirmation_count, self._policy.count),
            )
        return fault

    def _require(self, fault_id: str) -> Fault:
        fault = self._faults.get(fault_id)
        if fault is None:
            raise IllegalTransitionError("unknown fault id %s" % fault_id)
        return fault

    def _emit(self, kind: str, fault: Fault, reason: str) -> None:
        if self._on_event is not None:
            self._on_event(kind, fault, reason)

def _evidence_snapshot(result: DiagnosticResult) -> Dict[str, object]:
    ev = result.evidence
    return {
        "classification": result.classification.value,
        "fault_category": (result.fault_category.value if result.fault_category else None),
        "confidence": result.confidence.value,
        "reason": result.reason,
        "commanded_state": ev.commanded_state.value,
        "switching_feedback": ev.switching_feedback.value,
        "voltage": ev.voltage,
        "current": ev.current,
        "power": ev.power,
        "light_level": ev.light_level,
        "sensor_status": ev.sensor_status.value,
        "communication_status": ev.communication_status.value,
        "controller_status": ev.controller_status.value,
    }
