"""Command lifecycle tests (PR-CONTROL-002, PR-CONTROL-003, PR-COMM-010).

Covers: command lifecycle, duplicate command suppression, unauthorized
commands and energy-reset authorization.
"""


import pytest

from sslv1.command import Command, CommandLifecycle, CommandService
from sslv1.enums import (
    Action,
    AuthorizationStatus,
    CommandState,
    CommandType,
    ControlSubtype,
    Role,
)
from sslv1.errors import AuthorizationError, CommandError
from sslv1.authorization import Actor, AuthorizationService

from conftest import healthy_sources


# --------------------------------------------------------------------------
# 12. command lifecycle
# --------------------------------------------------------------------------
def test_command_lifecycle_reaches_actual_state_verified(lamp_node, operator):
    record = lamp_node.force_on(operator, ticks=1000)
    assert record.state is CommandState.ACKNOWLEDGED
    assert not record.succeeded
    lamp_node.step(healthy_sources(), ticks=2000)
    assert record.state is CommandState.ACTUAL_STATE_VERIFIED
    assert record.received_ticks == 1000
    assert record.executed_ticks == 1000
    assert record.acknowledged_ticks == 1000
    assert record.verified_ticks == 2000
    assert record.succeeded is True


def test_receipt_alone_is_not_success():
    """A command that is received but fails verification is not a success."""
    authorizer = AuthorizationService()
    service = CommandService(
        authorizer=authorizer,
        executor=lambda command: (True, "executed"),
        verifier=lambda command: (False, "actual state did not follow"),
    )
    command = Command(
        command_id="c-receipt",
        command_type=CommandType.FORCE_ON,
        target=lamp_target(),
        actor=Actor("a", Role.OPERATOR),
        created_ticks=0,
    )
    record = service.submit(command, ticks=10)
    assert record.state is CommandState.RECEIVED or record.state is CommandState.FAILED
    assert record.state is not CommandState.ACTUAL_STATE_VERIFIED
    assert record.succeeded is False
    assert record.received_ticks == 10
    assert record.verified_ticks is None


def test_illegal_command_transition_is_rejected():
    from sslv1.command import CommandRecord

    command = Command(
        command_id="c-1",
        command_type=CommandType.FORCE_ON,
        target=lamp_target(),
        actor=Actor("a", Role.OPERATOR),
        created_ticks=0,
    )
    record = CommandRecord(command=command, state=CommandState.ACTUAL_STATE_VERIFIED)
    assert CommandLifecycle.can_transition(
        CommandState.ACTUAL_STATE_VERIFIED, CommandState.EXECUTED
    ) is False
    with pytest.raises(CommandError):
        CommandLifecycle.transition(record, CommandState.EXECUTED, 1)


def lamp_target():
    from sslv1.identity import DeviceIdentity, Identifier

    return DeviceIdentity(
        product_id=Identifier("P"), site_id=Identifier("S"),
        group_id=Identifier("G"), lamp_id=Identifier("L"),
    )


# --------------------------------------------------------------------------
# 13. duplicate command
# --------------------------------------------------------------------------
def test_duplicate_command_is_not_executed_twice(lamp_node, operator):
    first = lamp_node.force_on(operator, ticks=1000)
    assert not first.succeeded
    lamp_node.step(healthy_sources(), ticks=1500)
    assert first.succeeded is True

    # Same command id submitted again: must not re-execute the action.
    from sslv1.command import Command

    duplicate = Command(
        command_id=first.command_id,
        command_type=CommandType.FORCE_ON,
        target=lamp_node.identity,
        actor=operator,
        created_ticks=2000,
    )
    second = lamp_node.commands.submit(duplicate, ticks=2000)

    assert second is first
    assert second.state is CommandState.ACTUAL_STATE_VERIFIED
    assert second.executed_ticks == 1000  # unchanged
    assert any(
        e.event_type.value == "COMMAND_DUPLICATE" for e in lamp_node.events
    )


def test_duplicate_command_does_not_toggle_the_lamp(lamp_node, operator):
    """A retried FORCE_OFF must not switch an already-OFF lamp back ON."""
    lamp_node.step(healthy_sources(light_level=10.0), ticks=1000)
    lamp_node.force_off(operator, ticks=2000)
    assert lamp_node.control.lamp_is_on is False

    from sslv1.command import Command

    duplicate = Command(
        command_id="dup-toggle",
        command_type=CommandType.FORCE_OFF,
        target=lamp_node.identity,
        actor=operator,
        created_ticks=3000,
    )
    lamp_node.commands.submit(duplicate, ticks=3000)
    lamp_node.commands.submit(duplicate, ticks=4000)
    assert lamp_node.control.lamp_is_on is False


