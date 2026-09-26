"""Deterministic in-memory bus used by the digital prototype.

The bus models only what the *domain* needs to reason about:

* addressing (including broadcast),
* delivery and non-delivery (a silent node),
* frame corruption,
* counters for transmitted / delivered / dropped / corrupted frames.

It does **not** model electrical behaviour, propagation delay, collisions or
transceiver timing. It is not a physical RS-485 driver.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Set

from ..errors import ProtocolError
from .frame import BROADCAST_DESTINATION, Frame


class BusEndpoint:
    """Something that can be attached to the bus and receive frames."""

    def receive(self, frame: Frame) -> None:  # pragma: no cover - interface
        raise NotImplementedError


@dataclass
class BusStatistics:
    transmitted: int = 0
    delivered: int = 0
    dropped: int = 0
    corrupted: int = 0
    undeliverable: int = 0


class InMemoryBus:
    """A deterministic, fault-injectable in-memory bus."""

    def __init__(self) -> None:
        self._endpoints: Dict[int, BusEndpoint] = {}
        self._silent: Set[int] = set()
        self._corrupt_next = False
        self.stats = BusStatistics()

    # ------------------------------------------------------------------
    def attach(self, address: int, endpoint: BusEndpoint) -> None:
        if address in self._endpoints:
            raise ProtocolError("address %d is already attached to the bus" % address)
        self._endpoints[address] = endpoint

    def detach(self, address: int) -> None:
        self._endpoints.pop(address, None)

    def is_attached(self, address: int) -> bool:
        return address in self._endpoints

    # ------------------------------------------------------------------
    # fault injection
    # ------------------------------------------------------------------
    def set_silent(self, address: int, silent: bool = True) -> None:
        """Make a node stop responding (its frames are dropped by the bus)."""
        if silent:
            self._silent.add(address)
        else:
            self._silent.discard(address)

    def corrupt_next_frame(self) -> None:
        """Ask the bus to corrupt the next transmitted frame."""
        self._corrupt_next = True

    # ------------------------------------------------------------------
    def send(self, frame: Frame, sender: Optional[BusEndpoint] = None) -> bool:
        """Transmit a frame. Returns ``True`` when it was delivered."""
        self.stats.transmitted += 1

        if sender is not None and frame.source not in self._endpoints:
            raise ProtocolError("sender address %d is not attached" % frame.source)

        wire = frame.encode()
        if self._corrupt_next:
            self._corrupt_next = False
            self.stats.corrupted += 1
            corrupted = bytearray(wire)
            corrupted[-1] ^= 0xFF  # break the CRC
            wire = bytes(corrupted)

        destinations = self._resolve_destinations(frame.destination)
        if not destinations:
            self.stats.undeliverable += 1
            return False

        delivered_any = False
        for address in destinations:
            if address in self._silent:
                self.stats.dropped += 1
                continue
            self._endpoints[address].receive(_decode(wire))
            self.stats.delivered += 1
            delivered_any = True
        return delivered_any

    def _resolve_destinations(self, destination: int):
        if destination == BROADCAST_DESTINATION:
            return sorted(self._endpoints)
        if destination not in self._endpoints:
            return []
        return [destination]

    # ------------------------------------------------------------------
    def reset_statistics(self) -> None:
        self.stats = BusStatistics()


def _decode(wire: bytes) -> Frame:
    from .frame import decode_frame

    return decode_frame(wire)
