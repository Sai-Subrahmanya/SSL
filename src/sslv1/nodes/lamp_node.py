"""Lamp Node simulation.

A :class:`LampNode` is the digital counterpart of one physical lamp node. It
composes the domain layer (control, measurement, diagnostics, faults,
notification, events, storage, commands, time, communication state) and adds
no hardware coupling whatsoever.

Readings arrive through :class:`LampNodeSources`, an abstract input record.
The simulation supplies it; a future hardware abstraction layer would supply
the same structure from real sensors.
"""


from dataclasses import dataclass, replace
from typing import Dict, List, Optional, Tuple

from ..authorization import Actor, AuthorizationService
from ..comm.bus import BusEndpoint, InMemoryBus
from ..comm.frame import Frame
from ..comm.state_machine import CommunicationStateMachine
from ..command import Command, CommandRecord, CommandService
from ..configuration import LampConfiguration
from ..control import ControlDecision, ControlModel, ProtectionState
from ..diagnostics import DiagnosticEngine, DiagnosticEvidence, DiagnosticResult
from ..enums import (
    Action,
    CommandType,
    CommunicationStatus,
    ConfiguredMode,
    ControlSubtype,
    ControllerStatus,
    EventSeverity,
    EventSource,
    EventType,
    LampState,
    MessageType,
    OverrideState,
    RecordType,
    SensorStatus,
)
from ..errors import ConfigurationError
from ..event import Event, EventLog
from ..fault import Fault, FaultEngine
from ..identity import BusAddress, DeviceIdentity, Identifier
from ..measurement import Measurement, MeasurementAssessment, MeasurementValidator
from ..notification import NotificationEngine
from ..storage import RecordStore, RetentionPolicy
from ..time_model import LogicalClock, TimeModel, Timestamp

#: Default conversion used for energy accumulation (1000 logical ticks/second).
DEFAULT_TICKS_PER_SECOND = 1000
DEFAULT_TICKS_PER_HOUR = DEFAULT_TICKS_PER_SECOND * 3600


@dataclass(frozen=True)
class LampNodeSources:
    """Abstract hardware-independent readings for one control cycle."""

    voltage: Optional[float] = None
    current: Optional[float] = None
    power: Optional[float] = None
    light_level: Optional[float] = None
    switching_feedback: LampState = LampState.UNKNOWN
    sensor_status: SensorStatus = SensorStatus.VALID
    controller_status: ControllerStatus = ControllerStatus.NORMAL


