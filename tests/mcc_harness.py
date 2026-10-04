"""Deterministic multi-site, multi-group harness for the Phase 15 MCC tests.

Builds a complete digital system under one Master Control Center::

    MccSim
     +-- site (1..N)
          +-- bus + GroupController + 1..N LampNodes  (one group each)

Every device shares one :class:`~sslv1.time_model.LogicalClock` and one
:class:`~sslv1.authorization.AuthorizationService`, because the MCC data layer
compares timestamps and the tests compare authorization outcomes across the
whole system. Nothing here talks to hardware, reads a wall clock or uses
randomness: the same script always produces the same states.

The harness only *pumps* traffic (nodes answer, the group controller collects)
and injects conditions (silent lamp, unavailable upstream link, readings).
Domain decisions stay in the modules under test.
"""

from __future__ import annotations

from typing import Callable, Dict, Optional, Tuple

from fault_injection import FaultyUpstreamLink
from conftest import PRODUCT, healthy_sources, make_lamp_config
from sslv1.authorization import AuthorizationService
from sslv1.comm import InMemoryBus, MessageType
from sslv1.control import ControlDecision
from sslv1.identity import BusAddress, DeviceIdentity, Identifier
from sslv1.mcc import MasterControlCenter, MasterControlCenterConfig
from sslv1.nodes import (
    GroupController,
    GroupControllerConfig,
    LampNode,
    LampNodeSources,
    UpstreamLink,
)
from sslv1.time_model import LogicalClock

#: Logical ticks per second used by every Phase 15 scenario.
TICKS_PER_SECOND = 1000

#: A 16-lamp group, the documented initial target (``PR-SCALABILITY-001``).
LAMPS_PER_GROUP = 16


def ident(value) -> Identifier:
    """Accept an :class:`Identifier` or a plain string, as the MCC does."""
    if isinstance(value, Identifier):
        return value
    return Identifier(str(value))


def group_identifier(index: int) -> Identifier:
    """``GRP-01``, ``GRP-02`` ... deterministic per index."""
    return Identifier("GRP-%02d" % index)


def site_identifier(index: int) -> Identifier:
    """``SITE-A``, ``SITE-B`` ... deterministic per index."""
    return Identifier("SITE-%s" % chr(ord("A") + index))


