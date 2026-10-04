"""Deterministic fault-injection harness for the Smart Street Light V1 prototype.

This module is **test support**, not production code: it builds a group of
simulated lamp nodes and a Group Controller on the in-memory bus and injects
one defined fault at a time. It contains no randomness, no wall-clock access
and no hardware dependency, so every injected scenario is reproducible from
its inputs alone.

The harness does not bypass the domain layer. Sensor and electrical faults are
injected as *readings* (:class:`~sslv1.nodes.LampNodeSources`), link faults go
through the documented bus hooks (:class:`~sslv1.comm.InMemoryBus`), and
storage faults use the documented store hooks. Every injection is counted so a
test can prove the fault was actually applied instead of silently doing
nothing.

Phase 14 scope: this exercises the digital model only. It does not validate
electrical safety, EMC/RF behaviour, relay or surge performance, IP rating,
mains wiring or physical RTC retention.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Sequence, Tuple

from conftest import GROUP, PRODUCT, SITE, healthy_sources, make_lamp_config
from sslv1.authorization import Actor, AuthorizationService
from sslv1.comm import Frame, InMemoryBus, MessageType
from sslv1.control import ControlDecision
from sslv1.enums import (
    ControllerStatus,
    LampState,
    Role,
    SensorStatus,
)
from sslv1.errors import ProtocolError
from sslv1.identity import BusAddress, DeviceIdentity, Identifier
from sslv1.nodes import (
    GroupController,
    GroupControllerConfig,
    InMemoryUpstreamLink,
    LampNode,
    LampNodeSources,
)
from sslv1.storage import StorageRecord
from sslv1.time_model import LogicalClock

#: Logical ticks per second used by every Phase 14 scenario.
TICKS_PER_SECOND = 1000

OPERATOR = Actor("operator-01", Role.OPERATOR)
ENGINEER = Actor("engineer-01", Role.ENGINEER)
ADMIN = Actor("admin-01", Role.ADMIN)
VIEWER = Actor("viewer-01", Role.VIEWER)


# ---------------------------------------------------------------------------
# Evidence injectors (category 1-3: sensor, electrical, switching feedback)
# ---------------------------------------------------------------------------
def light_missing() -> LampNodeSources:
    """A missing light measurement with the sensor still reported valid."""
    return healthy_sources(light_level=None)


def light_invalid() -> LampNodeSources:
    """A light sensor that reports invalid status."""
    return healthy_sources(sensor_status=SensorStatus.INVALID)


def light_nonfinite() -> LampNodeSources:
    """A non-finite light measurement."""
    return healthy_sources(light_level=float("nan"))


def light_out_of_range() -> LampNodeSources:
    """A light measurement outside the configured sensor range."""
    return healthy_sources(light_level=1_000_000.0)


def light_dead_band(level: float = 100.0) -> LampNodeSources:
    """A light level inside the hysteresis dead band (no decision input)."""
    return healthy_sources(light_level=level)


def light_oscillating() -> List[LampNodeSources]:
    """A sensor oscillating around the threshold (dark,bright,dark,bright...).

    Each sample carries switching feedback that matches the state the lamp
    would be commanded into, so the only variable under test is the light
    evidence itself. Oscillation must not create one independent lamp-health
    alert per crossing (``PR-FAULT-006``).
    """
    return [DARK, healthy_sources(light_level=900.0, switching_feedback=LampState.OFF,
                                  current=0.0, power=0.0)] * 3


def under_current() -> LampNodeSources:
    """Current below the expected band but above the near-zero threshold."""
    return healthy_sources(current=0.10, power=23.0)


def open_load() -> LampNodeSources:
    """Commanded ON, switching path ON, no current at all."""
    return healthy_sources(current=0.0, power=0.0)


def over_current() -> LampNodeSources:
    """Current above the configured maximum."""
    return healthy_sources(current=1.8, power=414.0)


def unexpected_current() -> LampNodeSources:
    """Current while the lamp is commanded and reported OFF."""
    return healthy_sources(current=0.45, power=103.5,
                           switching_feedback=LampState.OFF)


def inconsistent_power() -> LampNodeSources:
    """Voltage, current and power that cannot all be true together."""
    return healthy_sources(current=0.45, power=350.0)


def electrical_missing() -> LampNodeSources:
    """No electrical evidence at all (voltage, current, power absent)."""
    return healthy_sources(voltage=None, current=None, power=None)


def electrical_nonfinite() -> LampNodeSources:
    """A non-finite electrical reading."""
    return healthy_sources(current=float("inf"))


def supply_abnormal() -> LampNodeSources:
    """Supply voltage outside the configured band while commanded ON."""
    return healthy_sources(voltage=150.0)


def feedback_off_while_commanded_on() -> LampNodeSources:
    """Commanded ON but the switching path reports OFF."""
    return healthy_sources(switching_feedback=LampState.OFF, current=0.0, power=0.0)


def feedback_on_while_commanded_off() -> LampNodeSources:
    """Commanded OFF (bright ambient light) but the path still reports ON."""
    return healthy_sources(light_level=900.0, switching_feedback=LampState.ON,
                           current=0.45, power=103.5)


def commanded_off_calm() -> LampNodeSources:
    """Commanded OFF with matching feedback and no current (override baseline)."""
    return healthy_sources(light_level=10.0, switching_feedback=LampState.OFF,
                           current=0.0, power=0.0)


def feedback_unknown() -> LampNodeSources:
    """Switching feedback cannot be read."""
    return healthy_sources(switching_feedback=LampState.UNKNOWN)


def controller_fault() -> LampNodeSources:
    """The node controller itself reports a fault."""
    return healthy_sources(controller_status=ControllerStatus.FAULT)


DARK = healthy_sources(light_level=10.0)
BRIGHT = healthy_sources(light_level=900.0)


# ---------------------------------------------------------------------------
# Injectable upstream link (category 11: store-and-forward)
# ---------------------------------------------------------------------------
class FaultyUpstreamLink(InMemoryUpstreamLink):
    """Upstream link with deterministic, injectable confirmation loss.

    ``lose_confirmations`` makes the next N uploads report failure *after* the
    remote side has received the record, which is exactly the lost-response
    case: the sender cannot know the record arrived, so it must keep the
    record pending and retry rather than silently drop it.
    """

    def __init__(self, available: bool = True) -> None:
        super().__init__(available=available)
        self.received: List[int] = []
        self.lose_confirmations = 0
        self.confirmations_lost = 0

    def upload(self, record: StorageRecord) -> bool:
        if not self.available():
            self.failed.append(record.sequence_number)
            return False
        self.received.append(record.sequence_number)
        if self.lose_confirmations > 0:
            self.lose_confirmations -= 1
            self.confirmations_lost += 1
            return False
        self.uploaded.append(record.sequence_number)
        return True


@dataclass
class InjectionLog:
    """Counts of faults actually applied by the harness."""

    requests_dropped: int = 0
    responses_dropped: int = 0
    corrupted_frames: int = 0
    malformed_frames: int = 0
    capture_replays: int = 0

    @property
    def total(self) -> int:
        return (self.requests_dropped + self.responses_dropped
                + self.corrupted_frames + self.malformed_frames)


# ---------------------------------------------------------------------------
# Group simulation harness
# ---------------------------------------------------------------------------
class GroupSim:
    """A deterministic 1..16 node group with injectable faults."""

    def __init__(
        self,
        node_count: int = 1,
        storage_capacity: Optional[int] = None,
        group_storage_capacity: Optional[int] = None,
        upstream: Optional[FaultyUpstreamLink] = None,
        lamp_config_overrides: Optional[Dict[str, object]] = None,
    ) -> None:
        if not 1 <= node_count <= 16:
            raise ValueError("the digital prototype models groups of 1..16 nodes")
        self.clock = LogicalClock()
        self.bus = InMemoryBus()
        self.authorizer = AuthorizationService()
        self.upstream = upstream if upstream is not None else FaultyUpstreamLink()
        self.injections = InjectionLog()
        self._captured: List[Frame] = []

        self.nodes: List[LampNode] = []
        for index in range(node_count):
            address = index + 1
            lamp_id = Identifier("LAMP-%02d" % address)
            identity = DeviceIdentity(
                product_id=PRODUCT, site_id=SITE, group_id=GROUP, lamp_id=lamp_id
            )
            config = make_lamp_config(
                lamp_id, bus_address=address, **(lamp_config_overrides or {})
            )
            node = LampNode(
                identity,
                BusAddress(address),
                config,
                clock=self.clock,
                bus=self.bus,
                authorizer=self.authorizer,
                storage_capacity=storage_capacity,
            )
            node.start()
            self.nodes.append(node)

        self.gc = GroupController(
            identity=DeviceIdentity(product_id=PRODUCT, site_id=SITE, group_id=GROUP),
            config=GroupControllerConfig(
                max_nodes=16, storage_capacity=group_storage_capacity
            ),
            clock=self.clock,
            bus=self.bus,
            upstream=self.upstream,
            authorizer=self.authorizer,
        )
        for node in self.nodes:
            self.gc.register_node(node.lamp_id, node.bus_address)

    # -- node access -------------------------------------------------------
    @property
    def node(self) -> LampNode:
        return self.nodes[0]

    def node_for(self, address: int) -> LampNode:
        return self.nodes[address - 1]

    def registration(self, node: LampNode):
        return self.gc.registration_for(node.lamp_id)

    def comm_state(self, node: LampNode):
        return self.registration(node).comm.state

    def active_faults(self, node: LampNode):
        return node.faults.active_faults

    def events_of(self, node: LampNode, event_type) -> list:
        return [e for e in node.events if e.event_type is event_type]

    # -- time and control cycles -------------------------------------------
    def step(
        self,
        node: LampNode = None,
        sources: Optional[LampNodeSources] = None,
        ticks: Optional[int] = None,
        **source_overrides,
    ) -> ControlDecision:
        """Run one control cycle on one node with healthy readings by default."""
        node = node if node is not None else self.nodes[0]
        if sources is None:
            sources = healthy_sources(**source_overrides)
        elif source_overrides:
            raise ValueError("pass either a source reading set or overrides")
        if ticks is None:
            ticks = self.clock.ticks + node.config.measurement_interval_ticks
        return node.step(sources, ticks=ticks)

    def step_all(self, ticks: Optional[int] = None, **source_overrides) -> None:
        """Run one control cycle on every node at the same logical tick."""
        for index, node in enumerate(self.nodes):
            moment = ticks if ticks is not None else self.clock.ticks + TICKS_PER_SECOND
            self.step(node, ticks=moment + index, **source_overrides)

    def advance(self, ticks: int) -> int:
        return self.clock.advance(ticks)

    # -- traffic ------------------------------------------------------------
    def deliver(
        self,
        corrupt: int = 0,
        drop: int = 0,
        malformed: int = 0,
    ) -> int:
        """Pump every queued node response toward the Group Controller.

        ``drop`` discards the first N responses (lost replies), ``corrupt``
        makes them fail their CRC on the wire (the receiver never sees them,
        ``PR-COMM-006``), and ``malformed`` rewrites the payload of the first
        N responses into bytes that cannot be decoded. Returns how many frames
        were delivered.
        """
        delivered = 0
        dropped = malformed_sent = corrupted = 0
        for node in self.nodes:
            for frame in node.process_incoming():
                if dropped < drop:
                    dropped += 1
                    self.injections.responses_dropped += 1
                    continue
                if malformed_sent < malformed:
                    frame = replace(frame, payload=b"\x00\x01\x02")
                    malformed_sent += 1
                    self.injections.malformed_frames += 1
                if corrupted < corrupt:
                    self.bus.corrupt_next_frame()
                    corrupted += 1
                try:
                    if self.bus.send(frame):
                        delivered += 1
                except ProtocolError:
                    # Corrupted on the wire: detected by the CRC check and
                    # never handed to a receiver.
                    self.injections.corrupted_frames += 1
        self.gc.collect_responses()
        return delivered

    def capture(self) -> Tuple[Frame, ...]:
        """Take queued node responses off the bus without delivering them."""
        captured = []
        for node in self.nodes:
            captured.extend(node.process_incoming())
        self._captured.extend(captured)
        return tuple(captured)

    def replay(self, frames: Sequence[Frame], corrupt: int = 0) -> int:
        """Deliver previously captured frames to the Group Controller."""
        delivered = 0
        corrupted = 0
        for frame in frames:
            if corrupted < corrupt:
                self.bus.corrupt_next_frame()
                corrupted += 1
            try:
                if self.bus.send(frame):
                    delivered += 1
            except ProtocolError:
                self.injections.corrupted_frames += 1
        self.injections.capture_replays += 1
        self.gc.collect_responses()
        return delivered

    def poll(self, message_type: MessageType = MessageType.STATUS_REQUEST,
             drop_request_to: Optional[int] = None) -> Dict[int, bool]:
        """Poll the group, optionally dropping the request to one address."""
        if drop_request_to is None:
            return self.gc.poll(message_type)
        self.bus.set_silent(drop_request_to, True)
        try:
            before = self.bus.stats.dropped
            result = self.gc.poll(message_type)
            if self.bus.stats.dropped > before:
                self.injections.requests_dropped += 1
            return result
        finally:
            self.bus.set_silent(drop_request_to, False)

    def silence(self, address: int, silent: bool = True) -> None:
        """Make the bus stop delivering frames addressed to ``address``."""
        self.bus.set_silent(address, silent)

    def rounds(
        self,
        count: int,
        message_type: MessageType = MessageType.STATUS_REQUEST,
        ticks_per_round: Optional[int] = None,
        drop_request_to: Optional[int] = None,
        **node_overrides,
    ) -> None:
        """Run ``count`` deterministic poll rounds, pumping node responses."""
        interval = ticks_per_round if ticks_per_round else TICKS_PER_SECOND
        for _ in range(count):
            self.clock.advance(interval)
            self.poll(message_type, drop_request_to=drop_request_to)
            self.deliver()
            if node_overrides:
                self.step_all(self.clock.ticks + TICKS_PER_SECOND, **node_overrides)

    def service_timeouts(self) -> None:
        self.gc.service_timeouts()

    # -- upstream -----------------------------------------------------------
    def upstream_down(self) -> None:
        self.upstream.set_available(False)

    def upstream_up(self) -> None:
        self.upstream.set_available(True)

    # -- commands -----------------------------------------------------------
    def forward(self, subtype, actor: Actor = ENGINEER, node: Optional[LampNode] = None,
                command_id: Optional[str] = None, parameter: int = 0):
        node = node if node is not None else self.nodes[0]
        return self.gc.forward_control(
            node.lamp_id, subtype, actor, command_id=command_id, parameter=parameter
        )


def driven(sim: GroupSim, node: LampNode, sources, count: int,
           step_ticks: int = TICKS_PER_SECOND, start_ticks: int = 0):
    """Apply ``count`` consecutive observations of ``sources`` to one node."""
    for index in range(count):
        sim.step(node, sources=sources, ticks=start_ticks + (index + 1) * step_ticks)


def confirmed_fault(node: LampNode, count: Optional[int] = None, step_ticks: int = TICKS_PER_SECOND):
    """Drive one node to a confirmed fault with deterministic observations."""
    total = count if count is not None else node.config.fault_confirmation_count
    for index in range(total):
        node.step(open_load(), ticks=(index + 1) * step_ticks)
    faults = [f for f in node.faults.active_faults if f.is_confirmed]
    if not faults:
        raise AssertionError("expected a confirmed fault")
    return faults[0]


__all__ = [
    "ADMIN", "BRIGHT", "DARK", "ENGINEER", "FaultyUpstreamLink", "GroupSim",
    "InjectionLog", "OPERATOR", "TICKS_PER_SECOND", "VIEWER",
    "commanded_off_calm", "confirmed_fault", "controller_fault", "driven", "electrical_missing",
    "electrical_nonfinite", "feedback_off_while_commanded_on",
    "feedback_on_while_commanded_off", "feedback_unknown", "inconsistent_power",
    "light_dead_band", "light_invalid", "light_missing", "light_nonfinite",
    "light_oscillating", "light_out_of_range", "open_load", "over_current",
    "supply_abnormal", "under_current", "unexpected_current",
]
