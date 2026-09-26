"""Group Controller simulation.

The Group Controller is the RS-485 bus master for a group of lamp nodes. It
provides:

* node registration and addressing,
* cyclic polling,
* per-node communication health (via the communication state machine),
* measurement, fault and event aggregation,
* configuration distribution,
* time synchronization,
* an **abstract** local storage/buffer for upstream outages
  (``PR-SCALABILITY-005``, ``D-037``) - no physical memory device is selected,
* store-and-forward with no silent record loss.

The failure of one lamp node must not affect the others (``PR-SCALABILITY-003``,
``PR-FAULT-012``).
"""


from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from ..authorization import Actor, AuthorizationService
from ..comm.bus import InMemoryBus
from ..comm.frame import BROADCAST_DESTINATION, MASTER_ADDRESS, Frame
from ..comm.state_machine import CommunicationStateMachine
from ..command import Command, CommandRecord, CommandService
from ..enums import (
    CommState,
    CommandType,
    EventSeverity,
    EventSource,
    EventType,
    MessageType,
    RecordType,
)
from ..errors import ConfigurationError
from ..event import Event, EventLog
from ..fault import Fault
from ..identity import BusAddress, DeviceIdentity, Identifier
from ..measurement import Measurement
from ..storage import RecordStore, RetentionPolicy, StorageRecord
from ..time_model import LogicalClock, Timestamp


class UpstreamLink:
    """Abstract upstream connectivity toward the Master Control Center."""

    def available(self) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def upload(self, record: StorageRecord) -> bool:  # pragma: no cover - interface
        raise NotImplementedError


class InMemoryUpstreamLink(UpstreamLink):
    """A deterministic, injectable upstream link."""

    def __init__(self, available: bool = True) -> None:
        self._available = available
        self.uploaded: List[int] = []
        self.failed: List[int] = []

    def available(self) -> bool:
        return self._available

    def set_available(self, available: bool) -> None:
        self._available = available

    def upload(self, record: StorageRecord) -> bool:
        if not self._available:
            self.failed.append(record.sequence_number)
            return False
        self.uploaded.append(record.sequence_number)
        return True


@dataclass
class GroupControllerConfig:
    """Group-level configuration.

    Only group-scope settings live here; per-lamp settings stay in
    :class:`~sslv1.configuration.LampConfiguration`.
    """

    max_nodes: int = 16
    poll_timeout_ticks: int = 500
    poll_retry_count: int = 2
    storage_capacity: Optional[int] = None

    def validated(self) -> "GroupControllerConfig":
        if self.max_nodes < 1:
            raise ConfigurationError("max_nodes must be at least 1")
        if self.poll_timeout_ticks <= 0:
            raise ConfigurationError("poll_timeout_ticks must be positive")
        if self.poll_retry_count < 0:
            raise ConfigurationError("poll_retry_count must be non-negative")
        return self


@dataclass
class NodeRegistration:
    """A registered lamp node and its runtime state."""

    lamp_id: Identifier
    bus_address: BusAddress
    comm: CommunicationStateMachine = field(
        default_factory=lambda: CommunicationStateMachine(retry_limit=2)
    )
    pending_requests: List[Frame] = field(default_factory=list)
    awaiting_response: bool = False
    last_seen_ticks: Optional[int] = None
    last_measurement: Optional[Measurement] = None
    last_fault: Optional[Fault] = None


