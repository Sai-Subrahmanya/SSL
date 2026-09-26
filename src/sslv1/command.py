"""Command model and command lifecycle.

A command is **not** successful merely because it was received
(``PR-CONTROL-002``, ``D-017``)::

    COMMAND_CREATED -> RECEIVED -> EXECUTED -> ACKNOWLEDGED -> ACTUAL_STATE_VERIFIED

Duplicate command ids must not execute the physical action twice
(``PR-CONTROL-003``). ``RESET_ENERGY`` is carried as a ``CONTROL_COMMAND``
subtype, not as a separate command or message type (``PR-COMM-010``,
``D-038``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Callable, Dict, Mapping, Optional, Tuple

from .authorization import Actor, AuthorizationService
from .enums import (
    AuthorizationStatus,
    CommandState,
    CommandType,
    ControlSubtype,
)
from .errors import CommandError
from .identity import DeviceIdentity

@dataclass(frozen=True)
class Command:
    """An immutable command request."""

    command_id: str
    command_type: CommandType
    target: DeviceIdentity
    actor: Actor
    created_ticks: int
    subtype: Optional[ControlSubtype] = None
    parameters: Mapping[str, object] = field(default_factory=dict)
    priority: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.command_type, CommandType):
            raise CommandError("invalid command type")
        if self.subtype is not None:
            expected = {ControlSubtype.LAMP_ON: CommandType.FORCE_ON,
                        ControlSubtype.LAMP_OFF: CommandType.FORCE_OFF,
                        ControlSubtype.RETURN_TO_AUTO: CommandType.RETURN_TO_AUTO,
                        ControlSubtype.SET_MODE: CommandType.SET_MODE,
                        ControlSubtype.RESET_ENERGY: CommandType.SET_MODE}.get(self.subtype)
            if expected is None or self.command_type is not expected:
                raise CommandError("command type/subtype mismatch")
        if not self.command_id or not self.command_id.strip():
            raise CommandError("command_id must not be empty")

    @property
    def is_control_command(self) -> bool:
        return self.command_type in (CommandType.FORCE_ON, CommandType.FORCE_OFF, CommandType.RETURN_TO_AUTO) or (
            self.command_type is CommandType.SET_MODE and self.subtype is not None
        )

@dataclass
class CommandRecord:
    """Mutable lifecycle state for one command."""

    command: Command
    state: CommandState = CommandState.CREATED
    authorization_status: AuthorizationStatus = AuthorizationStatus.UNKNOWN
    received_ticks: Optional[int] = None
    executed_ticks: Optional[int] = None
    acknowledged_ticks: Optional[int] = None
    verified_ticks: Optional[int] = None
    result: str = ""
    transmitted_ticks: Optional[int] = None
    evidence: Dict[str, object] = field(default_factory=dict)
    verification_reason: str = ""

    @property
    def command_id(self) -> str:
        return self.command.command_id

    @property
    def succeeded(self) -> bool:
        return self.state is CommandState.ACTUAL_STATE_VERIFIED

class CommandLifecycle:
    """Permitted command lifecycle transitions (``PR-CONTROL-002``)."""

    TRANSITIONS: ClassVar[Dict[CommandState, frozenset]] = {
        CommandState.CREATED: frozenset(
            {CommandState.RECEIVED, CommandState.REJECTED}
        ),
        CommandState.RECEIVED: frozenset(
            {CommandState.EXECUTED, CommandState.FAILED, CommandState.REJECTED}
        ),
        CommandState.EXECUTED: frozenset(
            {CommandState.ACKNOWLEDGED, CommandState.FAILED}
        ),
        CommandState.ACKNOWLEDGED: frozenset(
            {
                CommandState.ACTUAL_STATE_VERIFIED,
                CommandState.FAILED,
            }
        ),
        CommandState.ACTUAL_STATE_VERIFIED: frozenset(),
        CommandState.REJECTED: frozenset(),
        CommandState.FAILED: frozenset(),
    }

    @classmethod
    def can_transition(cls, current: CommandState, target: CommandState) -> bool:
        return target in cls.TRANSITIONS[current]

    @classmethod
    def transition(
        cls, record: CommandRecord, target: CommandState, ticks: int, reason: str = ""
    ) -> None:
        if not cls.can_transition(record.state, target):
            raise CommandError(
                "illegal command transition %s -> %s for command %s"
                % (record.state.value, target.value, record.command_id)
            )
        record.state = target
        stamp = {
            CommandState.RECEIVED: "received_ticks",
            CommandState.EXECUTED: "executed_ticks",
            CommandState.ACKNOWLEDGED: "acknowledged_ticks",
            CommandState.ACTUAL_STATE_VERIFIED: "verified_ticks",
        }.get(target)
        if stamp is not None:
            setattr(record, stamp, ticks)
        if reason:
            if target is CommandState.ACTUAL_STATE_VERIFIED or (
                target is CommandState.FAILED and record.acknowledged_ticks is not None
            ):
                record.verification_reason = reason
            else:
                record.result = reason

#: Executes a command and returns ``(ok, reason)``.
Executor = Callable[[Command], Tuple[bool, str]]
#: Verifies the actual state after execution and returns ``(ok, reason)``.
Verifier = Callable[[Command], Tuple[Optional[bool], str]]

class CommandService:
    """Authorizes, executes and verifies commands with duplicate suppression."""

    def __init__(
        self,
        authorizer: AuthorizationService,
        executor: Executor,
        verifier: Verifier,
        on_event: Optional[Callable[[str, CommandRecord, str], None]] = None,
    ) -> None:
        self._authorizer = authorizer
        self._executor = executor
        self._verifier = verifier
        self._on_event = on_event
        self._records: Dict[str, CommandRecord] = {}

    @property
    def records(self) -> Tuple[CommandRecord, ...]:
        return tuple(self._records.values())

    def get(self, command_id: str) -> Optional[CommandRecord]:
        return self._records.get(command_id)

    def submit(self, command: Command, ticks: int, pending: bool = False) -> CommandRecord:
        """Run a command through the full lifecycle.

        Returns the existing record without re-executing when ``command_id``
        has already been processed (``PR-CONTROL-003``).
        """
        self._event_ticks = ticks
        existing = self._records.get(command.command_id)
        if existing is not None:
            prior = existing.command
            if (prior.command_type, prior.subtype, prior.target, prior.actor, prior.parameters) != (
                    command.command_type, command.subtype, command.target, command.actor, command.parameters):
                rejected = CommandRecord(command=command)
                rejected.authorization_status = self._authorizer.authorize(command.actor, _action_for(command))
                CommandLifecycle.transition(rejected, CommandState.REJECTED, ticks,
                                            "command ID conflicts with an existing request")
                self._emit("COMMAND_REJECTED", rejected, rejected.result)
                return rejected
            self._emit("COMMAND_DUPLICATE", existing, "duplicate command id ignored")
            return existing

        record = CommandRecord(command=command)
        self._records[command.command_id] = record

        # authorization
        record.authorization_status = self._authorizer.authorize(
            command.actor, _action_for(command)
        )
        if record.authorization_status is not AuthorizationStatus.AUTHORIZED:
            CommandLifecycle.transition(
                record,
                CommandState.REJECTED,
                ticks,
                "not authorized (%s)" % record.authorization_status.value,
            )
            self._emit("COMMAND_REJECTED", record, record.result)
            return record

        # receipt
        CommandLifecycle.transition(record, CommandState.RECEIVED, ticks, "received")
        self._emit("COMMAND_RECEIVED", record, "received")

        if pending:
            return record

        # execution
        ok, reason = self._executor(command)
        if not ok:
            CommandLifecycle.transition(record, CommandState.FAILED, ticks, reason)
            self._emit("COMMAND_REJECTED", record, reason)
            return record
        CommandLifecycle.transition(record, CommandState.EXECUTED, ticks, reason)
        self._emit("COMMAND_EXECUTED", record, reason)

        # acknowledgement
        CommandLifecycle.transition(record, CommandState.ACKNOWLEDGED, ticks, "acknowledged")
        self._emit("COMMAND_EXECUTED", record, "acknowledged")

        # actual-state verification
        verified, verify_reason = self._verifier(command)
        if verified is None:
            return record
        if not verified:
            CommandLifecycle.transition(record, CommandState.FAILED, ticks, verify_reason)
            self._emit(
                "COMMAND_VERIFICATION_FAILED", record, verify_reason
            )
            return record
        CommandLifecycle.transition(
            record, CommandState.ACTUAL_STATE_VERIFIED, ticks, verify_reason
        )
        self._emit("COMMAND_VERIFIED", record, verify_reason)
        return record

    def advance(self, record: CommandRecord, state: CommandState, ticks: int,
                reason: str = "") -> None:
        self._event_ticks = ticks
        CommandLifecycle.transition(record, state, ticks, reason)
        kind = {CommandState.FAILED: "COMMAND_VERIFICATION_FAILED",
                CommandState.REJECTED: "COMMAND_REJECTED",
                CommandState.ACTUAL_STATE_VERIFIED: "COMMAND_VERIFIED"}.get(
                    state, "COMMAND_EXECUTED")
        self._emit(kind, record, reason)

    def verify_pending(self, ticks: int) -> None:
        for record in self.records:
            if record.state is CommandState.ACKNOWLEDGED:
                ok, reason = self._verifier(record.command)
                if ok is not None:
                    self.advance(record, CommandState.ACTUAL_STATE_VERIFIED if ok
                                 else CommandState.FAILED, ticks, reason)

    def _emit(self, kind: str, record: CommandRecord, reason: str) -> None:
        if self._on_event is not None:
            self._on_event(kind, record, reason)

def _action_for(command: Command):
    """Map a command to the action it requires."""
    from .enums import Action

    mapping = {
        CommandType.FORCE_ON: Action.CONTROL_LAMP,
        CommandType.FORCE_OFF: Action.CONTROL_LAMP,
        CommandType.RETURN_TO_AUTO: Action.CONTROL_LAMP,
        CommandType.SET_MODE: Action.CONFIGURE,
        CommandType.READ_CONFIG: Action.VIEW_STATUS,
        CommandType.WRITE_CONFIG: Action.CONFIGURE,
        CommandType.TIME_SYNC: Action.ADMINISTER,
        CommandType.IDENTIFY: Action.VIEW_STATUS,
        CommandType.ACKNOWLEDGE_FAULT: Action.ACKNOWLEDGE_FAULT,
        CommandType.START_REPAIR: Action.START_REPAIR,
        CommandType.VERIFY_REPAIR: Action.VERIFY_REPAIR,
        CommandType.CLOSE_FAULT: Action.CLOSE_FAULT,
        CommandType.HEARTBEAT: Action.VIEW_STATUS,
    }
    if command.subtype is not None:
        return {ControlSubtype.RESET_ENERGY: Action.RESET_ENERGY,
                ControlSubtype.SET_MODE: Action.CONFIGURE,
                ControlSubtype.LAMP_ON: Action.CONTROL_LAMP,
                ControlSubtype.LAMP_OFF: Action.CONTROL_LAMP,
                ControlSubtype.RETURN_TO_AUTO: Action.CONTROL_LAMP}[command.subtype]
    return mapping[command.command_type]