def test_command_service_reports_execution_failure():
    authorizer = AuthorizationService()
    service = CommandService(
        authorizer=authorizer,
        executor=lambda command: (False, "actuator busy"),
        verifier=lambda command: (True, "ok"),
    )
    command = Command(
        command_id="c-fail",
        command_type=CommandType.FORCE_ON,
        target=lamp_target(),
        actor=Actor("a", Role.OPERATOR),
        created_ticks=0,
    )
    record = service.submit(command, ticks=10)
    assert record.state is CommandState.FAILED
    assert record.result == "actuator busy"


def test_command_service_reports_verification_failure():
    authorizer = AuthorizationService()
    service = CommandService(
        authorizer=authorizer,
        executor=lambda command: (True, "executed"),
        verifier=lambda command: (False, "actual state did not follow"),
    )
    command = Command(
        command_id="c-verify",
        command_type=CommandType.FORCE_ON,
        target=lamp_target(),
        actor=Actor("a", Role.OPERATOR),
        created_ticks=0,
    )
    record = service.submit(command, ticks=10)
    assert record.state is CommandState.FAILED
    assert record.verification_reason == "actual state did not follow"


# --------------------------------------------------------------------------
# 14. unauthorized command
# --------------------------------------------------------------------------
def test_unauthorized_operator_cannot_force_the_lamp(lamp_node, viewer):
    record = lamp_node.force_on(viewer, ticks=1000)
    assert record.state is CommandState.REJECTED
    assert record.authorization_status is AuthorizationStatus.UNAUTHORIZED
    assert lamp_node.control.active_override.value == "NONE"


def test_unauthenticated_actor_is_rejected(lamp_node):
    ghost = Actor(actor_id="ghost", role=Role.OWNER, authenticated=False)
    record = lamp_node.force_on(ghost, ticks=1000)
    assert record.state is CommandState.REJECTED
    assert record.authorization_status is AuthorizationStatus.UNKNOWN


def test_rejected_command_is_audited(lamp_node, viewer):
    lamp_node.force_on(viewer, ticks=1000)
    rejected = [
        e for e in lamp_node.events if e.event_type.value == "COMMAND_REJECTED"
    ]
    assert rejected
    assert "viewer-01" in rejected[0].reason


# --------------------------------------------------------------------------
# RESET_ENERGY as a CONTROL_COMMAND subtype
# --------------------------------------------------------------------------
def test_energy_reset_requires_authorization(lamp_node, operator, engineer):
    from sslv1.enums import LampState as LS
    from sslv1.nodes import LampNodeSources

    for index in range(3):
        lamp_node.step(
            LampNodeSources(voltage=230.0, current=0.45, power=103.5, light_level=10.0,
                            switching_feedback=LS.ON),
            ticks=1000 * (index + 1),
        )
    assert lamp_node._energy > 0.0

    denied = lamp_node.reset_energy(operator, ticks=10_000)
    assert denied.state is CommandState.REJECTED
    assert lamp_node._energy > 0.0

    allowed = lamp_node.reset_energy(engineer, ticks=11_000)
    assert allowed.succeeded is True
    assert lamp_node._energy == 0.0
    assert any(e.event_type.value == "ENERGY_RESET" for e in lamp_node.events)


def test_reset_energy_is_a_control_subtype_not_a_message_type():
    """RESET_ENERGY must not appear as an RS-485 message type."""
    from sslv1.enums import MessageType

    assert ControlSubtype.RESET_ENERGY.value == "RESET_ENERGY"
    assert "RESET_ENERGY" not in [m.value for m in MessageType]
    assert len(list(MessageType)) == 17


def test_authorization_roles_cover_the_expected_actions():
    authorizer = AuthorizationService()
    assert authorizer.is_authorized(Actor("v", Role.VIEWER), Action.VIEW_STATUS)
    assert not authorizer.is_authorized(Actor("v", Role.VIEWER), Action.CONTROL_LAMP)
    assert authorizer.is_authorized(Actor("o", Role.OPERATOR), Action.CONTROL_LAMP)
    assert authorizer.is_authorized(Actor("o", Role.OPERATOR), Action.ACKNOWLEDGE_FAULT)
    assert not authorizer.is_authorized(Actor("o", Role.OPERATOR), Action.CONFIGURE)
    assert authorizer.is_authorized(Actor("e", Role.ENGINEER), Action.CONFIGURE)
    assert authorizer.is_authorized(Actor("e", Role.ENGINEER), Action.RESET_ENERGY)
    assert authorizer.is_authorized(Actor("a", Role.ADMIN), Action.DELETE_RECORD)
    assert authorizer.is_authorized(Actor("ow", Role.OWNER), Action.ADMINISTER)
    with pytest.raises(AuthorizationError):
        authorizer.require(Actor("v", Role.VIEWER), Action.ADMINISTER)
