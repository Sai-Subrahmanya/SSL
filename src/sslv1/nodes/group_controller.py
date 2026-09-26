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
from ..comm.frame import MASTER_ADDRESS, Frame, PROTOCOL_VERSION
from ..comm.state_machine import CommunicationStateMachine
from ..command import Command, CommandRecord, CommandService
from ..enums import (
    CommState,
    CommandState,
    ControlSubtype,
    ConfiguredMode,
    LampState,
    OverrideState,
    Role,
    Action,
    CommandType,
    EventSeverity,
    EventSource,
    EventType,
    MessageType,
    RecordType,
)
from ..errors import ConfigurationError, ValidationError, ProtocolError, StorageError, AuthorizationError
from ..event import Event, EventLog
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
        for name in ("max_nodes", "poll_timeout_ticks", "poll_retry_count"):
            if type(getattr(self, name)) is not int:
                raise ConfigurationError(name + " must be an integer")
        if self.storage_capacity is not None and (type(self.storage_capacity) is not int or self.storage_capacity < 1):
            raise ConfigurationError("storage_capacity must be a positive integer or None")
        if self.max_nodes < 1:
            raise ConfigurationError("max_nodes must be at least 1")
        if self.poll_timeout_ticks <= 0:
            raise ConfigurationError("poll_timeout_ticks must be positive")
        if self.poll_retry_count < 0:
            raise ConfigurationError("poll_retry_count must be non-negative")
        return self