class MccSim:
    """A deterministic site/group/lamp system under one MCC."""

    def __init__(
        self,
        site_count: int = 1,
        group_count: int = 1,
        lamps_per_group: int = LAMPS_PER_GROUP,
        storage_capacity: Optional[int] = None,
        group_storage_capacity: Optional[int] = None,
        lamp_config_overrides: Optional[Dict[str, object]] = None,
        status_max_age_ticks: Optional[int] = None,
        upstream_factory: Optional[
            Callable[["MasterControlCenter", Identifier, Identifier], UpstreamLink]
        ] = None,
    ) -> None:
        if min(site_count, group_count, lamps_per_group) < 1:
            raise ValueError("a simulation needs at least one site, group and lamp")
        self.clock = LogicalClock()
        self.authorizer = AuthorizationService()
        self.mcc = MasterControlCenter(
            config=MasterControlCenterConfig(status_max_age_ticks=status_max_age_ticks),
            clock=self.clock,
        )
        self._buses: Dict[Tuple[Identifier, Identifier], InMemoryBus] = {}
        self._controllers: Dict[Tuple[Identifier, Identifier], GroupController] = {}
        self._upstreams: Dict[Tuple[Identifier, Identifier], UpstreamLink] = {}
        self._lamps: Dict[Tuple[Identifier, Identifier, Identifier], LampNode] = {}
        self._silent: Dict[Tuple[Identifier, Identifier, Identifier], bool] = {}
        #: Builds the upstream link of one group, called as
        #: ``factory(mcc, site, group)`` while the groups are being built. The
        #: default is the injectable Phase 14 link; the Phase 16 integration
        #: tests pass ``lambda mcc, site, group: MccUpstreamLink(...)`` so the
        #: MCC itself is the other end of every upload.
        self._upstream_factory = upstream_factory

        for site_index in range(site_count):
            site = site_identifier(site_index)
            self.mcc.create_site(site)
            for group_index in range(1, group_count + 1):
                group = group_identifier(group_index)
                self._build_group(
                    site, group, lamps_per_group, storage_capacity,
                    group_storage_capacity, lamp_config_overrides or {},
                )

    # ------------------------------------------------------------------
    def _build_group(self, site, group, lamps_per_group, storage_capacity,
                     group_storage_capacity, lamp_config_overrides) -> None:
        bus = InMemoryBus()
        upstream = (
            self._upstream_factory(self.mcc, site, group)
            if self._upstream_factory is not None
            else FaultyUpstreamLink()
        )
        controller = GroupController(
            identity=DeviceIdentity(product_id=PRODUCT, site_id=site, group_id=group),
            config=GroupControllerConfig(
                max_nodes=max(lamps_per_group, 16),
                storage_capacity=group_storage_capacity,
            ),
            clock=self.clock,
            bus=bus,
            upstream=upstream,
            authorizer=self.authorizer,
        )
        key = (site, group)
        self._buses[key] = bus
        self._upstreams[key] = upstream
        self._controllers[key] = controller
        self.mcc.register_group(site, group, controller)

        for index in range(1, lamps_per_group + 1):
            address = index
            lamp = Identifier("LAMP-%02d" % address)
            identity = DeviceIdentity(
                product_id=PRODUCT, site_id=site, group_id=group, lamp_id=lamp
            )
            config = make_lamp_config(
                lamp, bus_address=address, site_id=site, group_id=group,
                **lamp_config_overrides
            )
            node = LampNode(
                identity=identity,
                bus_address=BusAddress(address),
                config=config,
                clock=self.clock,
                bus=bus,
                authorizer=self.authorizer,
                storage_capacity=storage_capacity,
            )
            node.start(ticks=1)
            self._lamps[(site, group, lamp)] = node
            self.mcc.register_lamp(site, group, node)

    # ------------------------------------------------------------------
    # accessors
    # ------------------------------------------------------------------
    @property
    def site(self) -> Identifier:
        return self.mcc.sites[0].site_id

    def gc(self, site: Identifier, group: Identifier) -> GroupController:
        return self._controllers[(ident(site), ident(group))]

    def bus(self, site: Identifier, group: Identifier) -> InMemoryBus:
        return self._buses[(ident(site), ident(group))]

    def upstream(self, site: Identifier, group: Identifier) -> UpstreamLink:
        return self._upstreams[(ident(site), ident(group))]

    def node(self, site: Identifier, group: Identifier, lamp) -> LampNode:
        return self._lamps[(ident(site), ident(group), ident(lamp))]

    def nodes(self, site: Identifier, group: Identifier) -> Tuple[LampNode, ...]:
        key = (ident(site), ident(group))
        return tuple(
            node for (node_site, node_group, _), node in sorted(self._lamps.items())
            if (node_site, node_group) == key
        )

    def lamp_ids(self, site: Identifier, group: Identifier) -> Tuple[Identifier, ...]:
        key = (ident(site), ident(group))
        return tuple(lamp for (lamp_site, lamp_group, lamp) in sorted(self._lamps)
                     if (lamp_site, lamp_group) == key)

    # ------------------------------------------------------------------
    # time and traffic
    # ------------------------------------------------------------------
    def advance(self, ticks: int) -> int:
        return self.clock.advance(ticks)

    def step(
        self,
        site: Identifier,
        group: Identifier,
        lamp,
        sources: Optional[LampNodeSources] = None,
        ticks: Optional[int] = None,
        **overrides,
    ) -> ControlDecision:
        """Run one control cycle on one lamp with healthy readings by default."""
        node = self.node(site, group, lamp)
        if sources is None:
            sources = healthy_sources(**overrides)
        elif overrides:
            raise ValueError("pass either a reading set or overrides")
        return node.step(sources, ticks=ticks)

    def step_group(
        self, site: Identifier, group: Identifier, ticks: Optional[int] = None, **overrides
    ) -> None:
        """Run one control cycle on every lamp of one group.

        The shared clock only moves forward, so ``ticks`` is a start moment and
        each lamp is stepped one tick later than the previous one.
        """
        base = ticks if ticks is not None else self.clock.ticks + TICKS_PER_SECOND
        for index, node in enumerate(self.nodes(site, group)):
            if self._silent.get((ident(site), ident(group), node.lamp_id)):
                continue
            moment = max(base, self.clock.ticks) + index
            node.step(healthy_sources(**overrides), ticks=moment)

    def pump(self, site: Identifier, group: Identifier) -> int:
        """Deliver every queued node response to the group controller."""
        sent = 0
        for node in self.nodes(site, group):
            frames = [] if self._silent.get((ident(site), ident(group), node.lamp_id)) else (
                node.process_incoming()
            )
            for frame in frames:
                self.bus(site, group).send(frame)
                sent += 1
        return sent

    def round(
        self,
        site: Identifier,
        group: Identifier,
        message_type: MessageType = MessageType.MEASUREMENT_REQUEST,
        ticks: Optional[int] = None,
    ) -> None:
        """One complete poll exchange: advance, poll, answer, collect."""
        self.advance(ticks if ticks is not None else TICKS_PER_SECOND)
        self.gc(site, group).poll(message_type)
        self.pump(site, group)
        self.gc(site, group).collect_responses()

    def rounds(
        self,
        count: int = 1,
        message_type: MessageType = MessageType.STATUS_REQUEST,
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
    ) -> None:
        """Run ``count`` complete rounds for one or more groups."""
        for _ in range(count):
            for key in self._selected(site, group):
                self.round(key[0], key[1], message_type)

    def cycle(
        self,
        message_types: Tuple[MessageType, ...] = (
            MessageType.STATUS_REQUEST,
            MessageType.MEASUREMENT_REQUEST,
            MessageType.FAULT_REPORT,
            MessageType.EVENT_REPORT,
        ),
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
        ticks: Optional[int] = None,
        forward: bool = False,
    ) -> None:
        """One complete system cycle for the selected groups.

        Advance the logical clock, let the nodes run their control cycle (the
        deterministic stand-in for time passing on the field devices), then run
        one poll exchange per message type and optionally attempt the upstream
        upload. Domain decisions stay in the modules under test; this only
        pumps traffic.
        """
        for key in self._selected(site, group):
            self.step_group(key[0], key[1], ticks=ticks)
        for message_type in message_types:
            self.rounds(1, message_type, site=site, group=group)
        if forward:
            self.mcc.forward_upstream(site, group)

    def restart_group(
        self, site: Identifier, group: Identifier, ticks: Optional[int] = None
    ) -> Dict[str, int]:
        """Simulate a Group Controller restart (transient state only)."""
        return self.gc(site, group).restart(ticks)

    def restart_lamp(
        self, site: Identifier, group: Identifier, lamp, ticks: Optional[int] = None
    ) -> None:
        """Simulate a Lamp Node watchdog restart."""
        self.node(site, group, lamp).restart(ticks)

    def expire(self, site: Identifier, group: Identifier, ticks: int) -> None:
        """Advance time and let the group controller service its timeouts."""
        self.advance(ticks)
        self.gc(site, group).service_timeouts()

    def _selected(self, site: Optional[Identifier], group: Optional[Identifier]):
        keys = sorted(self._controllers)
        if site is not None:
            keys = [k for k in keys if k[0] == ident(site)]
        if group is not None:
            keys = [k for k in keys if k[1] == ident(group)]
        return keys

    # ------------------------------------------------------------------
    # condition injection
    # ------------------------------------------------------------------
    def silence_lamp(self, site: Identifier, group: Identifier, lamp, silent: bool = True) -> None:
        """Make one lamp stop answering (a dead node, not a state change)."""
        self._silent[(ident(site), ident(group), ident(lamp))] = silent

    def silence_group(self, site: Identifier, group: Identifier, silent: bool = True) -> None:
        for lamp in self.lamp_ids(site, group):
            self.silence_lamp(site, group, lamp, silent)

    def set_upstream(self, site: Identifier, group: Identifier, available: bool) -> None:
        """Take the group controller's upstream link (toward the MCC) up or down."""
        self.upstream(site, group).set_available(available)

    def lamp_is_on(self, site: Identifier, group: Identifier, lamp) -> bool:
        return self.node(site, group, lamp).control.lamp_is_on

    def confirm_fault(
        self, site: Identifier, group: Identifier, lamp, sources: LampNodeSources,
        ticks: Optional[int] = None,
    ):
        """Drive one lamp with abnormal readings until a fault is confirmed."""
        node = self.node(site, group, lamp)
        moment = ticks if ticks is not None else self.clock.ticks + TICKS_PER_SECOND
        fault = None
        for _ in range(node.config.fault_confirmation_count):
            self.step(site, group, lamp, sources=sources, ticks=moment)
            confirmed = [f for f in node.faults.active_faults if f.is_confirmed]
            if confirmed:
                fault = confirmed[0]
                break
            moment += TICKS_PER_SECOND
        return fault
