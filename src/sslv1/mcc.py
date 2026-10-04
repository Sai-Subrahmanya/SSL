"""Master Control Center data/orchestration layer (Phase 15).

The Master Control Center (MCC) is the logical operator/control layer *above*
the Group Controllers (``D-001``, ``D-030``, ``docs/01`` section 6). This
module implements its **data layer** for the digital prototype::

    MCC
     +-- Site
          +-- Group (one Group Controller)
               +-- Lamp (one Lamp Node) x 1..N

Deliberately, the MCC is a **consumer and orchestration layer**:

* registry: it owns the site -> group -> lamp inventory and the identity
  validation that goes with it (``PR-IDENTITY-001``, ``PR-IDENTITY-003``),
* aggregation: it derives status from what the Group Controllers already
  hold - registrations, received records and the existing ``EventLog``,
* control: it forwards operator commands through
  ``GroupController.forward_control``, the existing authorization and command
  path, and preserves the original actor identity end to end,
* configuration: it exposes the existing configuration readback only,
* audit: it reads the existing audit trail instead of keeping one; there is no
  MCC event log, because a second audit mechanism would be a parallel record
  of the same commands. MCC-issued commands are audited where they are
  executed, at the Group Controller, with the originating actor.

It does **not** implement lamp control, diagnostics, the fault lifecycle, the
notification lifecycle, the command lifecycle, the communication protocol,
storage or authorization, and it keeps no second copy of any of them. There is
no MCC permission system: authorization stays in the existing services and the
MCC adds no decision of its own.

Phase 16 completes the **upstream end** of that architecture: the abstract
upstream link of the Group Controller already uploads records, and
:class:`MccUpstreamLink` makes the MCC the other end of it. The MCC accepts
each record identity once (:meth:`MasterControlCenter.receive_upstream`), keeps
them in arrival order - it adds no storage engine of its own, and what it holds
is exactly what arrived - and can drive the documented post-recovery sequence
through the controllers (:meth:`MasterControlCenter.recover_upstream`).

Consequences stated rather than hidden:

* the MCC can only show what a Group Controller has actually reported, so a
  silent node is reported as unavailable or stale, never as healthy,
* a value that has never been reported is ``None``; measurements are never
  invented and missing data is never converted into zeros,
* fault evidence times are *MCC observation* times (when the group controller
  received each report): the current ``FAULT_REPORT`` payload carries no
  node-local evidence timestamps and no node-side fault-to-event linkage, so
  those stay at the node layer,
* the freshness limit is a presentation limit of this data layer in logical
  ticks, not a product threshold; no numeric value is frozen (``docs/09``),
* nothing here is a production MCC: no GUI (assumption ``A-24``), no
  persistence, no database, no network, no physical link. Physical
  communication, production security and multi-site deployment remain
  unvalidated (``docs/09``).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

from .authorization import Actor
from .comm import MessageType
from .command import CommandRecord
from .enums import (
    AggregateHealth,
    CommState,
    CommunicationStatus,
    ConfiguredMode,
    ControlSubtype,
    ControllerStatus,
    EventSeverity,
    FaultSeverity,
    FaultState,
    FaultType,
    Freshness,
    LampAvailability,
    LampState,
    NotificationState,
    OperatingMode,
    OverrideState,
    RecordType,
    SensorStatus,
    TimeSyncState,
)
from .errors import ConfigurationError
from .event import Event
from .identity import BusAddress, Identifier
from .nodes import GroupController, LampNode
from .nodes.group_controller import UpstreamLink
from .storage import StorageRecord
from .time_model import LogicalClock

#: Fault states that still need operator attention. The MCC does not manage
#: this lifecycle; it only filters the states the node reported.
_ACTIVE_FAULT_STATES = frozenset(
    {
        FaultState.SUSPECTED,
        FaultState.CONFIRMED,
        FaultState.ACKNOWLEDGED,
        FaultState.UNDER_REPAIR,
        FaultState.VERIFYING,
    }
)

#: Severity ordering for aggregate "highest severity" reporting.
_SEVERITY_ORDER = (
    FaultSeverity.INFO,
    FaultSeverity.MINOR,
    FaultSeverity.MAJOR,
    FaultSeverity.CRITICAL,
)

#: Communication states that mean "the link is retrying or degraded".
_UNHEALTHY_COMM_STATES = frozenset({CommState.RETRY, CommState.DEGRADED})


def _identifier(value) -> Identifier:
    """Accept an :class:`Identifier` or a plain string at the MCC boundary."""
    if isinstance(value, Identifier):
        return value
    return Identifier(str(value))


def _enum(enum_type, value):
    """Convert a transported value back to its enum, or ``None``.

    A value the receiver cannot interpret becomes ``None`` rather than an
    invented state.
    """
    if value is None:
        return None
    if isinstance(value, enum_type):
        return value
    try:
        return enum_type(value)
    except (ValueError, KeyError):
        try:
            return enum_type[str(value).split(".")[-1]]
        except (ValueError, KeyError):
            return None


def _highest_severity(severities) -> Optional[FaultSeverity]:
    ranked = [s for s in severities if s in _SEVERITY_ORDER]
    if not ranked:
        return None
    return max(ranked, key=_SEVERITY_ORDER.index)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MasterControlCenterConfig:
    """MCC data-layer configuration.

    ``status_max_age_ticks`` is the age beyond which an observation is no
    longer presented as current. It is a presentation limit of the data layer
    expressed in logical ticks, **not** a product threshold: no numeric value
    is frozen (``docs/09``). When it is not configured, freshness is reported
    as ``UNKNOWN`` - an unconfigured limit is never reported as ``FRESH``.
    """

    status_max_age_ticks: Optional[int] = None

    def validated(self) -> "MasterControlCenterConfig":
        limit = self.status_max_age_ticks
        if limit is not None and (not isinstance(limit, int) or isinstance(limit, bool)):
            raise ConfigurationError("status_max_age_ticks must be an integer or None")
        if limit is not None and limit <= 0:
            raise ConfigurationError("status_max_age_ticks must be positive")
        return self


# ---------------------------------------------------------------------------
# Registry entries
# ---------------------------------------------------------------------------
@dataclass
class LampRegistration:
    """A lamp registered at one group of one site.

    Registration records identity only. The MCC holds no device handle and no
    lamp state of its own: everything it reports is read back from the Group
    Controller that serves the group (D-041).
    """

    site_id: Identifier
    group_id: Identifier
    lamp_id: Identifier
    bus_address: BusAddress


@dataclass
class GroupRegistration:
    """A group (served by one Group Controller) registered at one site."""

    site_id: Identifier
    group_id: Identifier
    controller: GroupController
    lamps: Dict[Identifier, LampRegistration] = field(default_factory=dict)

    @property
    def lamp_count(self) -> int:
        return len(self.lamps)


@dataclass
class SiteRegistration:
    """A site and its groups: the MCC aggregation root."""

    site_id: Identifier
    groups: Dict[Identifier, GroupRegistration] = field(default_factory=dict)

    @property
    def group_count(self) -> int:
        return len(self.groups)

    @property
    def lamp_count(self) -> int:
        return sum(group.lamp_count for group in self.groups.values())


# ---------------------------------------------------------------------------
# Read models (views over the layers below, never a second lifecycle)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ReceivedRecord:
    """One record the MCC received from a Group Controller.

    ``record`` is the existing :class:`~sslv1.storage.StorageRecord`, unchanged:
    the MCC adds origin and arrival order, never a second record format.
    """

    site_id: Identifier
    group_id: Identifier
    record: StorageRecord

    @property
    def record_type(self):
        return self.record.record_type

    @property
    def sequence_number(self) -> int:
        return self.record.sequence_number

    @property
    def lamp_id(self) -> Optional[Identifier]:
        lamp = self.record.payload.get("lamp_id")
        return Identifier(str(lamp)) if lamp else None

    @property
    def timestamp_ticks(self) -> int:
        """The record's own logical timestamp.

        The MCC does not re-stamp what it received: arrival *order* is the
        order of this list, and the record keeps the timestamp its device
        wrote.
        """
        return self.record.timestamp.ticks


class MccUpstreamLink(UpstreamLink):
    """The Master Control Center end of the existing abstract upstream link.

    ``GroupController`` uploads records through an injected
    :class:`~sslv1.nodes.group_controller.UpstreamLink`; this implementation
    connects one group's controller to the MCC. It is wired per group, because
    a group identity is only unique within its site, and it refuses records
    that do not belong to that group's controller - an unidentifiable upload
    stays pending at the sender instead of appearing in the MCC history.
    """

    def __init__(
        self,
        mcc: "MasterControlCenter",
        site: Identifier,
        group: Identifier,
        available: bool = True,
    ) -> None:
        self._mcc = mcc
        self._site = _identifier(site)
        self._group = _identifier(group)
        self._available = available

    def available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        """The upstream outage injection point (link down toward the MCC)."""
        self._available = available

    def upload(self, record: StorageRecord) -> bool:
        if not self._available:
            return False
        return self._mcc.receive_upstream(self._site, self._group, record)


@dataclass(frozen=True)
class FaultSummary:
    """An active fault as the MCC currently knows it.

    Built from the ``FAULT`` records a Group Controller received; the MCC owns
    no fault state. ``first_reported_ticks`` / ``latest_reported_ticks`` are
    *observation* times at the group controller, not physical evidence
    timestamps, because the wire report carries no node-local evidence times.

    ``latest_record_sequence`` is the identity of the stored record this summary
    was read from, so the fault can be traced back into the existing audit trail
    (``fault_records``). Events the group received for the same lamp are read
    through ``events`` / ``reported_events``: the existing wire event report
    carries no fault linkage, so no per-fault event pairing is claimed here.

    The existing fault report transports the one fault the node reports first,
    so a lamp with several concurrent faults is visible one fault at a time. A
    fault stops appearing as active when the node reports no active fault (the
    clearing record) - never because another fault was reported instead, since
    that would claim a clearance the node never reported.
    """

    site_id: Identifier
    group_id: Identifier
    lamp_id: Identifier
    fault_id: str
    fault_type: Optional[FaultType]
    diagnostic_classification: Optional[str]
    state: Optional[FaultState]
    severity: Optional[FaultSeverity]
    notification_state: Optional[NotificationState]
    confirmation_count: Optional[int]
    first_reported_ticks: int
    latest_reported_ticks: int
    latest_record_sequence: int
    time_sync_state: TimeSyncState

    @property
    def is_active(self) -> bool:
        return self.state in _ACTIVE_FAULT_STATES


@dataclass(frozen=True)
class LampStatus:
    """The MCC view of one lamp, aggregated from what the group reported.

    ``availability`` describes whether the MCC can rely on the lamp *now*:
    communication health plus whether an observation exists and is not known
    to be stale. ``freshness`` reports the age verdict separately and is
    ``UNKNOWN`` when no freshness limit is configured.
    """

    site_id: Identifier
    group_id: Identifier
    lamp_id: Identifier
    bus_address: BusAddress
    availability: LampAvailability
    comm_state: CommState
    freshness: Freshness
    age_ticks: Optional[int]
    last_seen_ticks: Optional[int]
    # state reported by STATUS_RESPONSE / MEASUREMENT_RESPONSE
    effective_mode: Optional[OperatingMode]
    active_override: Optional[OverrideState]
    configured_mode: Optional[ConfiguredMode]
    commanded_state: Optional[LampState]
    switching_feedback: Optional[LampState]
    actual_state: Optional[LampState]
    sensor_status: Optional[SensorStatus]
    controller_status: Optional[ControllerStatus]
    communication_status: Optional[CommunicationStatus]
    # last measurement reported by MEASUREMENT_RESPONSE
    measured_ticks: Optional[int]
    time_sync_state: Optional[TimeSyncState]
    voltage: Optional[float]
    current: Optional[float]
    power: Optional[float]
    energy: Optional[float]
    light_level: Optional[float]
    faults: Tuple[FaultSummary, ...] = ()


@dataclass(frozen=True)
class GroupStatus:
    """Group-level aggregation for one site.

    Individual failures are listed, never summarised away: ``degraded_lamps``,
    ``recovering_lamps``, ``unavailable_lamps``, ``unknown_lamps`` and
    ``faulted_lamps`` name the lamps affected, so a healthy aggregate cannot
    conceal an unhealthy lamp.
    """

    site_id: Identifier
    group_id: Identifier
    health: AggregateHealth
    total_lamps: int
    healthy_lamps: int
    comm_summary: Dict[str, int]
    degraded_lamps: Tuple[Identifier, ...]
    recovering_lamps: Tuple[Identifier, ...]
    unavailable_lamps: Tuple[Identifier, ...]
    unknown_lamps: Tuple[Identifier, ...]
    active_faults: int
    highest_severity: Optional[FaultSeverity]
    faulted_lamps: Tuple[Identifier, ...]
    aggregate_power: float
    aggregate_energy: float
    latest_observation_ticks: Optional[int]
    upstream_available: bool
    pending_upload: int
    retained_records: int
    storage_full: bool


@dataclass(frozen=True)
class SiteStatus:
    """Site-level aggregation across groups.

    ``groups`` carries every group status, so a healthy site cannot conceal an
    unhealthy group; ``unhealthy_groups`` names them directly.
    """

    site_id: Identifier
    health: AggregateHealth
    total_groups: int
    total_lamps: int
    healthy_lamps: int
    active_faults: int
    highest_severity: Optional[FaultSeverity]
    unhealthy_groups: Tuple[Identifier, ...]
    groups: Tuple[GroupStatus, ...]
    aggregate_power: float
    aggregate_energy: float
    latest_observation_ticks: Optional[int]


# ---------------------------------------------------------------------------
# Master Control Center
# ---------------------------------------------------------------------------
class MasterControlCenter:
    """Deterministic digital MCC data layer over one or more groups.

    The MCC requires a **single logical clock** shared with every registered
    controller and lamp node: age and freshness are only meaningful when all
    timestamps come from the same deterministic timeline. A device using a
    different clock is rejected at registration instead of being aggregated
    into nonsense.
    """

    def __init__(
        self,
        config: Optional[MasterControlCenterConfig] = None,
        clock: Optional[LogicalClock] = None,
    ) -> None:
        self.config = (config or MasterControlCenterConfig()).validated()
        self.clock = clock or LogicalClock()
        self._sites: Dict[Identifier, SiteRegistration] = {}
        self._received: List[ReceivedRecord] = []
        self._received_identities: set = set()
        self._duplicate_uploads = 0

    # ------------------------------------------------------------------
    # registry: sites
    # ------------------------------------------------------------------
    def create_site(self, site: Identifier) -> SiteRegistration:
        """Create a site; duplicate site identities are rejected."""
        site = _identifier(site)
        if site in self._sites:
            raise ConfigurationError("site %s is already registered" % site)
        registration = SiteRegistration(site_id=site)
        self._sites[site] = registration
        return registration

    @property
    def sites(self) -> Tuple[SiteRegistration, ...]:
        return tuple(self._sites[site] for site in sorted(self._sites))

    def site(self, site: Identifier) -> SiteRegistration:
        site = _identifier(site)
        registration = self._sites.get(site)
        if registration is None:
            raise ConfigurationError("site %s is not registered" % site)
        return registration

    def has_site(self, site: Identifier) -> bool:
        return _identifier(site) in self._sites

    # ------------------------------------------------------------------
    # registry: groups
    # ------------------------------------------------------------------
    def register_group(
        self, site: Identifier, group: Identifier, controller: GroupController
    ) -> GroupRegistration:
        """Attach a Group Controller to a site as one group.

        The controller identity must match the site and group it is registered
        under: an inconsistent hierarchy is rejected, never re-labelled.
        """
        site = _identifier(site)
        group = _identifier(group)
        registration = self.site(site)
        identity = controller.identity
        if identity.site_id != site or identity.group_id != group:
            raise ConfigurationError(
                "group controller identity %s does not match %s/%s" % (identity, site, group)
            )
        if controller.clock is not self.clock:
            raise ConfigurationError(
                "group controller for %s/%s must use the MCC logical clock" % (site, group)
            )
        if group in registration.groups:
            raise ConfigurationError(
                "group %s is already registered at site %s" % (group, site)
            )
        registered = GroupRegistration(site_id=site, group_id=group, controller=controller)
        registration.groups[group] = registered
        return registered

    def groups(self, site: Identifier) -> Tuple[GroupRegistration, ...]:
        registration = self.site(site)
        return tuple(registration.groups[group] for group in sorted(registration.groups))

    def group(self, site: Identifier, group: Identifier) -> GroupRegistration:
        group = _identifier(group)
        registration = self.site(site).groups.get(group)
        if registration is None:
            raise ConfigurationError("group %s is not registered at site %s" % (group, site))
        return registration

    # ------------------------------------------------------------------
    # registry: lamps
    # ------------------------------------------------------------------
    def register_lamp(
        self, site: Identifier, group: Identifier, node: LampNode
    ) -> LampRegistration:
        """Register a lamp node under its group, validating the hierarchy.

        The node is also registered with the Group Controller so that the
        group inventory and the MCC inventory agree.
        """
        site = _identifier(site)
        group = _identifier(group)
        registration = self.group(site, group)
        identity = node.identity
        if identity.site_id != site or identity.group_id != group:
            raise ConfigurationError(
                "lamp identity %s does not match %s/%s" % (identity, site, group)
            )
        if node.clock is not self.clock:
            raise ConfigurationError("lamp %s must use the MCC logical clock" % node.lamp_id)
        if node.lamp_id in registration.lamps:
            raise ConfigurationError(
                "lamp %s is already registered at %s/%s" % (node.lamp_id, site, group)
            )
        if registration.controller.registration_for(node.lamp_id) is None:
            registration.controller.register_node(node.lamp_id, node.bus_address)
        registered = LampRegistration(
            site_id=site,
            group_id=group,
            lamp_id=node.lamp_id,
            bus_address=node.bus_address,
        )
        registration.lamps[node.lamp_id] = registered
        return registered

    def lamps(
        self, site: Optional[Identifier] = None, group: Optional[Identifier] = None
    ) -> Tuple[LampRegistration, ...]:
        """List lamp registrations for a group, a site, or the whole MCC."""
        result: List[LampRegistration] = []
        for group_registration in self._iter_groups(site, group):
            for lamp in sorted(group_registration.lamps):
                result.append(group_registration.lamps[lamp])
        return tuple(result)

    def lamp(self, site: Identifier, group: Identifier, lamp: Identifier) -> LampRegistration:
        lamp = _identifier(lamp)
        registration = self.group(site, group).lamps.get(lamp)
        if registration is None:
            raise ConfigurationError("lamp %s is not registered at %s/%s" % (lamp, site, group))
        return registration

    # ------------------------------------------------------------------
    # orchestration of the existing layers
    # ------------------------------------------------------------------
    def poll(
        self,
        message_type: MessageType = MessageType.STATUS_REQUEST,
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
    ) -> Dict[Tuple[Identifier, Identifier], Dict[int, bool]]:
        """Start one poll per idle node through the existing controllers.

        Delegates to :meth:`GroupController.poll`; delivery, retry and timeout
        behaviour stay in the Group Controller.
        """
        results: Dict[Tuple[Identifier, Identifier], Dict[int, bool]] = {}
        for registration in self._iter_groups(site, group):
            results[(registration.site_id, registration.group_id)] = (
                registration.controller.poll(message_type)
            )
        return results

    def request_control(
        self,
        site: Identifier,
        group: Identifier,
        lamp: Identifier,
        subtype: ControlSubtype,
        actor: Actor,
        command_id: Optional[str] = None,
        parameter: int = 0,
        target_state: Optional[LampState] = None,
    ) -> CommandRecord:
        """Forward a control command through the existing command path.

        Authorization is decided by the existing ``CommandService`` at the
        Group Controller (and again at the node for node-privilege actions);
        the MCC adds no permission system and preserves the actor identity
        unchanged. An unauthorized command is rejected before anything is
        transmitted.
        """
        registration = self.lamp(site, group, lamp)
        return self.group(site, group).controller.forward_control(
            registration.lamp_id,
            subtype,
            actor,
            command_id=command_id,
            parameter=parameter,
            target_state=target_state,
        )

    def force_on(
        self, site: Identifier, group: Identifier, lamp: Identifier, actor: Actor,
        command_id: Optional[str] = None,
    ) -> CommandRecord:
        return self.request_control(site, group, lamp, ControlSubtype.LAMP_ON, actor,
                                    command_id=command_id)

    def force_off(
        self, site: Identifier, group: Identifier, lamp: Identifier, actor: Actor,
        command_id: Optional[str] = None,
    ) -> CommandRecord:
        return self.request_control(site, group, lamp, ControlSubtype.LAMP_OFF, actor,
                                    command_id=command_id)

    def return_to_auto(
        self, site: Identifier, group: Identifier, lamp: Identifier, actor: Actor,
        command_id: Optional[str] = None,
    ) -> CommandRecord:
        return self.request_control(site, group, lamp, ControlSubtype.RETURN_TO_AUTO, actor,
                                    command_id=command_id)

    def command(
        self, site: Identifier, group: Identifier, command_id: str
    ) -> Optional[CommandRecord]:
        """The existing command record for an MCC-issued action, if any."""
        return self.group(site, group).controller.commands.get(command_id)

    def commands(self, site: Identifier, group: Identifier) -> Tuple[CommandRecord, ...]:
        """Every command record the group controller holds (existing model)."""
        return tuple(self.group(site, group).controller.commands.records)

    def read_configuration(
        self, site: Identifier, group: Identifier, lamp: Identifier
    ) -> None:
        """Request the existing configuration readback for one lamp.

        Only readback is exposed. Writing configuration stays with the
        existing bounded distribution path at the Group Controller; structured
        remote configuration remains unimplemented and ``PR-CONFIG-001`` /
        ``PR-CONFIG-002`` stay PARTIAL.
        """
        registration = self.lamp(site, group, lamp)
        self.group(site, group).controller.read_configuration(registration.lamp_id)

    def configuration_snapshot(
        self, site: Identifier, group: Identifier, lamp: Identifier
    ) -> Optional[Dict[str, object]]:
        """The last configuration readback the group received, or ``None``."""
        registration = self.lamp(site, group, lamp)
        node_registration = self.group(site, group).controller.registration_for(
            registration.lamp_id
        )
        if node_registration is None or not node_registration.configuration:
            return None
        return dict(node_registration.configuration)

    # ------------------------------------------------------------------
    # upstream: records the group controllers delivered (Phase 16)
    # ------------------------------------------------------------------
    def receive_upstream(
        self, site: Identifier, group: Identifier, record: StorageRecord
    ) -> bool:
        """Accept one uploaded record from a Group Controller.

        Returns ``True`` when the record is now held by the MCC. A record that
        was already received is **also** ``True``: the sender's confirmation
        semantics are "the far end has it", and a re-sent record after a lost
        confirmation must not be reported to the sender as a failure while the
        record is in fact delivered. The duplicate is counted, not stored
        twice, so duplicate delivery cannot corrupt or duplicate history.

        Returns ``False`` only for a record the MCC cannot attribute to that
        group's controller, or that contradicts its own scope, so it stays
        pending at the sender and remains visible as pending instead of
        silently vanishing.

        The record envelope carries ``device_id``, which for a group-level
        device is the group id (``docs/03``): group ids are unique inside a
        site, not across sites, so the *site* is established by the link that
        delivered the record. Everything the record itself still states about
        its scope is checked here:
        record validity, the site/group the record names (measurement
        payloads carry them), and that any lamp it names is registered with
        that group's controller. A mis-delivered record is therefore refused
        rather than filed under the wrong site, group or lamp.
        """
        registration = self.group(site, group)
        if record.device_id != registration.controller.identity.device_id:
            return False
        if not record.is_valid():
            return False
        payload = record.payload or {}
        for name, expected in (("site_id", registration.site_id),
                               ("group_id", registration.group_id)):
            claimed = payload.get(name)
            if claimed is not None and str(claimed) != str(expected):
                return False
        lamp = payload.get("lamp_id")
        if lamp is not None and registration.controller.registration_for(
                Identifier(str(lamp))) is None:
            return False
        identity = (str(site), str(group), record.record_type.value, record.sequence_number)
        if identity in self._received_identities:
            self._duplicate_uploads += 1
            return True
        self._received_identities.add(identity)
        self._received.append(
            ReceivedRecord(site_id=registration.site_id, group_id=registration.group_id,
                           record=record)
        )
        return True

    def upstream_records(
        self,
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
        record_type: Optional[RecordType] = None,
        lamp: Optional[Identifier] = None,
    ) -> Tuple[ReceivedRecord, ...]:
        """Records the MCC received, in arrival order.

        Arrival order is the MCC's own deterministic ordering evidence; the
        per-device upload order is asserted in the tests, it is not assumed
        here. Nothing is reordered, aggregated or rewritten.
        """
        selected = tuple(self._iter_groups(site, group))
        scope = {(registration.site_id, registration.group_id) for registration in selected}
        records = []
        for received in self._received:
            if (received.site_id, received.group_id) not in scope:
                continue
            if record_type is not None and received.record_type is not record_type:
                continue
            if lamp is not None and received.lamp_id != _identifier(lamp):
                continue
            records.append(received)
        return tuple(records)

    @property
    def duplicate_uploads(self) -> int:
        """How many already-received records were offered again."""
        return self._duplicate_uploads

    def forward_upstream(
        self, site: Optional[Identifier] = None, group: Optional[Identifier] = None
    ) -> Dict[Tuple[Identifier, Identifier], Dict[str, int]]:
        """Upload pending records through the existing routers, per group."""
        return {
            (registration.site_id, registration.group_id):
                registration.controller.forward_upstream()
            for registration in self._iter_groups(site, group)
        }

    def recover_upstream(
        self, site: Optional[Identifier] = None, group: Optional[Identifier] = None
    ) -> Dict[Tuple[Identifier, Identifier], Dict[str, object]]:
        """Run the documented post-recovery sequence, per selected group.

        Delegates to ``GroupController.resynchronize_upstream``: the sequence
        belongs to the layer that owns the buffer and the link, the MCC only
        drives it (``PR-OFFLINE-005``).
        """
        return {
            (registration.site_id, registration.group_id):
                registration.controller.resynchronize_upstream()
            for registration in self._iter_groups(site, group)
        }

    # ------------------------------------------------------------------
    # fault and event visibility (existing structures only)
    # ------------------------------------------------------------------
    def fault_records(
        self,
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
        lamp: Optional[Identifier] = None,
    ) -> Tuple[StorageRecord, ...]:
        """``FAULT`` records the group controllers actually received.

        These are the existing storage records, not an MCC-side format.
        """
        records: List[StorageRecord] = []
        for registration in self._iter_groups(site, group):
            for record in registration.controller.storage.records:
                if record.record_type is not RecordType.FAULT:
                    continue
                if lamp is not None and record.payload.get("lamp_id") != str(lamp):
                    continue
                records.append(record)
        return tuple(sorted(records, key=lambda r: (r.timestamp.ticks, r.sequence_number)))

    def active_faults(
        self,
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
        lamp: Optional[Identifier] = None,
    ) -> Tuple[FaultSummary, ...]:
        """Active faults, one summary per fault identity.

        The latest report for each fault identity wins; a fault the node no
        longer reports as active is omitted. The MCC keeps no fault state.
        """
        latest: Dict[Tuple[str, str, str, str], StorageRecord] = {}
        first_ticks: Dict[Tuple[str, str, str, str], int] = {}
        for registration in self._iter_groups(site, group):
            for record in registration.controller.storage.records:
                if record.record_type is not RecordType.FAULT:
                    continue
                payload = record.payload
                if lamp is not None and payload.get("lamp_id") != str(lamp):
                    continue
                fault_id = str(payload.get("fault_id") or "")
                if not fault_id or not payload.get("lamp_id"):
                    continue
                # A group id is only unique within its site, so the site is part
                # of the fault identity here: the same group id at another site
                # is never the same fault.
                key = (
                    str(registration.site_id),
                    str(registration.group_id),
                    str(payload.get("lamp_id")),
                    fault_id,
                )
                previous = latest.get(key)
                if previous is None or record.sequence_number > previous.sequence_number:
                    latest[key] = record
                first_ticks[key] = min(
                    first_ticks.get(key, record.timestamp.ticks), record.timestamp.ticks
                )

        summaries: List[FaultSummary] = []
        for (site_key, group_key, lamp_key, fault_id), record in latest.items():
            if record.payload.get("cleared"):
                # The group recorded the node answering "no active fault" for a
                # fault it reported before: the fault is over, so it is not in
                # the active view. The record itself stays readable through
                # ``fault_records`` — nothing is erased or re-created.
                continue
            summary = FaultSummary(
                site_id=Identifier(site_key),
                group_id=Identifier(group_key),
                lamp_id=Identifier(lamp_key),
                fault_id=fault_id,
                fault_type=_enum(FaultType, record.payload.get("fault_type")),
                diagnostic_classification=(
                    str(record.payload["diagnostic_classification"])
                    if record.payload.get("diagnostic_classification") is not None
                    else None
                ),
                state=_enum(FaultState, record.payload.get("fault_state")),
                severity=_enum(FaultSeverity, record.payload.get("severity")),
                notification_state=_enum(
                    NotificationState, record.payload.get("notification_state")
                ),
                confirmation_count=record.payload.get("confirmation_count"),
                first_reported_ticks=first_ticks[(site_key, group_key, lamp_key, fault_id)],
                latest_reported_ticks=record.timestamp.ticks,
                latest_record_sequence=record.sequence_number,
                time_sync_state=record.timestamp.sync_state,
            )
            if summary.is_active:
                summaries.append(summary)
        return tuple(
            sorted(
                summaries,
                key=lambda f: (f.latest_reported_ticks, str(f.site_id), str(f.group_id),
                               str(f.lamp_id), f.fault_id),
            )
        )

    def events(
        self,
        site: Optional[Identifier] = None,
        group: Optional[Identifier] = None,
        event_type=None,
        min_severity: Optional[EventSeverity] = None,
    ) -> Tuple[Event, ...]:
        """Audit events from the existing ``EventLog`` of every group.

        Group-level audit (commands, configuration, security, communication and
        storage transitions) already lives there; the MCC reads it and adds
        nothing of its own.
        """
        order = list(EventSeverity)
        floor = order.index(min_severity) if min_severity else None
        collected: List[Event] = []
        for registration in self._iter_groups(site, group):
            for event in registration.controller.events:
                if event_type is not None and event.event_type is not event_type:
                    continue
                if floor is not None and order.index(event.severity) < floor:
                    continue
                collected.append(event)
        return tuple(
            sorted(collected, key=lambda e: (e.timestamp.ticks, str(e.device_id), e.event_id))
        )

    def reported_events(
        self, site: Identifier, group: Identifier, lamp: Optional[Identifier] = None
    ) -> Tuple[StorageRecord, ...]:
        """``EVENT`` records the group controller received from its nodes."""
        records = []
        for record in self.group(site, group).controller.storage.records:
            if record.record_type is not RecordType.EVENT:
                continue
            if lamp is not None and record.payload.get("lamp_id") != str(lamp):
                continue
            records.append(record)
        return tuple(sorted(records, key=lambda r: (r.timestamp.ticks, r.sequence_number)))

    # ------------------------------------------------------------------
    # status aggregation
    # ------------------------------------------------------------------
    def lamp_status(
        self, site: Identifier, group: Identifier, lamp: Identifier
    ) -> LampStatus:
        """The aggregated status of one lamp."""
        return self._lamp_status(self.lamp(site, group, lamp), self.group(site, group))

    def lamp_statuses(
        self, site: Optional[Identifier] = None, group: Optional[Identifier] = None
    ) -> Tuple[LampStatus, ...]:
        """The aggregated status of every selected lamp, in registry order."""
        return tuple(
            self._lamp_status(lamp, self.group(lamp.site_id, lamp.group_id))
            for lamp in self.lamps(site, group)
        )

    def group_status(self, site: Identifier, group: Identifier) -> GroupStatus:
        """Group-level aggregation; individual failures are listed, not hidden."""
        registration = self.group(site, group)
        controller = registration.controller
        faults = self.active_faults(site, group)
        faults_by_lamp: Dict[Identifier, List[FaultSummary]] = {}
        for fault in faults:
            faults_by_lamp.setdefault(fault.lamp_id, []).append(fault)
        statuses = [
            self._lamp_status(lamp, registration,
                              tuple(faults_by_lamp.get(lamp.lamp_id, ())))
            for _, lamp in sorted(registration.lamps.items())
        ]
        upstream_available = controller.upstream.available()

        def matching(availability: LampAvailability) -> Tuple[Identifier, ...]:
            return tuple(s.lamp_id for s in statuses if s.availability is availability)

        observations = [s.last_seen_ticks for s in statuses if s.last_seen_ticks is not None]

        if not statuses:
            health = AggregateHealth.UNKNOWN
        elif not upstream_available:
            health = AggregateHealth.UNAVAILABLE
        elif all(s.availability is LampAvailability.UNKNOWN for s in statuses):
            health = AggregateHealth.UNKNOWN
        elif all(s.availability is LampAvailability.UNAVAILABLE for s in statuses):
            # Every lamp of the group is unreachable: the group is unavailable,
            # not merely degraded. Calling it degraded would understate the
            # failure of the whole group (one unreachable lamp of many *is*
            # degradation, which the branch below reports).
            health = AggregateHealth.UNAVAILABLE
        elif all(s.availability is LampAvailability.HEALTHY for s in statuses) and not faults:
            health = AggregateHealth.HEALTHY
        else:
            health = AggregateHealth.DEGRADED

        return GroupStatus(
            site_id=site,
            group_id=group,
            health=health,
            total_lamps=len(statuses),
            healthy_lamps=len(matching(LampAvailability.HEALTHY)),
            comm_summary=dict(controller.communication_summary()),
            degraded_lamps=matching(LampAvailability.DEGRADED),
            recovering_lamps=matching(LampAvailability.RECOVERING),
            unavailable_lamps=matching(LampAvailability.UNAVAILABLE),
            unknown_lamps=matching(LampAvailability.UNKNOWN),
            active_faults=len(faults),
            highest_severity=_highest_severity([f.severity for f in faults]),
            faulted_lamps=tuple(sorted({f.lamp_id for f in faults}, key=str)),
            aggregate_power=controller.aggregate_power(),
            aggregate_energy=controller.aggregate_energy(),
            latest_observation_ticks=max(observations) if observations else None,
            upstream_available=upstream_available,
            pending_upload=len(controller.storage.pending_upload),
            retained_records=len(controller.storage.retained),
            storage_full=controller.storage.is_full,
        )

    def site_status(self, site: Identifier) -> SiteStatus:
        """Site-level aggregation; an unhealthy group is never concealed."""
        registration = self.site(site)
        groups = tuple(
            self.group_status(site, group) for group in sorted(registration.groups)
        )
        observations = [
            g.latest_observation_ticks for g in groups
            if g.latest_observation_ticks is not None
        ]

        if not groups:
            health = AggregateHealth.UNKNOWN
        elif all(g.health is AggregateHealth.UNAVAILABLE for g in groups):
            health = AggregateHealth.UNAVAILABLE
        elif all(g.health is AggregateHealth.UNKNOWN for g in groups):
            health = AggregateHealth.UNKNOWN
        elif all(g.health is AggregateHealth.HEALTHY for g in groups):
            health = AggregateHealth.HEALTHY
        else:
            health = AggregateHealth.DEGRADED

        return SiteStatus(
            site_id=site,
            health=health,
            total_groups=len(groups),
            total_lamps=sum(g.total_lamps for g in groups),
            healthy_lamps=sum(g.healthy_lamps for g in groups),
            active_faults=sum(g.active_faults for g in groups),
            highest_severity=_highest_severity([g.highest_severity for g in groups]),
            unhealthy_groups=tuple(
                g.group_id for g in groups if g.health is not AggregateHealth.HEALTHY
            ),
            groups=groups,
            aggregate_power=sum(g.aggregate_power for g in groups),
            aggregate_energy=sum(g.aggregate_energy for g in groups),
            latest_observation_ticks=max(observations) if observations else None,
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _iter_groups(
        self, site: Optional[Identifier], group: Optional[Identifier]
    ) -> Iterator[GroupRegistration]:
        """Select groups; a group id is only unique *within* a site."""
        if group is not None and site is None:
            raise ConfigurationError("selecting a group requires its site")
        if site is not None:
            return iter(self.groups(site) if group is None else (self.group(site, group),))
        return iter(
            tuple(
                site_registration.groups[key]
                for site_registration in self.sites
                for key in sorted(site_registration.groups)
            )
        )

    def _lamp_status(
        self,
        lamp: LampRegistration,
        group: GroupRegistration,
        precomputed_faults: Optional[Tuple[FaultSummary, ...]] = None,
    ) -> LampStatus:
        controller = group.controller
        node_registration = controller.registration_for(lamp.lamp_id)
        if node_registration is None:
            raise ConfigurationError(
                "lamp %s is registered at the MCC but not with its group controller"
                % lamp.lamp_id
            )

        measurement = node_registration.last_measurement
        reported = node_registration.status or {}
        last_seen = node_registration.last_seen_ticks
        age = None if last_seen is None else self.clock.ticks - last_seen
        limit = self.config.status_max_age_ticks
        if age is None or limit is None:
            freshness = Freshness.UNKNOWN
        elif age > limit:
            freshness = Freshness.STALE
        else:
            freshness = Freshness.FRESH

        faults = (
            self.active_faults(lamp.site_id, lamp.group_id, lamp.lamp_id)
            if precomputed_faults is None else precomputed_faults
        )
        availability = self._availability(
            node_registration.comm.state, measurement, reported, freshness,
            controller.upstream.available(), bool(faults),
        )

        def state_field(name):
            """Prefer the measurement value, then the status report."""
            if measurement is not None:
                value = getattr(measurement, name, None)
                if value is not None:
                    return value
            return reported.get(name)

        return LampStatus(
            site_id=lamp.site_id,
            group_id=lamp.group_id,
            lamp_id=lamp.lamp_id,
            bus_address=lamp.bus_address,
            availability=availability,
            comm_state=node_registration.comm.state,
            freshness=freshness,
            age_ticks=age,
            last_seen_ticks=last_seen,
            effective_mode=state_field("effective_mode"),
            active_override=reported.get("override"),
            configured_mode=self._configured_mode(node_registration),
            commanded_state=state_field("commanded_state"),
            switching_feedback=state_field("switching_feedback"),
            actual_state=state_field("actual_state"),
            sensor_status=state_field("sensor_status"),
            controller_status=state_field("controller_status"),
            communication_status=state_field("communication_status"),
            measured_ticks=measurement.timestamp.ticks if measurement else None,
            time_sync_state=measurement.timestamp.sync_state if measurement else None,
            voltage=measurement.voltage if measurement else None,
            current=measurement.current if measurement else None,
            power=measurement.power if measurement else None,
            energy=measurement.energy if measurement else None,
            light_level=measurement.light_level if measurement else None,
            faults=faults,
        )

    @staticmethod
    def _availability(
        comm_state: CommState,
        measurement,
        reported: Dict[str, object],
        freshness: Freshness,
        upstream_available: bool,
        has_active_fault: bool,
    ) -> LampAvailability:
        """Link health and data currency decide; a faulted lamp is not healthy.

        The communication verdict dominates: an active fault whose report is
        no longer reachable must not be presented as current, so a lamp whose
        data is stale stays ``UNKNOWN`` even if an old report mentioned a
        fault.
        """
        if not upstream_available:
            return LampAvailability.UNAVAILABLE
        if comm_state is CommState.COMM_FAULT:
            return LampAvailability.UNAVAILABLE
        if comm_state in _UNHEALTHY_COMM_STATES:
            return LampAvailability.DEGRADED
        if comm_state is CommState.RECOVERY:
            return LampAvailability.RECOVERING
        if freshness is Freshness.STALE:
            return LampAvailability.UNKNOWN
        if measurement is None and not reported:
            return LampAvailability.UNKNOWN
        if has_active_fault:
            return LampAvailability.DEGRADED
        return LampAvailability.HEALTHY

    @staticmethod
    def _configured_mode(node_registration) -> Optional[ConfiguredMode]:
        snapshot = node_registration.configuration
        if not snapshot:
            return None
        parameters = snapshot.get("parameters") or {}
        index = parameters.get("configured_mode")
        try:
            return list(ConfiguredMode)[int(index)]
        except (TypeError, ValueError, IndexError):
            return None