from ..comm.sequence import SequenceTracker


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
    sequences: SequenceTracker = field(default_factory=SequenceTracker)
    duplicate_frames: int = 0
    stale_frames: int = 0
    status: Optional[dict] = None
    configuration: Optional[dict] = None
    time_ack: Optional[dict] = None
    identity_ack: Optional[dict] = None
    heartbeat_ack: Optional[dict] = None
    last_poll_success: bool = False
    confirmed_event_id: int = 0
    received_event_ids: set = field(default_factory=set)
    confirmed_record_sequence: int = 0
    received_record_sequences: set = field(default_factory=set)


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
            capacity=self.config.storage_capacity, retention=RetentionPolicy(),
            on_delete=self._on_record_deleted
        )

        self._authorizer = authorizer or AuthorizationService()
        self.commands = CommandService(
            authorizer=self._authorizer,
            executor=self._execute_command,
            verifier=self._verify_command,
            on_event=self._on_command_event,
        )

        self._pending = {}
        self._pending_commands = {}
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
        for key, pending in list(self._pending.items()):
            if key[0] == bus_address:
                record = pending['record']
                if record is not None:
                    self.commands.advance(record, CommandState.FAILED, self.clock.ticks, "node unregistered")
                self._finish_request(key, False)
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
    def _next_sequence(self) -> int:
        self._sequence = (self._sequence + 1) & 0xFFFF
        if any(seq == self._sequence for _, seq in self._pending):
            raise ProtocolError("sequence still in flight")
        return self._sequence

    def _send_request(self, registration, message_type, payload=b"", record=None):
        if message_type is MessageType.MEASUREMENT_REQUEST:
            from ..comm.protocol import encode_payload
            payload = encode_payload(message_type, {"confirmed_record_sequence": registration.confirmed_record_sequence})
        if message_type is MessageType.EVENT_REPORT:
            payload = registration.confirmed_event_id.to_bytes(4, "big")
        frame = Frame(MASTER_ADDRESS, int(registration.bus_address), message_type,
                      payload, self._next_sequence())
        expected = {MessageType.STATUS_REQUEST: MessageType.STATUS_RESPONSE,
                    MessageType.MEASUREMENT_REQUEST: MessageType.MEASUREMENT_RESPONSE,
                    MessageType.CONTROL_COMMAND: MessageType.CONTROL_ACK,
                    MessageType.CONFIG_READ: MessageType.CONFIG_ACK,
                    MessageType.CONFIG_WRITE: MessageType.CONFIG_ACK,
                    MessageType.TIME_SYNC: MessageType.TIME_ACK,
                    MessageType.IDENTIFY: MessageType.IDENTIFY_ACK,
                    MessageType.HEARTBEAT: MessageType.HEARTBEAT_ACK,
                    MessageType.FAULT_REPORT: MessageType.FAULT_REPORT,
                    MessageType.EVENT_REPORT: MessageType.EVENT_REPORT}[message_type]
        pending = dict(frame=frame, expected=expected, record=record, retries=0,
                       deadline=self.clock.ticks + self.config.poll_timeout_ticks,
                       expires=self.clock.ticks + self.config.poll_timeout_ticks * (self.config.poll_retry_count + 1))
        self._pending[(frame.destination, frame.sequence)] = pending
        if record is not None:
            self._pending_commands[record.command_id] = pending
        registration.pending_requests.append(frame)
        registration.awaiting_response = True
        if record is not None:
            record.transmitted_ticks = self.clock.ticks
        self._transmit(frame)
        return pending

    def _transmit(self, frame):
        try:
            return self.bus.send(frame)
        except ProtocolError as exc:
            self._record_event(EventType.FRAME_REJECTED, EventSource.COMMUNICATION,
                               EventSeverity.WARNING, str(exc))
            return False

    def _finish_request(self, key, success):
        pending = self._pending.pop(key)
        frame = pending['frame']
        registration = self._registrations.get(frame.destination)
        if registration:
            if frame in registration.pending_requests:
                registration.pending_requests.remove(frame)
            registration.awaiting_response = bool(registration.pending_requests)
            registration.last_poll_success = success
        if pending['record'] is not None:
            self._pending_commands.pop(pending['record'].command_id, None)

    def service_timeouts(self) -> None:
        for key, pending in list(self._pending.items()):
            if self.clock.ticks < pending['deadline']:
                continue
            registration = self._registrations.get(key[0])
            if registration is None:
                self._finish_request(key, False)
                continue
            previous = registration.comm.state
            registration.comm.record_failure()
            self._record_event(EventType.COMM_STATE_CHANGED, EventSource.COMMUNICATION,
                               EventSeverity.WARNING, "request deadline elapsed",
                               data={"address": key[0], "previous": previous.value,
                                     "current": registration.comm.state.value})
            if pending['retries'] < self.config.poll_retry_count and self.clock.ticks < pending['expires']:
                pending['retries'] += 1
                pending['deadline'] = min(self.clock.ticks + self.config.poll_timeout_ticks, pending['expires'])
                self._transmit(pending['frame'])
            else:
                # Complete the documented failure path even for retry_count=0.
                registration.comm.retry_exhausted()
                self._record_event(EventType.COMM_FAULT_DETECTED, EventSource.COMMUNICATION,
                                   EventSeverity.ERROR, "node retries exhausted", data={"address": key[0]})
                record = pending['record']
                if record is not None and record.state in (CommandState.RECEIVED, CommandState.EXECUTED, CommandState.ACKNOWLEDGED):
                    self.commands.advance(record, CommandState.FAILED, self.clock.ticks,
                                          "remote response/verification timeout")
                self._finish_request(key, False)

    def poll(self, message_type: MessageType = MessageType.STATUS_REQUEST) -> Dict[int, bool]:
        """Start one request per idle node; True means a validated prior response.

        Delivery is never response receipt. Advance the logical clock and call
        collect_responses/service_timeouts to drive timeout and retry behavior.
        """
        if message_type not in (MessageType.STATUS_REQUEST, MessageType.MEASUREMENT_REQUEST,
                                MessageType.FAULT_REPORT, MessageType.EVENT_REPORT,
                                MessageType.HEARTBEAT, MessageType.CONFIG_READ):
            raise ProtocolError("not a poll request")
        self.collect_responses()
        results = {}
        for registration in self.registrations:
            address = int(registration.bus_address)
            results[address] = registration.last_poll_success
            if not registration.awaiting_response:
                registration.last_poll_success = False
                self._send_request(registration, message_type)
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
        self.service_timeouts()
        return responses

    # ------------------------------------------------------------------
    # frame handling
    # ------------------------------------------------------------------
    def receive(self, frame: Frame) -> None:
        self._incoming.append(frame)

    def _handle_frame(self, frame: Frame) -> Optional[Frame]:
        from ..comm.protocol import decode_payload
        registration = self._registrations.get(frame.source)
        try:
            if registration is None or frame.destination != MASTER_ADDRESS or frame.protocol_version != PROTOCOL_VERSION:
                raise ProtocolError("unregistered source, wrong destination or unsupported version")
            verdict = registration.sequences.classify(frame.sequence)
            if verdict != "new":
                if verdict == "duplicate":
                    registration.duplicate_frames += 1
                    event_type = EventType.DUPLICATE_FRAME_DETECTED
                else:
                    registration.stale_frames += 1
                    event_type = EventType.STALE_FRAME_DETECTED
                self._record_event(event_type, EventSource.COMMUNICATION, EventSeverity.WARNING,
                                   "%s frame from %d sequence %d" % (verdict, frame.source, frame.sequence))
                return None
            fields = decode_payload(frame.message_type, frame.payload)
            key = (frame.source, fields.get('request_sequence', -1))
            pending = self._pending.get(key)
            if pending is not None and self.clock.ticks >= pending['expires']:
                raise ProtocolError("response arrived after final transaction deadline")
            if pending is None or pending['expected'] is not frame.message_type:
                raise ProtocolError("response does not match an outstanding request")
            complete = True
            if frame.message_type is MessageType.CONTROL_ACK:
                complete = self._handle_control_ack(pending, fields)
            elif frame.message_type is MessageType.CONFIG_ACK:
                record = pending['record']
                if record is not None:
                    version = record.command.parameters['config_version']
                    if fields['config_version'] != version:
                        raise ProtocolError("configuration version mismatch")
                    if not fields['accepted']:
                        self.commands.advance(record, CommandState.FAILED, self.clock.ticks, fields['reason'])
                    else:
                        expected = record.command.parameters['parameters']
                        if any(fields['parameters'].get(k) != v for k, v in expected.items()):
                            raise ProtocolError("configuration ACK does not prove applied parameters")
                        self._acknowledge(record)
                        self.commands.advance(record, CommandState.ACTUAL_STATE_VERIFIED, self.clock.ticks,
                                              "node reports applied configuration readback")
                registration.configuration = dict(fields)
            elif frame.message_type is MessageType.STATUS_RESPONSE:
                registration.status = dict(fields)
            elif frame.message_type is MessageType.MEASUREMENT_RESPONSE:
                self._ingest_measurement(registration, fields)
            elif frame.message_type is MessageType.FAULT_REPORT:
                self._ingest_fault(registration, fields)
            elif frame.message_type is MessageType.EVENT_REPORT:
                self._ingest_event(registration, fields)
            elif frame.message_type is MessageType.TIME_ACK:
                request_fields = decode_payload(MessageType.TIME_SYNC, pending['frame'].payload)
                if fields['master_ticks'] != request_fields['master_ticks'] or fields['local_ticks'] != fields['master_ticks']:
                    raise ProtocolError("time ACK did not synchronize to requested tick")
                registration.time_ack = dict(fields)
                self._record_event(EventType.TIME_SYNCHRONIZED, EventSource.TIME, EventSeverity.INFO,
                                   "node time synchronization verified", data=dict(fields, address=frame.source),
                                   actor=request_fields["actor"].actor_id)
            elif frame.message_type is MessageType.IDENTIFY_ACK:
                if (fields['lamp_id'], fields['group_id'], fields['site_id'], fields['product_id']) != (
                        str(registration.lamp_id), str(self.group_id), str(self.site_id), str(self.identity.product_id)):
                    raise ProtocolError("identity mismatch")
                registration.identity_ack = dict(fields)
            elif frame.message_type is MessageType.HEARTBEAT_ACK:
                registration.heartbeat_ack = dict(fields)
            else:
                raise ProtocolError("unsupported response")
            registration.sequences.record(frame.sequence)
            registration.comm.record_success()
            registration.last_seen_ticks = self.clock.ticks
            if complete:
                self._finish_request(key, True)
        except (ProtocolError, ValueError, KeyError, TypeError, ValidationError) as exc:
            self._record_event(EventType.FRAME_REJECTED, EventSource.COMMUNICATION,
                               EventSeverity.WARNING, str(exc))
        return None

    def _acknowledge(self, record):
        if record.state is CommandState.RECEIVED:
            self.commands.advance(record, CommandState.EXECUTED, self.clock.ticks, "node execution reported")
        if record.state is CommandState.EXECUTED:
            self.commands.advance(record, CommandState.ACKNOWLEDGED, self.clock.ticks, "matched node ACK")

    def _handle_control_ack(self, pending, fields):
        record = pending['record']
        if record is None or fields['command_id'] != record.command_id:
            raise ProtocolError("command ACK identity mismatch")
        status = fields['execution_status']
        if status in (CommandState.REJECTED, CommandState.FAILED):
            self.commands.advance(record, CommandState.FAILED, self.clock.ticks, "node rejected/failed command")
            return True
        if status not in (CommandState.ACKNOWLEDGED, CommandState.ACTUAL_STATE_VERIFIED):
            raise ProtocolError("ACK does not report execution")
        subtype = record.command.subtype
        if status is CommandState.ACTUAL_STATE_VERIFIED:
            if subtype in (ControlSubtype.LAMP_ON, ControlSubtype.LAMP_OFF):
                expected = LampState.ON if subtype is ControlSubtype.LAMP_ON else LampState.OFF
                override = OverrideState.FORCE_ON if subtype is ControlSubtype.LAMP_ON else OverrideState.FORCE_OFF
                verified = (fields['actual_state'] is expected and fields['active_override'] is override
                            and fields['effective_mode'].value == override.value)
            elif subtype is ControlSubtype.RETURN_TO_AUTO:
                verified = (fields['active_override'] is OverrideState.NONE and
                            fields['effective_mode'].value == fields['configured_mode'].value)
            elif subtype is ControlSubtype.SET_MODE:
                verified = list(ConfiguredMode).index(fields['configured_mode']) == record.command.parameters['parameter']
            else:
                verified = fields['energy'] == 0
            if not verified:
                raise ProtocolError("ACK verification evidence inconsistent with requested action")
        self._acknowledge(record)
        record.evidence = dict(fields)
        if status is CommandState.ACTUAL_STATE_VERIFIED:
            self.commands.advance(record, CommandState.ACTUAL_STATE_VERIFIED, self.clock.ticks,
                                  "validated node execution and actual-state evidence")
            return True
        return False

    def _ingest_measurement(
        self, registration: NodeRegistration, fields: Dict[str, object]
    ) -> None:
        measurement = Measurement(
            timestamp=Timestamp(
                ticks=int(fields["timestamp_ticks"]),
                sync_state=fields["time_sync_state"],
            ),
            site_id=self.site_id,
            group_id=self.group_id,
            lamp_id=registration.lamp_id,
            effective_mode=fields["effective_mode"],
            commanded_state=fields["commanded_state"],
            switching_feedback=fields["switching_feedback"],
            actual_state=fields["actual_state"],
            voltage=float(fields["voltage_mv"]) / 1000.0 if fields["available_mask"] & 1 else None,
            current=float(fields["current_ma"]) / 1000.0 if fields["available_mask"] & 2 else None,
            power=float(fields["power_mw"]) / 1000.0 if fields["available_mask"] & 4 else None,
            energy=float(fields["energy_mwh"]) / 1000.0 if fields["available_mask"] & 8 else None,
            light_level=float(fields["light_level"]) if fields["available_mask"] & 16 else None,
            sensor_status=fields["sensor_status"],
            communication_status=self._comm_status(registration),
            controller_status=fields["controller_status"],
        )
        record_sequence = fields.get('record_sequence', 0)
        if record_sequence < 0:
            raise ProtocolError("invalid measurement record identity")
        if record_sequence and record_sequence in registration.received_record_sequences:
            registration.confirmed_record_sequence = record_sequence
            return
        registration.last_measurement = measurement
        stored = self._buffer_record(RecordType.MEASUREMENT, measurement.to_dict())
        if stored and record_sequence:
            registration.received_record_sequences.add(record_sequence)
            registration.confirmed_record_sequence = record_sequence

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

    def _ingest_event(self, registration, fields):
        event_id = int(fields['event_id'])
        if event_id in registration.received_event_ids:
            registration.confirmed_event_id = event_id
            return
        stored = self._buffer_record(RecordType.EVENT, {
            "lamp_id": str(registration.lamp_id), "event_id": event_id,
            "actor": fields.get("actor"), "event_type": str(fields['event_type']),
            "severity": fields['severity'], "reason": fields['reason']})
        if stored:
            registration.received_event_ids.add(event_id)
            registration.confirmed_event_id = event_id

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
            command_type={ControlSubtype.LAMP_ON: CommandType.FORCE_ON,
                          ControlSubtype.LAMP_OFF: CommandType.FORCE_OFF,
                          ControlSubtype.RETURN_TO_AUTO: CommandType.RETURN_TO_AUTO,
                          ControlSubtype.SET_MODE: CommandType.SET_MODE,
                          ControlSubtype.RESET_ENERGY: CommandType.SET_MODE}[subtype],
            subtype=subtype,
            target=self.identity.with_lamp(lamp_id),
            actor=actor,
            created_ticks=self.clock.ticks,
            parameters={"parameter": parameter},
        )
        existing = self.commands.get(command.command_id)
        record = self.commands.submit(command, self.clock.ticks, pending=True)
        if existing is not None or record.state is CommandState.REJECTED:
            return record
        from ..comm.protocol import encode_payload
        try:
            payload = encode_payload(MessageType.CONTROL_COMMAND, {
                "subtype": subtype, "target_state": target_state or LampState.UNKNOWN,
                "command_id": command.command_id, "parameter": parameter, "actor": actor})
            self._send_request(registration, MessageType.CONTROL_COMMAND, payload, record)
        except ProtocolError as exc:
            self.commands.advance(record, CommandState.FAILED, self.clock.ticks, str(exc))
        return record

    def distribute_configuration(self, lamp_id, parameters, actor, config_version=1):
        registration = self._require_registration(lamp_id)
        self._command_sequence += 1
        command = Command("gc-config-%s-%04d" % (lamp_id, self._command_sequence),
                          CommandType.WRITE_CONFIG, self.identity.with_lamp(lamp_id), actor,
                          self.clock.ticks, parameters={"config_version": config_version,
                                                       "parameters": dict(parameters)})
        record = self.commands.submit(command, self.clock.ticks, pending=True)
        if record.state is CommandState.REJECTED:
            return record
        from ..comm.protocol import encode_payload
        try:
            payload = encode_payload(MessageType.CONFIG_WRITE, {
                "config_version": config_version, "parameters": parameters, "actor": actor})
            self._send_request(registration, MessageType.CONFIG_WRITE, payload, record)
        except ProtocolError as exc:
            self.commands.advance(record, CommandState.FAILED, self.clock.ticks, str(exc))
        return record

    def synchronize_time(self, master_ticks=None, actor=None):
        actor = actor or Actor("anonymous", Role.VIEWER, False)
        if not self._authorizer.is_authorized(actor, Action.ADMINISTER):
            self._record_event(EventType.COMMAND_REJECTED, EventSource.SECURITY,
                               EventSeverity.WARNING, "time distribution denied", actor=actor.actor_id)
            raise AuthorizationError("time distribution requires ADMINISTER")
        from ..comm.protocol import encode_payload
        ticks = self.clock.ticks if master_ticks is None else master_ticks
        results = {}
        for registration in self.registrations:
            self._send_request(registration, MessageType.TIME_SYNC,
                               encode_payload(MessageType.TIME_SYNC, {"master_ticks": ticks, "actor": actor}))
            results[int(registration.bus_address)] = False
        return results

    def identify(self, lamp_id):
        self._send_request(self._require_registration(lamp_id), MessageType.IDENTIFY)

    def read_configuration(self, lamp_id):
        self._send_request(self._require_registration(lamp_id), MessageType.CONFIG_READ)

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
    def _buffer_record(self, record_type: RecordType, payload: Dict[str, object]) -> bool:
        try:
            self.storage.create(
                record_type=record_type,
                payload=payload,
                timestamp=Timestamp(ticks=self.clock.ticks, sync_state=self._time_sync_state()),
                device_id=self.identity.device_id,
            )
            return True
        except StorageError as exc:
            self._record_event(
                EventType.STORAGE_FULL,
                EventSource.STORAGE,
                EventSeverity.ERROR,
                "record not buffered: %s" % exc,
            )
            return False

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
            try:
                self.storage.mark_uploaded(record.sequence_number)
            except StorageError as exc:
                failed += 1
                self._record_event(EventType.RECORD_CORRUPT, EventSource.STORAGE, EventSeverity.ERROR,
                                   str(exc), data={"sequence_number": record.sequence_number})
                continue
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
        return False, "remote commands require pending request dispatch"

    def _verify_command(self, command: Command) -> Tuple[bool, str]:
        return False, "remote verification requires node evidence"

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

    def _on_record_deleted(self, record, actor, ticks):
        self._record_event(EventType.RECORD_DELETED, EventSource.STORAGE, EventSeverity.WARNING,
                           "retained record deleted", actor=actor,
                           data={"sequence_number": record.sequence_number, "deleted_ticks": ticks})

    def _record_event(
        self,
        event_type: EventType,
        source: EventSource,
        severity: EventSeverity,
        reason: str,
        data: Optional[Dict[str, object]] = None,
        actor: Optional[str] = None,
    ) -> Event:
        event = self.events.record(
            timestamp=Timestamp(ticks=self.clock.ticks, sync_state=self._time_sync_state()),
            device_id=self.identity.device_id,
            event_type=event_type,
            source=source,
            severity=severity,
            reason=reason,
            site_id=self.site_id,
            group_id=self.group_id,
            event_data=data or {},
            actor=actor,
        )

        if source in (EventSource.SECURITY, EventSource.CONFIGURATION, EventSource.TIME,
                      EventSource.COMMUNICATION):
            try:
                self.storage.create(RecordType.EVENT, {
                    "group_event_id": event.event_id, "event_type": event_type.value,
                    "actor": actor, "reason": reason, "data": data or {}},
                    event.timestamp, self.identity.device_id)
            except StorageError as exc:
                self.events.record(event.timestamp, self.identity.device_id,
                                   EventType.STORAGE_FULL, EventSource.STORAGE, EventSeverity.ERROR,
                                   "audit record not buffered: %s" % exc,
                                   event_data={"group_event_id": event.event_id})
        return event

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
            "storage_full": self.storage.is_full,
        }
