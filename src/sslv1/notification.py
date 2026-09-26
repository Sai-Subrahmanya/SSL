"""Notification state machine and notification engine.

Notification state is **independent** of the fault lifecycle
(``PR-FAULT-013``, ``D-033``): a fault may remain ``CONFIRMED`` while its
notification state moves ``PENDING -> SENT -> ACK_PENDING -> REMINDER_DUE ->
ESCALATED``.

Notification failure, reminder or escalation never changes the fault
lifecycle state and never switches a lamp off (``PR-FAULT-008``,
``PR-FAULT-009``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar, Dict, Optional

from .configuration import LampConfiguration
from .enums import NotificationState
from .errors import IllegalTransitionError
from .fault import Fault


class NotificationLifecycle:
    """Permitted notification state transitions."""

    TRANSITIONS: ClassVar[Dict[NotificationState, frozenset]] = {
        NotificationState.NOT_REQUIRED: frozenset(),
        NotificationState.PENDING: frozenset(
            {NotificationState.SENT, NotificationState.DELIVERY_FAILED}
        ),
        NotificationState.SENT: frozenset(
            {NotificationState.ACK_PENDING, NotificationState.DELIVERY_FAILED}
        ),
        NotificationState.ACK_PENDING: frozenset(
            {
                NotificationState.REMINDER_DUE,
                NotificationState.ESCALATED,
                NotificationState.DELIVERY_FAILED,
            }
        ),
        NotificationState.REMINDER_DUE: frozenset(
            {
                NotificationState.ACK_PENDING,
                NotificationState.ESCALATED,
                NotificationState.DELIVERY_FAILED,
            }
        ),
        NotificationState.ESCALATED: frozenset(
            {
                NotificationState.ACK_PENDING,
                NotificationState.DELIVERY_FAILED,
            }
        ),
        NotificationState.DELIVERY_FAILED: frozenset(
            {NotificationState.PENDING, NotificationState.ESCALATED}
        ),
    }

    @classmethod
    def can_transition(cls, current: NotificationState, target: NotificationState) -> bool:
        return target in cls.TRANSITIONS[current]

    @classmethod
    def transition(cls, fault: Fault, target: NotificationState, reason: str = "") -> None:
        if not cls.can_transition(fault.notification_state, target):
            raise IllegalTransitionError(
                "illegal notification transition %s -> %s for fault %s"
                % (fault.notification_state.value, target.value, fault.fault_id)
            )
        fault.notification_state = target
        if reason:
            fault.confirmation_reason = reason


@dataclass(frozen=True)
class NotificationPolicy:
    """Notification behaviour, taken from configuration."""

    ack_required: bool
    reminder_interval_ticks: int
    escalation_timeout_ticks: int
    destination: str
    role: str
    retry_count: int

    @classmethod
    def from_config(cls, config: LampConfiguration) -> "NotificationPolicy":
        return cls(
            ack_required=config.ack_required,
            reminder_interval_ticks=config.ack_reminder_interval_ticks,
            escalation_timeout_ticks=config.escalation_timeout_ticks,
            destination=config.escalation_destination,
            role=config.escalation_role.value,
            retry_count=config.notification_retry_count,
        )


class NotificationEngine:
    """Drives notification state for confirmed faults.

    The engine is deliberately passive with respect to lighting: nothing here
    can change a commanded lamp state.
    """

    def __init__(self, config: LampConfiguration, on_event=None) -> None:
        self._policy = NotificationPolicy.from_config(config)
        self._on_event = on_event
        self._last_notified: Dict[str, int] = {}
        self._delivery_attempts: Dict[str, int] = {}

    @property
    def policy(self) -> NotificationPolicy:
        return self._policy

    # ------------------------------------------------------------------
    def on_fault_confirmed(self, fault: Fault, ticks: int) -> None:
        """Initialise notification state when a fault is confirmed."""
        if not self._policy.ack_required:
            fault.notification_state = NotificationState.NOT_REQUIRED
            return
        fault.notification_state = NotificationState.PENDING
        self._last_notified[fault.fault_id] = ticks
        self._delivery_attempts[fault.fault_id] = 0

    def notify(self, fault: Fault, ticks: int, delivered: bool = True) -> NotificationState:
        """Attempt delivery of the notification."""
        if fault.notification_state is NotificationState.NOT_REQUIRED:
            return fault.notification_state

        if not delivered:
            return self.delivery_failed(fault, ticks)

        if fault.notification_state in (
            NotificationState.PENDING,
            NotificationState.REMINDER_DUE,
            NotificationState.ESCALATED,
            NotificationState.DELIVERY_FAILED,
        ):
            NotificationLifecycle.transition(
                fault,
                NotificationState.SENT,
                "notification sent to %s" % self._policy.destination,
            )
            NotificationLifecycle.transition(
                fault, NotificationState.ACK_PENDING, "awaiting acknowledgement"
            )
            self._last_notified[fault.fault_id] = ticks
            self._emit("FAULT_NOTIFIED", fault, "notification sent")
        return fault.notification_state

    def delivery_failed(self, fault: Fault, ticks: int) -> NotificationState:
        attempts = self._delivery_attempts.get(fault.fault_id, 0) + 1
        self._delivery_attempts[fault.fault_id] = attempts
        NotificationLifecycle.transition(
            fault, NotificationState.DELIVERY_FAILED, "delivery failed"
        )
        self._emit(
            "FAULT_NOTIFICATION_FAILED",
            fault,
            "delivery attempt %d failed" % attempts,
        )
        if attempts <= self._policy.retry_count:
            # Retry: back to PENDING, to be picked up by the next notify() call.
            NotificationLifecycle.transition(
                fault, NotificationState.PENDING, "retry scheduled"
            )
        return fault.notification_state

    def tick(self, fault: Fault, ticks: int) -> Optional[str]:
        """Advance notification state for elapsed time.

        Returns a short description of what happened, or ``None``.
        """
        if fault.notification_state is NotificationState.NOT_REQUIRED:
            return None
        last = self._last_notified.get(fault.fault_id)
        if last is None:
            return None

        elapsed = ticks - last

        # Escalation and reminders apply to the states in which the engine
        # actually *rests* while waiting for an acknowledgement. ``SENT`` is
        # deliberately absent: notify() moves SENT -> ACK_PENDING atomically,
        # so a fault never rests in SENT, and neither SENT -> REMINDER_DUE nor
        # SENT -> ESCALATED is a legal transition.
        if fault.notification_state in (
            NotificationState.ACK_PENDING,
            NotificationState.REMINDER_DUE,
        ):
            if elapsed >= self._policy.escalation_timeout_ticks:
                NotificationLifecycle.transition(
                    fault,
                    NotificationState.ESCALATED,
                    "escalation timeout %d ticks reached"
                    % self._policy.escalation_timeout_ticks,
                )
                self._emit(
                    "FAULT_ESCALATED",
                    fault,
                    "escalated to %s (%s)"
                    % (self._policy.destination, self._policy.role),
                )
                return "escalated"
            if elapsed >= self._policy.reminder_interval_ticks:
                if fault.notification_state is NotificationState.REMINDER_DUE:
                    # A reminder is already outstanding. Re-entering
                    # REMINDER_DUE is not a legal transition, and re-emitting
                    # on every tick would flood the event log. The only way
                    # forward from REMINDER_DUE is acknowledgement, delivery
                    # failure or escalation, all handled elsewhere.
                    return None
                NotificationLifecycle.transition(
                    fault,
                    NotificationState.REMINDER_DUE,
                    "reminder interval %d ticks elapsed"
                    % self._policy.reminder_interval_ticks,
                )
                self._emit("FAULT_REMINDER_DUE", fault, "reminder due")
                return "reminder_due"
        return None

    def acknowledge(self, fault: Fault, actor: str) -> None:
        """Record that an authorized actor acknowledged the notification.

        Acknowledgement is recorded; it does not close the fault and does not
        change lamp operation (``PR-FAULT-008``).
        """
        if fault.notification_state is NotificationState.NOT_REQUIRED:
            return
        # Notification state remains ACK_PENDING (or its current value); the
        # acknowledgement itself is recorded on the fault lifecycle by the
        # fault engine.
        self._emit(
            "FAULT_ACKNOWLEDGED",
            fault,
            "acknowledged by %s" % actor,
        )

    def _emit(self, kind: str, fault: Fault, reason: str) -> None:
        if self._on_event is not None:
            self._on_event(kind, fault, reason)
