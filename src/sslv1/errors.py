"""Domain-level exceptions.

Domain errors are raised for *programming* and *policy* violations, never for
physical conditions. They allow callers (simulation or hardware abstraction)
to convert a violation into an event rather than crashing the node.
"""

from __future__ import annotations


class SSLError(Exception):
    """Base class for all Smart Street Light V1 domain errors."""


class ValidationError(SSLError):
    """A value, configuration or transition failed validation."""


class ConfigurationError(ValidationError):
    """A configuration value or combination of values is invalid."""


class IllegalTransitionError(SSLError):
    """A state machine transition is not permitted."""


class CommandError(SSLError):
    """A command could not be created, authorized or executed."""


class AuthorizationError(SSLError):
    """An actor is not authorized to perform an action."""


class StorageError(SSLError):
    """A storage operation failed."""


class StorageFullError(StorageError):
    """The store cannot accept another record.

    The condition must be surfaced explicitly; records are never silently
    dropped (``PR-STORAGE-006``).
    """


class ProtocolError(SSLError):
    """A frame or payload could not be encoded, decoded or validated."""


class IntegrityError(ProtocolError):
    """A frame or record failed its CRC/integrity check."""
