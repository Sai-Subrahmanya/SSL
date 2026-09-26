"""Device identity and the site/group/lamp hierarchy.

Identity hierarchy (``PR-IDENTITY-001``, ``D-016``)::

    Product ID -> Site ID -> Group ID -> Lamp ID -> MCU Unique ID

Identity must be deterministic and persistent (``PR-IDENTITY-002``): the same
physical lamp node reports the same identity across restarts, and identity
does not depend on volatile state.

The RS-485 bus address is a *separate*, group-scoped value and is not a
substitute for ``lamp_id`` (``PR-IDENTITY-003``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .errors import ValidationError

#: Lowest valid RS-485 node address on a group bus.
MIN_BUS_ADDRESS = 1
#: Highest valid RS-485 node address on a group bus.
MAX_BUS_ADDRESS = 247


@dataclass(frozen=True, order=True)
class Identifier:
    """An opaque, validated identifier string.

    Identifiers are compared and hashed by value so that they are safe as
    dictionary keys and in sets.
    """

    value: str

    def __post_init__(self) -> None:
        if not isinstance(self.value, str):
            raise ValidationError("identifier must be a string")
        cleaned = self.value.strip()
        if not cleaned:
            raise ValidationError("identifier must not be empty")
        if len(cleaned) > 64:
            raise ValidationError("identifier must be at most 64 characters")
        object.__setattr__(self, "value", cleaned)

    def __str__(self) -> str:
        return self.value


def product_id(value: str) -> Identifier:
    return Identifier(value)


def site_id(value: str) -> Identifier:
    return Identifier(value)


def group_id(value: str) -> Identifier:
    return Identifier(value)


def lamp_id(value: str) -> Identifier:
    return Identifier(value)


@dataclass(frozen=True)
class McuUniqueId:
    """Silicon-level unique identifier of a node MCU.

    Modelled as an opaque byte string. The digital prototype does not depend
    on how a real MCU exposes it.
    """

    value: bytes

    def __post_init__(self) -> None:
        if not isinstance(self.value, (bytes, bytearray)):
            raise ValidationError("MCU unique id must be bytes")
        if len(self.value) == 0:
            raise ValidationError("MCU unique id must not be empty")
        object.__setattr__(self, "value", bytes(self.value))

    @property
    def hex(self) -> str:
        return self.value.hex()

    def __str__(self) -> str:
        return self.hex


@dataclass(frozen=True)
class DeviceIdentity:
    """Full identity of a device in the hierarchy.

    ``mcu_unique_id`` is optional because the Group Controller is not a lamp
    node and may not expose a lamp-node style silicon identifier in the
    digital model.
    """

    product_id: Identifier
    site_id: Identifier
    group_id: Identifier
    lamp_id: Optional[Identifier] = None
    mcu_unique_id: Optional[McuUniqueId] = None

    def with_lamp(self, lamp: Identifier) -> "DeviceIdentity":
        return DeviceIdentity(
            product_id=self.product_id,
            site_id=self.site_id,
            group_id=self.group_id,
            lamp_id=lamp,
            mcu_unique_id=self.mcu_unique_id,
        )

    @property
    def device_id(self) -> Identifier:
        """Stable identifier of the reporting device.

        For a lamp node this is the lamp id; for a group-level device it is
        the group id.
        """
        return self.lamp_id if self.lamp_id is not None else self.group_id

    def __str__(self) -> str:
        parts = [str(self.product_id), str(self.site_id), str(self.group_id)]
        if self.lamp_id is not None:
            parts.append(str(self.lamp_id))
        return "/".join(parts)


@dataclass(frozen=True)
class BusAddress:
    """A group-scoped RS-485 node address."""

    value: int

    def __post_init__(self) -> None:
        if not isinstance(self.value, int) or isinstance(self.value, bool):
            raise ValidationError("bus address must be an integer")
        if not (MIN_BUS_ADDRESS <= self.value <= MAX_BUS_ADDRESS):
            raise ValidationError(
                "bus address must be between %d and %d, got %d"
                % (MIN_BUS_ADDRESS, MAX_BUS_ADDRESS, self.value)
            )

    def __int__(self) -> int:
        return self.value

    def __str__(self) -> str:
        return str(self.value)


#: Broadcast address used for frames intended for every node on the bus.
BROADCAST_ADDRESS = 0xFF
#: Address conventionally used by the Group Controller (bus master).
MASTER_ADDRESS = 0
