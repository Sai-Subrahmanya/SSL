"""Communication state machine (``PR-COMM-008``, ``D-019``).

::

    COMM_HEALTHY -> RETRY -> DEGRADED -> COMM_FAULT -> RECOVERY -> COMM_HEALTHY

Communication failure must not stop local lamp operation; the state machine
only reports link health so that higher layers can decide what to do.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Tuple

from ..enums import CommState
from ..errors import IllegalTransitionError


@dataclass(frozen=True)
class CommTransition:
    from_state: CommState
    to_state: CommState
    reason: str
    at_index: int


class CommunicationStateMachine:
    """Deterministic per-link communication health state machine."""

    TRANSITIONS = {
        CommState.COMM_HEALTHY: frozenset({CommState.RETRY}),
        CommState.RETRY: frozenset({CommState.COMM_HEALTHY, CommState.DEGRADED}),
        CommState.DEGRADED: frozenset({CommState.COMM_HEALTHY, CommState.COMM_FAULT}),
        CommState.COMM_FAULT: frozenset({CommState.RECOVERY}),
        CommState.RECOVERY: frozenset({CommState.COMM_HEALTHY, CommState.COMM_FAULT}),
    }

    def __init__(self, retry_limit: int = 2) -> None:
        if retry_limit < 0:
            raise ValueError("retry_limit must be non-negative")
        self._state = CommState.COMM_HEALTHY
        self._retry_limit = retry_limit
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._history: List[CommTransition] = []

    # ------------------------------------------------------------------
    @property
    def state(self) -> CommState:
        return self._state

    @property
    def consecutive_failures(self) -> int:
        return self._consecutive_failures

    @property
    def history(self) -> Tuple[CommTransition, ...]:
        return tuple(self._history)

    # ------------------------------------------------------------------
    def record_success(self) -> CommState:
        """Record a successful exchange and advance the state machine."""
        self._consecutive_failures = 0
        self._consecutive_successes += 1

        if self._state is CommState.COMM_HEALTHY:
            return self._state
        if self._state is CommState.COMM_FAULT:
            self.begin_recovery()
            return self._state
        if self._state is CommState.RECOVERY:
            # One good exchange proves recovery; require confirmation to
            # return to COMM_HEALTHY.
            if self._consecutive_successes >= 1:
                self._move(CommState.COMM_HEALTHY, "recovery confirmed")
            return self._state
        if self._state in (CommState.RETRY, CommState.DEGRADED):
            self._move(CommState.COMM_HEALTHY, "response received")
        return self._state

    def record_failure(self) -> CommState:
        """Record a failed exchange and advance the state machine."""
        self._consecutive_successes = 0
        self._consecutive_failures += 1

        if self._state is CommState.COMM_HEALTHY:
            self._move(CommState.RETRY, "response missed")
        elif self._state is CommState.RETRY:
            if self._consecutive_failures > self._retry_limit:
                self._move(CommState.DEGRADED, "retry limit %d reached" % self._retry_limit)
        elif self._state is CommState.DEGRADED:
            self._move(CommState.COMM_FAULT, "communication fault detected")
        elif self._state is CommState.RECOVERY:
            self._move(CommState.COMM_FAULT, "recovery failed")
        return self._state

    def retry_exhausted(self) -> CommState:
        """Finish a request's configured retry budget without inventing misses."""
        if self._state is CommState.COMM_HEALTHY:
            self._move(CommState.RETRY, "request retries exhausted")
        if self._state is CommState.RETRY:
            self._move(CommState.DEGRADED, "request retry budget exhausted")
        if self._state in (CommState.DEGRADED, CommState.RECOVERY):
            self._move(CommState.COMM_FAULT, "request failed after final deadline")
        return self._state

    def begin_recovery(self) -> CommState:
        """Enter RECOVERY after a communication fault when a response arrives."""
        if self._state is CommState.COMM_FAULT:
            self._move(CommState.RECOVERY, "response received after fault")
        return self._state

    def reset(self) -> None:
        self._state = CommState.COMM_HEALTHY
        self._consecutive_failures = 0
        self._consecutive_successes = 0

    # ------------------------------------------------------------------
    def _move(self, target: CommState, reason: str) -> None:
        if target not in self.TRANSITIONS[self._state]:
            raise IllegalTransitionError(
                "illegal communication transition %s -> %s"
                % (self._state.value, target.value)
            )
        self._history.append(
            CommTransition(
                from_state=self._state,
                to_state=target,
                reason=reason,
                at_index=len(self._history),
            )
        )
        self._state = target