class LampNode(BusEndpoint):
    """Digital model of a single lamp node."""

    def __init__(
        self,
        identity: DeviceIdentity,
        bus_address: BusAddress,
        config: LampConfiguration,
        clock: Optional[LogicalClock] = None,
        bus: Optional[InMemoryBus] = None,
        authorizer: Optional[AuthorizationService] = None,
        ticks_per_hour: int = DEFAULT_TICKS_PER_HOUR,
        storage_capacity: Optional[int] = None,
    ) -> None:
        config.validated()
        if config.lamp_id != (identity.lamp_id or identity.device_id):
            raise ConfigurationError(
                "configuration belongs to lamp %s but the node identity is %s"
                % (config.lamp_id, identity.device_id)
            )
        if int(config.bus_address) != int(bus_address):
            raise ConfigurationError(
                "configuration bus address %s does not match node address %s"
                % (int(config.bus_address), int(bus_address))
            )
        self.identity = identity
        self.bus_address = bus_address
        self.config = config
        self.clock = clock or LogicalClock()
        self.bus = bus
        self.ticks_per_hour = ticks_per_hour

        self.time = TimeModel(clock=self.clock, device_id=identity.device_id)
        self.protection = ProtectionState()
        self.control = ControlModel(config=config, protection=self.protection)
        self.events = EventLog()
        self.validator = MeasurementValidator(config)
        self.diagnostics = DiagnosticEngine(config)
        self.faults = FaultEngine(config, on_event=self._on_fault_event)
        self.notifications = NotificationEngine(config, on_event=self._on_fault_event)
        self.storage = RecordStore(
            capacity=storage_capacity, retention=RetentionPolicy()
        )
        self.comm = CommunicationStateMachine(retry_limit=config.comm_retry_count)
        self._authorizer = authorizer or AuthorizationService()
        self.commands = CommandService(
            authorizer=self._authorizer,
            executor=self._execute_command,
            verifier=self._verify_command,
            on_event=self._on_command_event,
        )

        self._energy = 0.0
        self._measurement_sequence = 0
        self._measurements: List[Measurement] = []
        self._last_measurement: Optional[Measurement] = None
        self._last_decision: Optional[ControlDecision] = None
        self._last_assessment: Optional[MeasurementAssessment] = None
        self._last_diagnostic: Optional[DiagnosticResult] = None
        self._last_report_ticks: Optional[int] = None
        self._comm_status = CommunicationStatus.COMM_HEALTHY
        self._incoming: List[Frame] = []
        self._reported_events: Dict[int, bool] = {}

        if bus is not None:
            bus.attach(int(bus_address), self)

    # ------------------------------------------------------------------
    # identity
    # ------------------------------------------------------------------
    @property
    def lamp_id(self) -> Identifier:
        return self.identity.lamp_id or self.identity.device_id

    @property
    def measurements(self) -> Tuple[Measurement, ...]:
        """Measurements produced by this node, in production order."""
        return tuple(self._measurements)

    @property
    def last_measurement(self) -> Optional[Measurement]:
        return self._last_measurement

    @property
    def site_id(self) -> Identifier:
        return self.identity.site_id

    @property
    def group_id(self) -> Identifier:
        return self.identity.group_id

    # ------------------------------------------------------------------
    # lifecycle
    # ------------------------------------------------------------------
    def start(self, ticks: Optional[int] = None) -> None:
        """Start the node, restoring the configured restart state."""
        ticks = self.clock.ticks if ticks is None else ticks
        self.control.apply_override(OverrideState.NONE)
        self._apply_restart_default(ticks)
        self._record_event(
            EventType.NODE_STARTED,
            EventSource.SYSTEM,
            EventSeverity.INFO,
            "node started; configured_mode=%s" % self.control.configured_mode.value,
            ticks=ticks,
        )

    def restart(self, ticks: Optional[int] = None) -> None:
        """Simulate a watchdog reset / restart (``PR-CONTROL-005``)."""
        ticks = self.clock.ticks if ticks is None else ticks
        self.control.apply_override(OverrideState.NONE)
        self._apply_restart_default(ticks)
        self._record_event(
            EventType.NODE_RESTARTED,
            EventSource.SYSTEM,
            EventSeverity.WARNING,
            "watchdog restart; state restored to %s"
            % self.config.restart_default_state.value,
            ticks=ticks,
        )

    def _apply_restart_default(self, ticks: int) -> None:
        state = self.config.restart_default_state
        self.control.protection.active = False
        if state is LampState.ON:
            self.control._lamp_is_on = True
        else:
            self.control._lamp_is_on = False

    def set_protection(
        self,
        active: bool,
        state: LampState = LampState.OFF,
        reason: str = "",
    ) -> None:
        """Assert or clear a protection condition (test/inspection hook).

        V1 defines no automatic protective shutdown condition, so this is the
        only way a protection condition enters the model.
        """
        self.protection.active = bool(active)
        self.protection.safe_state = state
        self.protection.reason = reason
        if active:
            self.control.protection = self.protection

    # ------------------------------------------------------------------
    # control cycle
    # ------------------------------------------------------------------
    def step(self, sources: LampNodeSources, ticks: Optional[int] = None) -> ControlDecision:
        """Run one deterministic control/measurement/diagnostic cycle."""
        ticks = self.clock.ticks if ticks is None else ticks
        self.time.advance(self.config.measurement_interval_ticks)

        previous_state = self.control.lamp_is_on
        decision = self.control.decide(sources.light_level, ticks)
        self._last_decision = decision
        self._emit_control_events(decision, previous_state, ticks)

        self._accumulate_energy(sources, ticks)
        measurement = self._build_measurement(sources, decision, ticks)
        self._measurements.append(measurement)
        self._last_measurement = measurement

        assessment = self.validator.assess(measurement)
        self._last_assessment = assessment
        if assessment.has_issues:
            self._record_event(
                EventType.MEASUREMENT_OUT_OF_RANGE,
                EventSource.MEASUREMENT,
                EventSeverity.WARNING,
                "; ".join(assessment.issues),
                ticks=ticks,
            )

        diagnostic = self.diagnostics.evaluate(
            DiagnosticEvidence(
                commanded_state=decision.commanded_state,
                switching_feedback=sources.switching_feedback,
                voltage=sources.voltage,
                current=sources.current,
                power=sources.power,
                light_level=sources.light_level,
                sensor_status=sources.sensor_status,
                communication_status=self._comm_status,
                controller_status=sources.controller_status,
                voltage_valid=_voltage_valid(sources.voltage, self.config),
                power_consistent=assessment.physically_consistent,
            )
        )
        self._last_diagnostic = diagnostic

        newly_confirmed = self.faults.observe(
            self.site_id, self.group_id, self.lamp_id, diagnostic, ticks
        )
        if newly_confirmed is not None and newly_confirmed.is_confirmed:
            if newly_confirmed.state.value == "CONFIRMED":
                self.notifications.on_fault_confirmed(newly_confirmed, ticks)
                self.notifications.notify(newly_confirmed, ticks)
        for fault in self.faults.active_faults:
            if fault.state.value == "CONFIRMED":
                self.notifications.tick(fault, ticks)

        self._store_measurement(measurement, ticks)
        return decision

    def _accumulate_energy(self, sources: LampNodeSources, ticks: int) -> None:
        if sources.power is None:
            return
        self._energy += (
            sources.power * self.config.measurement_interval_ticks / self.ticks_per_hour
        )

    def _build_measurement(
        self, sources: LampNodeSources, decision: ControlDecision, ticks: int
    ) -> Measurement:
        self._measurement_sequence += 1
        return Measurement(
            timestamp=self.time.now(),
            site_id=self.site_id,
            group_id=self.group_id,
            lamp_id=self.lamp_id,
            operating_mode=decision.effective_mode,
            commanded_state=decision.commanded_state,
            switching_feedback=sources.switching_feedback,
            actual_state=_derive_actual_state(
                sources.switching_feedback, sources.current, self.config
            ),
            voltage=sources.voltage,
            current=sources.current,
            power=sources.power,
            energy=self._energy,
            light_level=sources.light_level,
            sensor_status=sources.sensor_status,
            communication_status=self._comm_status,
            controller_status=sources.controller_status,
            sequence_number=self._measurement_sequence,
        )

    def _store_measurement(self, measurement: Measurement, ticks: int) -> None:
        should_report = (
            self._last_report_ticks is None
            or (ticks - self._last_report_ticks) >= self.config.reporting_interval_ticks
        )
        if not should_report:
            return
        self._last_report_ticks = ticks
        try:
            record = self.storage.create(
                record_type=RecordType.MEASUREMENT,
                payload=measurement.to_dict(),
                timestamp=measurement.timestamp,
                device_id=self.identity.device_id,
            )
            self._record_event(
                EventType.RECORD_STORED,
                EventSource.STORAGE,
                EventSeverity.INFO,
                "measurement record %d stored" % record.sequence_number,
                ticks=ticks,
                data={"sequence_number": record.sequence_number},
            )
        except Exception as exc:  # storage full and similar explicit conditions
            self._record_event(
                EventType.STORAGE_FULL,
                EventSource.STORAGE,
                EventSeverity.ERROR,
                "measurement record not stored: %s" % exc,
                ticks=ticks,
            )

    # ------------------------------------------------------------------
    # communication
    # ------------------------------------------------------------------
    def receive(self, frame: Frame) -> None:
        """BusEndpoint entry point."""
        self._incoming.append(frame)

    def process_incoming(self) -> List[Frame]:
        """Handle every frame received since the last call.

        Returns the frames the node wants to send in response. The caller (a
        scenario or the group controller) puts them on the bus.
        """
        responses: List[Frame] = []
        while self._incoming:
            frame = self._incoming.pop(0)
            response = self._handle_frame(frame)
            if response is not None:
                responses.append(response)
        return responses

    def _handle_frame(self, frame: Frame) -> Optional[Frame]:
        try:
            handler = self._HANDLERS[frame.message_type]
        except KeyError:
            self._record_event(
                EventType.FRAME_REJECTED,
                EventSource.COMMUNICATION,
                EventSeverity.WARNING,
                "unsupported message type %s" % frame.message_type.value,
                ticks=self.clock.ticks,
            )
            return None
        return handler(self, frame)

    # -- handlers ---------------------------------------------------------
    def _handle_status_request(self, frame: Frame) -> Frame:
        payload = {
            "operating_mode": self.control.effective_mode,
            "override": self.control.active_override,
            "commanded_state": _commanded_state(self.control),
            "switching_feedback": (
                self._last_measurement.switching_feedback
                if self._last_measurement
                else LampState.UNKNOWN
            ),
            "actual_state": (
                self._last_measurement.actual_state
                if self._last_measurement
                else LampState.UNKNOWN
            ),
            "sensor_status": (
                self._last_measurement.sensor_status
                if self._last_measurement
                else SensorStatus.VALID
            ),
            "communication_status": self._comm_status,
            "controller_status": (
                self._last_measurement.controller_status
                if self._last_measurement
                else ControllerStatus.NORMAL
            ),
        }
        return self._respond(frame, MessageType.STATUS_RESPONSE, payload)

    def _handle_measurement_request(self, frame: Frame) -> Optional[Frame]:
        if self._last_measurement is None:
            return None
        m = self._last_measurement
        payload = {
            "timestamp_ticks": m.timestamp.ticks,
            "voltage_mv": int(round((m.voltage or 0.0) * 1000)),
            "current_ma": int(round((m.current or 0.0) * 1000)),
            "power_mw": int(round((m.power or 0.0) * 1000)),
            "energy_mwh": int(round((m.energy or 0.0) * 1000)),
            "light_level": int(round(m.light_level or 0.0)),
            "operating_mode": m.operating_mode,
            "commanded_state": m.commanded_state,
            "switching_feedback": m.switching_feedback,
            "actual_state": m.actual_state,
            "sensor_status": m.sensor_status,
            "communication_status": m.communication_status,
            "controller_status": m.controller_status,
        }
        return self._respond(frame, MessageType.MEASUREMENT_RESPONSE, payload)

    def _handle_control_command(self, frame: Frame) -> Frame:
        from ..comm.protocol import decode_payload

        fields = decode_payload(MessageType.CONTROL_COMMAND, frame.payload)
        command_id = str(fields["command_id"])
        subtype = fields["subtype"]
        actor = Actor(actor_id="group-controller", role=_role_for_subtype(subtype))

        if subtype is ControlSubtype.RESET_ENERGY:
            command = Command(
                command_id=command_id,
                command_type=CommandType.SET_MODE,
                subtype=ControlSubtype.RESET_ENERGY,
                target=self.identity,
                actor=actor,
                created_ticks=self.clock.ticks,
                parameters={"parameter": fields.get("parameter", 0)},
            )
        elif subtype is ControlSubtype.LAMP_ON:
            command = Command(
                command_id=command_id,
                command_type=CommandType.FORCE_ON,
                target=self.identity,
                actor=actor,
                created_ticks=self.clock.ticks,
            )
        elif subtype is ControlSubtype.LAMP_OFF:
            command = Command(
                command_id=command_id,
                command_type=CommandType.FORCE_OFF,
                target=self.identity,
                actor=actor,
                created_ticks=self.clock.ticks,
            )
        elif subtype is ControlSubtype.RETURN_TO_AUTO:
            command = Command(
                command_id=command_id,
                command_type=CommandType.RETURN_TO_AUTO,
                target=self.identity,
                actor=actor,
                created_ticks=self.clock.ticks,
            )
        else:  # SET_MODE
            command = Command(
                command_id=command_id,
                command_type=CommandType.SET_MODE,
                subtype=ControlSubtype.SET_MODE,
                target=self.identity,
                actor=actor,
                created_ticks=self.clock.ticks,
                parameters={"mode": fields.get("parameter", 0)},
            )

        record = self.commands.submit(command, self.clock.ticks)
        payload = {
            "command_id": command_id,
            "execution_status": record.state,
            "actual_state": _commanded_state(self.control),
        }
        return self._respond(frame, MessageType.CONTROL_ACK, payload)

    def _handle_fault_report_request(self, frame: Frame) -> Optional[Frame]:
        active = self.faults.active_faults
        if not active:
            return None
        fault = active[0]
        payload = {
            "fault_id": fault.fault_id,
            "fault_type": fault.fault_type,
            "diagnostic_classification": fault.diagnostic_classification,
            "fault_state": fault.state,
            "notification_state": fault.notification_state,
            "severity": fault.severity,
            "confirmation_count": fault.confirmation_count,
        }
        return self._respond(frame, MessageType.FAULT_REPORT, payload)

    def _handle_event_report_request(self, frame: Frame) -> Optional[Frame]:
        pending = [e for e in self.events if not self._reported_events.get(e.event_id)]
        if not pending:
            return None
        event = pending[0]
        self._reported_events[event.event_id] = True
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "severity": list(EventSeverity).index(event.severity),
            "reason": event.reason,
        }
        return self._respond(frame, MessageType.EVENT_REPORT, payload)

    def _handle_config_read(self, frame: Frame) -> Frame:
        payload = {"config_version": self.config_version, "parameters": self._config_parameters()}
        return self._respond(frame, MessageType.CONFIG_ACK, payload)

    def _handle_config_write(self, frame: Frame) -> Frame:
        from ..comm.protocol import decode_payload

        fields = decode_payload(MessageType.CONFIG_WRITE, frame.payload)
        parameters = fields.get("parameters", {})
        try:
            new_config = self._apply_config_parameters(parameters)
            new_config.validated()
        except ConfigurationError as exc:
            self._record_event(
                EventType.CONFIG_REJECTED,
                EventSource.CONFIGURATION,
                EventSeverity.WARNING,
                "configuration rejected: %s" % exc,
                ticks=self.clock.ticks,
            )
            return self._respond(
                frame,
                MessageType.CONFIG_ACK,
                {
                    "config_version": self.config_version,
                    "accepted": False,
                    "reason": str(exc),
                },
            )
        self.config = new_config
        self.control.config = new_config
        self.validator = MeasurementValidator(new_config)
        self.diagnostics = DiagnosticEngine(new_config)
        self.faults._config = new_config
        self.faults._policy = type(self.faults._policy).from_config(new_config)
        self.notifications._policy = type(self.notifications._policy).from_config(new_config)
        self.config_version += 1
        self._record_event(
            EventType.CONFIG_CHANGED,
            EventSource.CONFIGURATION,
            EventSeverity.INFO,
            "configuration updated: %s" % ", ".join(sorted(parameters)),
            ticks=self.clock.ticks,
        )
        return self._respond(
            frame,
            MessageType.CONFIG_ACK,
            {"config_version": self.config_version, "accepted": True, "reason": "applied"},
        )

    def _handle_time_sync(self, frame: Frame) -> Frame:
        from ..comm.protocol import decode_payload

        fields = decode_payload(MessageType.TIME_SYNC, frame.payload)
        master_ticks = int(fields["master_ticks"])
        self.time.synchronize(master_ticks)
        self._comm_status = CommunicationStatus.COMM_HEALTHY
        self._record_event(
            EventType.TIME_SYNCHRONIZED,
            EventSource.TIME,
            EventSeverity.INFO,
            "time synchronized to master tick %d" % master_ticks,
            ticks=self.clock.ticks,
        )
        return self._respond(
            frame,
            MessageType.TIME_ACK,
            {"master_ticks": master_ticks, "local_ticks": self.clock.ticks},
        )

    def _handle_identify(self, frame: Frame) -> Frame:
        payload = {
            "product_id": str(self.identity.product_id),
            "site_id": str(self.identity.site_id),
            "group_id": str(self.identity.group_id),
            "lamp_id": str(self.lamp_id),
            "mcu_unique_id": (
                str(self.identity.mcu_unique_id) if self.identity.mcu_unique_id else ""
            ),
        }
        return self._respond(frame, MessageType.IDENTIFY_ACK, payload)

    def _handle_heartbeat(self, frame: Frame) -> Frame:
        return self._respond(
            frame, MessageType.HEARTBEAT_ACK, {"local_ticks": self.clock.ticks}
        )

    _HANDLERS = {
        MessageType.STATUS_REQUEST: _handle_status_request,
        MessageType.MEASUREMENT_REQUEST: _handle_measurement_request,
        MessageType.CONTROL_COMMAND: _handle_control_command,
        MessageType.FAULT_REPORT: _handle_fault_report_request,
        MessageType.EVENT_REPORT: _handle_event_report_request,
        MessageType.CONFIG_READ: _handle_config_read,
        MessageType.CONFIG_WRITE: _handle_config_write,
        MessageType.TIME_SYNC: _handle_time_sync,
        MessageType.IDENTIFY: _handle_identify,
        MessageType.HEARTBEAT: _handle_heartbeat,
    }

    # ------------------------------------------------------------------
    # command execution / verification
    # ------------------------------------------------------------------
    def _execute_command(self, command: Command) -> Tuple[bool, str]:
        if command.command_type is CommandType.FORCE_ON:
            self.control.apply_override(OverrideState.FORCE_ON)
            self._record_event(
                EventType.OVERRIDE_APPLIED,
                EventSource.CONTROL,
                EventSeverity.INFO,
                "operator override FORCE_ON applied",
                actor=command.actor.actor_id,
                ticks=self.clock.ticks,
            )
            return True, "override FORCE_ON applied"
        if command.command_type is CommandType.FORCE_OFF:
            self.control.apply_override(OverrideState.FORCE_OFF)
            self._record_event(
                EventType.OVERRIDE_APPLIED,
                EventSource.CONTROL,
                EventSeverity.INFO,
                "operator override FORCE_OFF applied",
                actor=command.actor.actor_id,
                ticks=self.clock.ticks,
            )
            return True, "override FORCE_OFF applied"
        if command.command_type is CommandType.RETURN_TO_AUTO:
            had_override = self.control.active_override is not OverrideState.NONE
            self.control.clear_override()
            self._record_event(
                EventType.OVERRIDE_RELEASED,
                EventSource.CONTROL,
                EventSeverity.INFO,
                "override released; effective mode is now %s"
                % self.control.effective_mode.value,
                actor=command.actor.actor_id,
                ticks=self.clock.ticks,
            )
            return True, "returned to automatic mode (was %s)" % (
                "overridden" if had_override else "already automatic"
            )
        if command.command_type is CommandType.SET_MODE:
            if command.subtype is ControlSubtype.RESET_ENERGY:
                self._authorizer.require(command.actor, Action.RESET_ENERGY)
                self._energy = 0.0
                self._record_event(
                    EventType.ENERGY_RESET,
                    EventSource.CONTROL,
                    EventSeverity.WARNING,
                    "accumulated energy reset by %s" % command.actor.actor_id,
                    actor=command.actor.actor_id,
                    ticks=self.clock.ticks,
                )
                return True, "energy reset"
            mode_code = command.parameters.get("mode", 0)
            try:
                mode = list(ConfiguredMode)[int(mode_code)]
            except (IndexError, ValueError, TypeError):
                return False, "unknown configured mode code %r" % (mode_code,)
            self.control.set_configured_mode(mode)
            self._record_event(
                EventType.MODE_CHANGED,
                EventSource.CONTROL,
                EventSeverity.INFO,
                "configured mode changed to %s" % mode.value,
                actor=command.actor.actor_id,
                ticks=self.clock.ticks,
            )
            return True, "configured mode set to %s" % mode.value
        return False, "unsupported command type %s" % command.command_type.value

    def _verify_command(self, command: Command) -> Tuple[bool, str]:
        """Actual-state verification (``PR-CONTROL-002``)."""
        if command.command_type in (CommandType.FORCE_ON, CommandType.FORCE_OFF):
            expected = (
                LampState.ON
                if command.command_type is CommandType.FORCE_ON
                else LampState.OFF
            )
            actual = _commanded_state(self.control)
            if actual is expected:
                return True, "actual state %s matches commanded state" % actual.value
            return False, "actual state %s does not match %s" % (actual.value, expected.value)
        if command.command_type is CommandType.RETURN_TO_AUTO:
            if self.control.active_override is OverrideState.NONE:
                return True, "no active override"
            return False, "override still active"
        if command.command_type is CommandType.SET_MODE:
            if command.subtype is ControlSubtype.RESET_ENERGY:
                if self._energy == 0.0:
                    return True, "energy accumulator is zero"
                return False, "energy accumulator is %s" % self._energy
            return True, "configured mode applied"
        return True, "no actual-state check required"

    # ------------------------------------------------------------------
    # operator-facing API (used by scenarios and tests)
    # ------------------------------------------------------------------
    def force_on(self, actor: Actor, ticks: Optional[int] = None) -> CommandRecord:
        return self._submit(
            CommandType.FORCE_ON, actor, ticks, command_id=self._next_command_id("force-on")
        )

    def force_off(self, actor: Actor, ticks: Optional[int] = None) -> CommandRecord:
        return self._submit(
            CommandType.FORCE_OFF, actor, ticks, command_id=self._next_command_id("force-off")
        )

    def return_to_auto(self, actor: Actor, ticks: Optional[int] = None) -> CommandRecord:
        return self._submit(
            CommandType.RETURN_TO_AUTO,
            actor,
            ticks,
            command_id=self._next_command_id("return-to-auto"),
        )

    def set_configured_mode(
        self, mode: ConfiguredMode, actor: Actor, ticks: Optional[int] = None
    ) -> CommandRecord:
        return self._submit(
            CommandType.SET_MODE,
            actor,
            ticks,
            command_id=self._next_command_id("set-mode"),
            subtype=ControlSubtype.SET_MODE,
            parameters={"mode": list(ConfiguredMode).index(mode)},
        )

    def reset_energy(self, actor: Actor, ticks: Optional[int] = None) -> CommandRecord:
        """Reset the energy accumulator.

        ``RESET_ENERGY`` is a ``CONTROL_COMMAND`` *subtype* (``PR-COMM-010``,
        ``D-038``): it adds no new RS-485 message type.
        """
        return self._submit(
            CommandType.SET_MODE,
            actor,
            ticks,
            command_id=self._next_command_id("reset-energy"),
            subtype=ControlSubtype.RESET_ENERGY,
            parameters={"subtype": ControlSubtype.RESET_ENERGY.value},
        )

    def acknowledge_fault(
        self, fault_id: str, actor: Actor, ticks: Optional[int] = None
    ) -> Fault:
        ticks = self.clock.ticks if ticks is None else ticks
        fault = self.faults.acknowledge(fault_id, actor.actor_id, ticks)
        self.notifications.acknowledge(fault, actor.actor_id)
        return fault

    def start_repair(
        self, fault_id: str, actor: Actor, ticks: Optional[int] = None
    ) -> Fault:
        ticks = self.clock.ticks if ticks is None else ticks
        return self.faults.start_repair(fault_id, actor.actor_id, ticks)

    def report_repaired(
        self, fault_id: str, actor: Actor, ticks: Optional[int] = None
    ) -> Fault:
        ticks = self.clock.ticks if ticks is None else ticks
        return self.faults.report_repaired(fault_id, actor.actor_id, ticks)

    def verify_repair(
        self,
        fault_id: str,
        actor: Actor,
        verified: bool,
        ticks: Optional[int] = None,
        evidence: Optional[Dict[str, object]] = None,
    ) -> Fault:
        ticks = self.clock.ticks if ticks is None else ticks
        return self.faults.verify(
            fault_id, actor.actor_id, ticks, verified=verified, evidence=evidence
        )

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------
    def _submit(
        self,
        command_type: CommandType,
        actor: Actor,
        ticks: Optional[int],
        command_id: str,
        subtype: Optional[ControlSubtype] = None,
        parameters: Optional[Dict[str, object]] = None,
    ) -> CommandRecord:
        ticks = self.clock.ticks if ticks is None else ticks
        # Authorization is enforced by CommandService inside the lifecycle, so
        # an unauthorized actor yields a REJECTED record (never a RECEIVED
        # one) and the rejection is audited.
        command = Command(
            command_id=command_id,
            command_type=command_type,
            subtype=subtype,
            target=self.identity,
            actor=actor,
            created_ticks=ticks,
            parameters=dict(parameters or {}),
        )
        return self.commands.submit(command, ticks)

    def _next_command_id(self, prefix: str) -> str:
        self._command_sequence = getattr(self, "_command_sequence", 0) + 1
        return "%s-%s-%04d" % (str(self.lamp_id), prefix, self._command_sequence)

    def _respond(self, request: Frame, message_type: MessageType, payload: dict) -> Frame:
        from ..comm.protocol import encode_payload

        self._sequence = getattr(self, "_sequence", 0) + 1
        return Frame(
            source=int(self.bus_address),
            destination=request.source,
            message_type=message_type,
            payload=encode_payload(message_type, payload),
            sequence=self._sequence,
        )

    def _emit_control_events(
        self, decision: ControlDecision, previous_state: bool, ticks: int
    ) -> None:
        now_on = decision.commanded_state is LampState.ON
        if now_on and not previous_state:
            self._record_event(
                EventType.LAMP_ON,
                EventSource.CONTROL,
                EventSeverity.INFO,
                "lamp switched ON (%s)" % decision.reason,
                ticks=ticks,
            )
        elif not now_on and previous_state:
            self._record_event(
                EventType.LAMP_OFF,
                EventSource.CONTROL,
                EventSeverity.INFO,
                "lamp switched OFF (%s)" % decision.reason,
                ticks=ticks,
            )

    def _record_event(
        self,
        event_type: EventType,
        source: EventSource,
        severity: EventSeverity,
        reason: str,
        ticks: Optional[int] = None,
        actor: Optional[str] = None,
        related_fault_id: Optional[str] = None,
        data: Optional[Dict[str, object]] = None,
    ) -> Event:
        ticks = self.clock.ticks if ticks is None else ticks
        return self.events.record(
            timestamp=Timestamp(ticks=ticks, sync_state=self.time.sync_state),
            device_id=self.identity.device_id,
            event_type=event_type,
            source=source,
            severity=severity,
            reason=reason,
            site_id=self.site_id,
            group_id=self.group_id,
            lamp_id=self.lamp_id,
            related_fault_id=related_fault_id,
            actor=actor,
            event_data=data or {},
        )

    def _on_fault_event(self, kind: str, fault: Fault, reason: str) -> None:
        mapping = {
            "FAULT_SUSPECTED": (EventType.FAULT_SUSPECTED, EventSeverity.WARNING),
            "FAULT_CONFIRMED": (EventType.FAULT_CONFIRMED, EventSeverity.ERROR),
            "FAULT_ACKNOWLEDGED": (EventType.FAULT_ACKNOWLEDGED, EventSeverity.INFO),
            "FAULT_REMINDER_DUE": (EventType.FAULT_REMINDER_DUE, EventSeverity.WARNING),
            "FAULT_ESCALATED": (EventType.FAULT_ESCALATED, EventSeverity.ERROR),
            "FAULT_NOTIFIED": (EventType.FAULT_CONFIRMED, EventSeverity.INFO),
            "FAULT_NOTIFICATION_FAILED": (
                EventType.FAULT_NOTIFICATION_FAILED,
                EventSeverity.ERROR,
            ),
            "FAULT_REPAIR_STARTED": (EventType.FAULT_REPAIR_STARTED, EventSeverity.INFO),
            "FAULT_VERIFICATION_FAILED": (
                EventType.FAULT_VERIFICATION_FAILED,
                EventSeverity.ERROR,
            ),
            "FAULT_CLOSED": (EventType.FAULT_CLOSED, EventSeverity.INFO),
        }
        event_type, severity = mapping.get(kind, (EventType.FAULT_SUSPECTED, EventSeverity.INFO))
        self._record_event(
            event_type,
            EventSource.FAULT,
            severity,
            reason,
            related_fault_id=fault.fault_id,
            data={
                "fault_type": fault.fault_type.value,
                "diagnostic_classification": fault.diagnostic_classification.value,
                "fault_state": fault.state.value,
                "notification_state": fault.notification_state.value,
            },
        )

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
        event_type, severity = mapping.get(kind, (EventType.COMMAND_RECEIVED, EventSeverity.INFO))
        self._record_event(
            event_type,
            EventSource.SECURITY,
            severity,
            "%s by %s (%s): %s"
            % (
                record.command_id,
                record.command.actor.actor_id,
                record.command.actor.role.value,
                reason,
            ),
            actor=record.command.actor.actor_id,
            data={"command_type": record.command.command_type.value},
        )

    # ------------------------------------------------------------------
    # configuration helpers
    # ------------------------------------------------------------------
    @property
    def config_version(self) -> int:
        return getattr(self, "_config_version", 1)

    @config_version.setter
    def config_version(self, value: int) -> None:
        self._config_version = value

    def _config_parameters(self) -> Dict[str, int]:
        cfg = self.config
        return {
            "configured_mode": list(ConfiguredMode).index(cfg.configured_mode),
            "light_on_threshold": int(cfg.light_on_threshold),
            "light_off_threshold": int(cfg.light_off_threshold),
            "measurement_interval_ticks": cfg.measurement_interval_ticks,
            "reporting_interval_ticks": cfg.reporting_interval_ticks,
            "fault_confirmation_count": cfg.fault_confirmation_count,
            "fault_confirmation_window_ticks": cfg.fault_confirmation_window_ticks,
            "comm_retry_count": cfg.comm_retry_count,
            "comm_timeout_ticks": cfg.comm_timeout_ticks,
            "ack_reminder_interval_ticks": cfg.ack_reminder_interval_ticks,
            "escalation_timeout_ticks": cfg.escalation_timeout_ticks,
        }

    def _apply_config_parameters(self, parameters: Dict[str, int]) -> LampConfiguration:
        updates: Dict[str, object] = {}
        for key, value in parameters.items():
            if key == "configured_mode":
                updates["configured_mode"] = list(ConfiguredMode)[int(value)]
            elif key in (
                "light_on_threshold",
                "light_off_threshold",
            ):
                updates[key] = float(value)
            else:
                updates[key] = int(value)
        return replace(self.config, **updates)

    # ------------------------------------------------------------------
    # reporting helpers
    # ------------------------------------------------------------------
    def snapshot(self) -> Dict[str, object]:
        return {
            "lamp_id": str(self.lamp_id),
            "bus_address": int(self.bus_address),
            "configured_mode": self.control.configured_mode.value,
            "active_override": self.control.active_override.value,
            "effective_mode": self.control.effective_mode.value,
            "lamp_is_on": self.control.lamp_is_on,
            "comm_state": self.comm.state.value,
            "time_sync_state": self.time.sync_state.value,
            "active_faults": [f.fault_id for f in self.faults.active_faults],
            "stored_records": len(self.storage),
            "pending_upload": len(self.storage.pending_upload),
            "events": len(self.events),
        }

    def set_communication_status(self, status: CommunicationStatus) -> None:
        self._comm_status = status


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _commanded_state(control: ControlModel) -> LampState:
    return LampState.ON if control.lamp_is_on else LampState.OFF


def _voltage_valid(voltage: Optional[float], config: LampConfiguration) -> bool:
    if voltage is None:
        return False
    return config.voltage_min <= voltage <= config.voltage_max


def _derive_actual_state(
    switching_feedback: LampState, current: Optional[float], config: LampConfiguration
) -> LampState:
    """Derive the observed lamp state from switching feedback and current."""
    if switching_feedback is LampState.UNKNOWN:
        return LampState.UNKNOWN
    if switching_feedback is LampState.ON:
        if current is not None and current >= config.unexpected_current_min:
            return LampState.ON
        return LampState.UNKNOWN
    # switching feedback OFF
    if current is None or current < config.unexpected_current_min:
        return LampState.OFF
    return LampState.UNKNOWN


def _role_for_subtype(subtype: ControlSubtype):
    from ..enums import Role

    if subtype is ControlSubtype.RESET_ENERGY:
        return Role.ENGINEER
    return Role.OPERATOR
