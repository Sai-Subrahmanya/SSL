"""Preliminary operator roles and abstract authorization.

Roles (``PR-SECURITY-006``, ``D-036``):

* ``VIEWER``   - read-only monitoring
* ``OPERATOR`` - normal operational control and acknowledgement
* ``ENGINEER`` - diagnostics, configuration and engineering functions
* ``ADMIN``    - system, device and configuration administration
* ``OWNER``    - highest organizational authority

The detailed permission matrix is deliberately deferred to the security
design phase (assumption ``A-27``). Authentication is represented abstractly:
this module answers "is this actor authorized for this action", never "is
this actor who they claim to be".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Mapping, Optional

from .enums import Action, AuthorizationStatus, Role
from .errors import AuthorizationError

#: Preliminary role -> permitted actions. Ordered from least to most privilege.
_ROLE_ACTIONS: Mapping[Role, frozenset] = {
    Role.VIEWER: frozenset({Action.VIEW_STATUS}),
    Role.OPERATOR: frozenset(
        {
            Action.VIEW_STATUS,
            Action.CONTROL_LAMP,
            Action.ACKNOWLEDGE_FAULT,
        }
    ),
    Role.ENGINEER: frozenset(
        {
            Action.VIEW_STATUS,
            Action.CONTROL_LAMP,
            Action.ACKNOWLEDGE_FAULT,
            Action.CONFIGURE,
            Action.RESET_ENERGY,
            Action.START_REPAIR,
            Action.VERIFY_REPAIR,
            Action.CLOSE_FAULT,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Action.VIEW_STATUS,
            Action.CONTROL_LAMP,
            Action.ACKNOWLEDGE_FAULT,
            Action.CONFIGURE,
            Action.RESET_ENERGY,
            Action.START_REPAIR,
            Action.VERIFY_REPAIR,
            Action.CLOSE_FAULT,
            Action.ADMINISTER,
            Action.DELETE_RECORD,
        }
    ),
    Role.OWNER: frozenset({action for action in Action}),
}


@dataclass(frozen=True)
class Actor:
    """An actor that can issue commands. Authentication status is abstract."""

    actor_id: str
    role: Role
    authenticated: bool = True

    def __post_init__(self) -> None:
        if not self.actor_id or not self.actor_id.strip():
            from .errors import ValidationError

            raise ValidationError("actor_id must not be empty")


def actions_for_role(role: Role) -> frozenset:
    """Return the set of actions a role is permitted to perform."""
    return _ROLE_ACTIONS[role]


class AuthorizationService:
    """Abstract authorization decisions.

    Deterministic and free of cryptography: the digital prototype must not be
    used to claim validation of security, key management or authentication
    (``PR-SECURITY-005``).
    """

    def __init__(self, extra_grants: Optional[Mapping[Role, Iterable[Action]]] = None) -> None:
        self._actions = {role: set(perms) for role, perms in _ROLE_ACTIONS.items()}
        if extra_grants:
            for role, actions in extra_grants.items():
                self._actions[role].update(actions)

    def authorize(self, actor: Actor, action: Action) -> AuthorizationStatus:
        if not actor.authenticated:
            return AuthorizationStatus.UNKNOWN
        if action in self._actions[actor.role]:
            return AuthorizationStatus.AUTHORIZED
        return AuthorizationStatus.UNAUTHORIZED

    def is_authorized(self, actor: Actor, action: Action) -> bool:
        return self.authorize(actor, action) is AuthorizationStatus.AUTHORIZED

    def require(self, actor: Actor, action: Action) -> None:
        """Raise :class:`AuthorizationError` when the action is not permitted."""
        status = self.authorize(actor, action)
        if status is not AuthorizationStatus.AUTHORIZED:
            raise AuthorizationError(
                "actor %r with role %s is not authorized for %s (status=%s)"
                % (actor.actor_id, actor.role.value, action.value, status.value)
            )