class GroupController:
    """Digital model of the Group Controller."""

    def __init__(
        self,
        identity: DeviceIdentity,
        config: Optional[GroupControllerConfig] = None,
        clock: Optional[LogicalClock] = None,
        bus: Optional[InMemoryBus] = None,
        upstream: Optional[UpstreamLink] = None,
        authorizer: Optional[AuthorizationService] = None,
    ) -> None:
        self.identity = identity
        self.config = (config or GroupControllerConfig()).validated()
        self.clock = clock or LogicalClock()
        self.bus = bus or InMemoryBus()
        self.upstream = upstream or InMemoryUpstreamLink()
        self.events = EventLog()
        self.storage = RecordStore(
            capacity=self.config.storage_capacity, retention=RetentionPolicy()
        )

        self._authorizer = authorizer or AuthorizationService()
        self.commands = CommandService(
            authorizer=self._authorizer,
            executor=self._execute_command,
            verifier=self._verify_command,
            on_event=self._on_command_event,
        )

        self._registrations: Dict[int, NodeRegistration] = {}
        self._by_lamp: Dict[Identifier, NodeRegistration] = {}
        self._sequence = 0
        self._command_sequence = 0
        self._last_poll_ticks: Optional[int] = None
        self._incoming: List[Frame] = []
        self.bus.attach(MASTER_ADDRESS, self)

    # ------------------------------------------------------------------
    # identity
    # ------------------------------------------------------------------
    @property
    def site_id(self) -> Identifier:
        return self.identity.site_id

    @property
    def group_id(self) -> Identifier:
        return self.identity.group_id

    # ------------------------------------------------------------------
    # node registration
    # ------------------------------------------------------------------
    def register_node(
        self, lamp_id: Identifier, bus_address: BusAddress
    ) -> NodeRegistration:
        """Register a lamp node on the bus (``PR-COMM-002``)."""
        address = int(bus_address)
        if address in self._registrations:
            raise ConfigurationError(
                "bus address %d is already registered to lamp %s"
                % (address, self._registrations[address].lamp_id)
            )
        if len(self._registrations) >= self.config.max_nodes:
            raise ConfigurationError(
                "group already holds the configured maximum of %d nodes"
                % self.config.max_nodes
            )
        if lamp_id in self._by_lamp:
            raise ConfigurationError("lamp %s is already registered" % lamp_id)

        registration = NodeRegistration(
            lamp_id=lamp_id,
            bus_address=bus_address,
            comm=CommunicationStateMachine(
                retry_limit=self.config.poll_retry_count
            ),
        )
        self._registrations[address] = registration
        self._by_lamp[lamp_id] = registration
        self._record_event(
            EventType.NODE_STARTED,
            EventSource.SYSTEM,
            EventSeverity.INFO,
            "node %s registered at bus address %d" % (lamp_id, address),
        )
        return registration

    def unregister_node(self, bus_address: int) -> None:
        registration = self._registrations.pop(bus_address, None)
        if registration is not None:
            self._by_lamp.pop(registration.lamp_id, None)

    @property
    def registrations(self) -> Tuple[NodeRegistration, ...]:
        return tuple(
            self._registrations[address] for address in sorted(self._registrations)
        )

    def registration_for(self, lamp_id: Identifier) -> Optional[NodeRegistration]:
        return self._by_lamp.get(lamp_id)

    @property
    def node_count(self) -> int:
        return len(self._registrations)

    # ------------------------------------------------------------------
    # polling
    # ------------------------------------------------------------------
    def poll(self, message_type: MessageType = MessageType.STATUS_REQUEST) -> Dict[int, bool]:
        """Poll every registered node once.

        Returns a mapping of bus address to whether a response was received.
        A silent node does not prevent the other nodes from being polled
        (``PR-SCALABILITY-003``).
        """
        results: Dict[int, bool] = {}
        for address in sorted(self._registrations):
            registration = self._registrations[address]
            self._sequence += 1
            frame = Frame(
                source=MASTER_ADDRESS,
                destination=address,
                message_type=message_type,
                sequence=self._sequence,
            )
            registration.pending_requests.append(frame)
            registration.awaiting_response = True
            delivered = self.bus.send(frame)
            if not delivered:
                registration.comm.record_failure()
                registration.awaiting_response = False
                results[address] = False
                continue
            results[address] = True
        self._last_poll_ticks = self.clock.ticks
        return results

    def collect_responses(self) -> List[Frame]:
        """Handle frames received from nodes and return responses to send."""
        responses: List[Frame] = []
        while self._incoming:
            frame = self._incoming.pop(0)
            response = self._handle_frame(frame)
            if response is not None:
                responses.append(response)
        return responses

    # ------------------------------------------------------------------
    # frame handling
    # ------------------------------------------------------------------
    def receive(self, frame: Frame) -> None:
        self._incoming.append(frame)

    def _handle_frame(self, frame: Frame) -> Optional[Frame]:
        registration = self._registrations.get(frame.source)
        if registration is None:
            self._record_event(
                EventType.FRAME_REJECTED,
                EventSource.COMMUNICATION,
                EventSeverity.WARNING,
                "frame from unregistered address %d" % frame.source,
            )
            return None
        registration.comm.record_success()
        registration.last_seen_ticks = self.clock.ticks
        registration.awaiting_response = False

        from ..comm.protocol import decode_payload

        try:
            fields = decode_payload(frame.message_type, frame.payload)
        except Exception as exc:
            self._record_event(
                EventType.FRAME_REJECTED,
                EventSource.COMMUNICATION,
                EventSeverity.WARNING,
                "undecodable payload from %d: %s" % (frame.source, exc),
            )
            return None

        if frame.message_type is MessageType.MEASUREMENT_RESPONSE:
            self._ingest_measurement(registration, fields)
        elif frame.message_type is MessageType.FAULT_REPORT:
            self._ingest_fault(registration, fields)
        elif frame.message_type is MessageType.EVENT_REPORT:
            self._ingest_event(registration, fields)
        return None

    def _ingest_measurement(
        self, registration: NodeRegistration, fields: Dict[str, object]
    ) -> None:
        measurement = Measurement(
            timestamp=Timestamp(
                ticks=int(fields["timestamp_ticks"]),
                sync_state=self._time_sync_state(),
            ),
            site_id=self.site_id,
            group_id=self.group_id,
            lamp_id=registration.lamp_id,
            operating_mode=fields["operating_mode"],
            commanded_state=fields["commanded_state"],
            switching_feedback=fields["switching_feedback"],
            actual_state=fields["actual_state"],
            voltage=float(fields["voltage_mv"]) / 1000.0,
            current=float(fields["current_ma"]) / 1000.0,
            power=float(fields["power_mw"]) / 1000.0,
            energy=float(fields["energy_mwh"]) / 1000.0,
            light_level=float(fields["light_level"]),
            sensor_status=fields["sensor_status"],
            communication_status=self._comm_status(registration),
            controller_status=fields["controller_status"],
        )
        registration.last_measurement = measurement
        self._buffer_record(RecordType.MEASUREMENT, measurement.to_dict())

    def _ingest_fault(
        self, registration: NodeRegistration, fields: Dict[str, object]
    ) -> None:
        self._buffer_record(
            RecordType.FAULT,
            {
                "lamp_id": str(registration.lamp_id),
                "fault_id": fields.get("fault_id"),
                "fault_type": str(fields.get("fault_type")),
                "diagnostic_classification": str(fields.get("diagnostic_classification")),
                "fault_state": str(fields.get("fault_state")),
                "notification_state": str(fields.get("notification_state")),
                "severity": str(fields.get("severity")),
                "confirmation_count": fields.get("confirmation_count"),
            },
        )

    def _ingest_event(
        self, registration: NodeRegistration, fields: Dict[str, object]
    ) -> None:
        self._buffer_record(
            RecordType.EVENT,
            {
                "lamp_id": str(registration.lamp_id),
                "event_id": fields.get("event_id"),
                "event_type": str(fields.get("event_type")),
                "severity": fields.get("severity"),
                "reason": fields.get("reason"),
            },
        )

    # ------------------------------------------------------------------
    # command forwarding
    # ------------------------------------------------------------------
    def forward_control(
        self,
        lamp_id: Identifier,
        subtype,
        actor: Actor,
        command_id: Optional[str] = None,
        parameter: int = 0,
        target_state=None,
    ) -> CommandRecord:
        """Forward a control command to a node via ``CONTROL_COMMAND``."""
        registration = self._require_registration(lamp_id)
        self._command_sequence += 1
        command = Command(
            command_id=command_id or "gc-%s-%04d" % (lamp_id, self._command_sequence),
            command_type=CommandType.SET_MODE,
            subtype=subtype,
            target=self.identity.with_lamp(lamp_id),
            actor=actor,
            created_ticks=self.clock.ticks,
            parameters={"parameter": parameter},
        )
        self._sequence += 1
        frame = Frame(
            source=MASTER_ADDRESS,
            destination=int(registration.bus_address),
            message_type=MessageType.CONTROL_COMMAND,
            payload=_encode_control(subtype, command.command_id, parameter, target_state),
            sequence=self._sequence,
        )
        registration.pending_requests.append(frame)
        self.bus.send(frame)
        return self.commands.submit(command, self.clock.ticks)

    def distribute_configuration(
        self,
        lamp_id: Identifier,
        parameters: Dict[str, int],
        actor: Actor,
        config_version: int = 1,
    ) -> CommandRecord:
        """Push configuration to a node (``PR-CONFIG-002``)."""
        registration = self._require_registration(lamp_id)
        self._command_sequence += 1
        command = Command(
            command_id="gc-config-%s-%04d" % (lamp_id, self._command_sequence),
            command_type=CommandType.WRITE_CONFIG,
            target=self.identity.with_lamp(lamp_id),
            actor=actor,
            created_ticks=self.clock.ticks,
            parameters=dict(parameters),
        )
        self._sequence += 1
        frame = Frame(
            source=MASTER_ADDRESS,
            destination=int(registration.bus_address),
            message_type=MessageType.CONFIG_WRITE,
            payload=_encode_config_write(config_version, parameters),
            sequence=self._sequence,
        )
        registration.pending_requests.append(frame)
        self.bus.send(frame)
        return self.commands.submit(command, self.clock.ticks)

    def synchronize_time(self, master_ticks: Optional[int] = None) -> Dict[int, bool]:
        """Distribute time to every node (``PR-TIME-003``)."""
        ticks = self.clock.ticks if master_ticks is None else master_ticks
        results: Dict[int, bool] = {}
        self._sequence += 1
        frame = Frame(
            source=MASTER_ADDRESS,
            destination=BROADCAST_DESTINATION,
            message_type=MessageType.TIME_SYNC,
            payload=_encode_time_sync(ticks),
            sequence=self._sequence,
        )
        for address in sorted(self._registrations):
            targeted = Frame(
                source=frame.source,
                destination=address,
                message_type=frame.message_type,
                payload=frame.payload,
                sequence=frame.sequence,
            )
            results[address] = self.bus.send(targeted)
        self._record_event(
            EventType.TIME_SYNCHRONIZED,
            EventSource.TIME,
            EventSeverity.INFO,
            "time distributed to %d nodes at tick %d" % (len(results), ticks),
        )
        return results

    def identify(self, lamp_id: Identifier) -> None:
        registration = self._require_registration(lamp_id)
        self._sequence += 1
        self.bus.send(
            Frame(
                source=MASTER_ADDRESS,
                destination=int(registration.bus_address),
                message_type=MessageType.IDENTIFY,
                sequence=self._sequence,
            )
        )

    # ------------------------------------------------------------------
    # aggregation
    # ------------------------------------------------------------------
    def measurements(self) -> Tuple[Measurement, ...]:
        return tuple(
            r.last_measurement for r in self.registrations if r.last_measurement is not None
        )

    def aggregate_power(self) -> float:
        return sum((m.power or 0.0) for m in self.measurements())

    def aggregate_energy(self) -> float:
        return sum((m.energy or 0.0) for m in self.measurements())

    def communication_summary(self) -> Dict[str, int]:
        summary = {state.value: 0 for state in CommState}
        for registration in self.registrations:
            summary[registration.comm.state.value] += 1
        return summary

    def degraded_nodes(self) -> Tuple[Identifier, ...]:
        return tuple(
            r.lamp_id
            for r in self.registrations
            if r.comm.state
            in (CommState.DEGRADED, CommState.COMM_FAULT, CommState.RECOVERY)
        )

    # ------------------------------------------------------------------
    # store-and-forward
    # ------------------------------------------------------------------
    def _buffer_record(self, record_type: RecordType, payload: Dict[str, object]) -> None:
        try:
            self.storage.create(
                record_type=record_type,
                payload=payload,
                timestamp=Timestamp(ticks=self.clock.ticks, sync_state=self._time_sync_state()),
                device_id=self.identity.device_id,
            )
        except Exception as exc:
            self._record_event(
                EventType.STORAGE_FULL,
                EventSource.STORAGE,
                EventSeverity.ERROR,
                "record not buffered: %s" % exc,
            )

    def forward_upstream(self) -> Dict[str, int]:
        """Attempt to upload every pending record.

        Records are only removed from the pending upload queue after upstream
        confirmation. Nothing is ever deleted by uploading
        (``PR-STORAGE-009``).
        """
        uploaded = 0
        confirmed = 0
        failed = 0
        for record in list(self.storage.pending_upload):
            if not self.upstream.available():
                failed += 1
                continue
            self.storage.mark_uploaded(record.sequence_number)
            if self.upstream.upload(record):
                self.storage.mark_confirmed(record.sequence_number)
                uploaded += 1
                confirmed += 1
            else:
                failed += 1
        if confirmed:
            self._record_event(
                EventType.RECORD_CONFIRMED,
                EventSource.STORAGE,
                EventSeverity.INFO,
                "%d records confirmed upstream and moved out of the pending queue"
                % confirmed,
            )
        return {"uploaded": uploaded, "confirmed": confirmed, "failed": failed}

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _execute_command(self, command: Command) -> Tuple[bool, str]:
        return True, "command forwarded to node"

    def _verify_command(self, command: Command) -> Tuple[bool, str]:
        return True, "forwarding acknowledged"

    def _on_command_event(self, kind: str, record: CommandRecord, reason: str) -> None:
        mapping = {
            "COMMAND_RECEIVED": (EventType.COMMAND_RECEIVED, EventSeverity.INFO),
            "COMMAND_EXECUTED": (EventType.COMMAND_EXECUTED, EventSeverity.INFO),
            "COMMAND_REJECTED": (EventType.COMMAND_REJECTED, EventSeverity.WARNING),
            "COMMAND_DUPLICATE": (EventType.COMMAND_DUPLICATE, EventSeverity.WARNING),
            "COMMAND_VERIFIED": (EventType.COMMAND_VERIFIED, EventSeverity.INFO),
            "COMMAND_VERIFICATION_FAILED": (
                EventType.COMMAND_VERIFICATION_FAILED,
                EventSeverity.ERROR,
            ),
        }
        event_type, severity = mapping.get(
            kind, (EventType.COMMAND_RECEIVED, EventSeverity.INFO)
        )
        self._record_event(
            event_type,
            EventSource.SECURITY,
            severity,
            "%s: %s" % (record.command_id, reason),
            actor=record.command.actor.actor_id,
        )

    def _record_event(
        self,
        event_type: EventType,
        source: EventSource,
        severity: EventSeverity,
        reason: str,
        data: Optional[Dict[str, object]] = None,
        actor: Optional[str] = None,
    ) -> Event:
        return self.events.record(
            timestamp=Timestamp(ticks=self.clock.ticks, sync_state=self._time_sync_state()),
            device_id=self.identity.device_id,
            event_type=event_type,
            source=source,
            severity=severity,
            reason=reason,
            site_id=self.site_id,
            group_id=self.group_id,
            event_data=data or {},
        )

    def _require_registration(self, lamp_id: Identifier) -> NodeRegistration:
        registration = self._by_lamp.get(lamp_id)
        if registration is None:
            raise ConfigurationError("lamp %s is not registered in this group" % lamp_id)
        return registration

    def _time_sync_state(self):
        from ..enums import TimeSyncState

        return TimeSyncState.SYNCHRONIZED

    def _comm_status(self, registration: NodeRegistration):
        from ..enums import CommunicationStatus

        mapping = {
            CommState.COMM_HEALTHY: CommunicationStatus.COMM_HEALTHY,
            CommState.RETRY: CommunicationStatus.RETRY,
            CommState.DEGRADED: CommunicationStatus.DEGRADED,
            CommState.COMM_FAULT: CommunicationStatus.COMM_FAULT,
            CommState.RECOVERY: CommunicationStatus.RECOVERY,
        }
        return mapping[registration.comm.state]

    def _controller_status(self, registration: NodeRegistration):
        from ..enums import ControllerStatus

        return ControllerStatus.NORMAL

    def snapshot(self) -> Dict[str, object]:
        return {
            "group_id": str(self.group_id),
            "nodes": self.node_count,
            "communication": self.communication_summary(),
            "aggregate_power": self.aggregate_power(),
            "aggregate_energy": self.aggregate_energy(),
            "stored_records": len(self.storage),
            "pending_upload": len(self.storage.pending_upload),
            "retained_records": len(self.storage.retained),
            "upstream_available": self.upstream.available(),
            "events": len(self.events),
        }


# --------------------------------------------------------------------------
# payload helpers (kept here to avoid importing the codec into the controller)
# --------------------------------------------------------------------------
def _encode_control(subtype, command_id: str, parameter: int, target_state) -> bytes:
    from ..comm.protocol import encode_payload
    from ..enums import LampState

    state = target_state if target_state is not None else LampState.UNKNOWN
    return encode_payload(
        MessageType.CONTROL_COMMAND,
        {"subtype": subtype, "target_state": state, "command_id": command_id,
         "parameter": parameter},
    )


def _encode_config_write(config_version: int, parameters: Dict[str, int]) -> bytes:
    from ..comm.protocol import encode_payload

    return encode_payload(
        MessageType.CONFIG_WRITE,
        {"config_version": config_version, "parameters": parameters},
    )


def _encode_time_sync(ticks: int) -> bytes:
    from ..comm.protocol import encode_payload

    return encode_payload(MessageType.TIME_SYNC, {"master_ticks": ticks})
