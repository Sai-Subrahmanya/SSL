"""Payload codecs for the initial message type set.

Payloads are encoded as compact big-endian binary with one-byte length
prefixes for variable-length strings. The codecs are pure functions: they
depend on nothing outside the standard library and on no hardware.

Command actions such as ``RESET_ENERGY`` are carried as *subtypes* inside
``CONTROL_COMMAND`` and never introduce a new message type
(``PR-COMM-010``, ``D-038``).
"""

from __future__ import annotations

import struct
from typing import Callable, Dict, Mapping, Tuple

from ..enums import (
    CommandState,
    CommunicationStatus,
    ControlSubtype,
    ControllerStatus,
    DiagnosticClassification,
    EventType,
    FaultSeverity,
    FaultState,
    FaultType,
    LampState,
    MessageType,
    NotificationState,
    OperatingMode,
    OverrideState,
    SensorStatus,
)
from ..errors import ProtocolError

Encoder = Callable[[Mapping[str, object]], bytes]
Decoder = Callable[[bytes], Dict[str, object]]


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _pack_str(value: str) -> bytes:
    raw = value.encode("utf-8")
    if len(raw) > 255:
        raise ProtocolError("string too long for payload")
    return bytes([len(raw)]) + raw


def _unpack_str(data: bytes, offset: int) -> Tuple[str, int]:
    if offset >= len(data):
        raise ProtocolError("truncated string in payload")
    length = data[offset]
    offset += 1
    if offset + length > len(data):
        raise ProtocolError("truncated string body in payload")
    return data[offset : offset + length].decode("utf-8"), offset + length


def _enum_code(enum_cls, value, field: str) -> int:
    try:
        return list(enum_cls).index(value)
    except ValueError:
        raise ProtocolError("unknown %s value %r" % (field, value))


def _enum_from_code(enum_cls, code: int, field: str):
    try:
        return list(enum_cls)[code]
    except IndexError:
        raise ProtocolError("unknown %s code %d" % (field, code))


def _require(fields: Mapping[str, object], *names: str) -> None:
    missing = [n for n in names if n not in fields]
    if missing:
        raise ProtocolError("missing payload fields: %s" % ", ".join(missing))


# --------------------------------------------------------------------------
# codecs
# --------------------------------------------------------------------------
def _encode_empty(fields: Mapping[str, object]) -> bytes:
    return b""


def _decode_empty(data: bytes) -> Dict[str, object]:
    if data:
        raise ProtocolError("expected empty payload")
    return {}


def _encode_status_response(fields: Mapping[str, object]) -> bytes:
    _require(
        fields,
        "operating_mode",
        "override",
        "commanded_state",
        "switching_feedback",
        "actual_state",
        "sensor_status",
        "communication_status",
        "controller_status",
    )
    return struct.pack(
        ">8B",
        _enum_code(OperatingMode, fields["operating_mode"], "operating_mode"),
        _enum_code(OverrideState, fields["override"], "override"),
        _enum_code(LampState, fields["commanded_state"], "commanded_state"),
        _enum_code(LampState, fields["switching_feedback"], "switching_feedback"),
        _enum_code(LampState, fields["actual_state"], "actual_state"),
        _enum_code(SensorStatus, fields["sensor_status"], "sensor_status"),
        _enum_code(CommunicationStatus, fields["communication_status"], "communication_status"),
        _enum_code(ControllerStatus, fields["controller_status"], "controller_status"),
    )


def _decode_status_response(data: bytes) -> Dict[str, object]:
    if len(data) != 8:
        raise ProtocolError("STATUS_RESPONSE payload must be 8 bytes")
    codes = struct.unpack(">8B", data)
    return {
        "operating_mode": list(OperatingMode)[codes[0]],
        "override": list(OverrideState)[codes[1]],
        "commanded_state": list(LampState)[codes[2]],
        "switching_feedback": list(LampState)[codes[3]],
        "actual_state": list(LampState)[codes[4]],
        "sensor_status": list(SensorStatus)[codes[5]],
        "communication_status": list(CommunicationStatus)[codes[6]],
        "controller_status": list(ControllerStatus)[codes[7]],
    }


_MEASUREMENT_FORMAT = ">qiiiiq7B"


def _encode_measurement_response(fields: Mapping[str, object]) -> bytes:
    _require(
        fields,
        "timestamp_ticks",
        "voltage_mv",
        "current_ma",
        "power_mw",
        "energy_mwh",
        "light_level",
        "operating_mode",
        "commanded_state",
        "switching_feedback",
        "actual_state",
        "sensor_status",
        "communication_status",
        "controller_status",
    )
    return struct.pack(
        _MEASUREMENT_FORMAT,
        int(fields["timestamp_ticks"]),
        int(fields["voltage_mv"]),
        int(fields["current_ma"]),
        int(fields["power_mw"]),
        int(fields["energy_mwh"]),
        int(fields["light_level"]),
        _enum_code(OperatingMode, fields["operating_mode"], "operating_mode"),
        _enum_code(LampState, fields["commanded_state"], "commanded_state"),
        _enum_code(LampState, fields["switching_feedback"], "switching_feedback"),
        _enum_code(LampState, fields["actual_state"], "actual_state"),
        _enum_code(SensorStatus, fields["sensor_status"], "sensor_status"),
        _enum_code(CommunicationStatus, fields["communication_status"], "communication_status"),
        _enum_code(ControllerStatus, fields["controller_status"], "controller_status"),
    )


def _decode_measurement_response(data: bytes) -> Dict[str, object]:
    if len(data) != struct.calcsize(_MEASUREMENT_FORMAT):
        raise ProtocolError("MEASUREMENT_RESPONSE payload has wrong size")
    values = struct.unpack(_MEASUREMENT_FORMAT, data)
    return {
        "timestamp_ticks": values[0],
        "voltage_mv": values[1],
        "current_ma": values[2],
        "power_mw": values[3],
        "energy_mwh": values[4],
        "light_level": values[5],
        "operating_mode": list(OperatingMode)[values[6]],
        "commanded_state": list(LampState)[values[7]],
        "switching_feedback": list(LampState)[values[8]],
        "actual_state": list(LampState)[values[9]],
        "sensor_status": list(SensorStatus)[values[10]],
        "communication_status": list(CommunicationStatus)[values[11]],
        "controller_status": list(ControllerStatus)[values[12]],
    }


def _encode_control_command(fields: Mapping[str, object]) -> bytes:
    _require(fields, "subtype", "target_state", "command_id", "parameter")
    return b"".join(
        [
            struct.pack(
                ">BBi",
                _enum_code(ControlSubtype, fields["subtype"], "subtype"),
                _enum_code(LampState, fields["target_state"], "target_state"),
                int(fields["parameter"]),
            ),
            _pack_str(str(fields["command_id"])),
        ]
    )


def _decode_control_command(data: bytes) -> Dict[str, object]:
    if len(data) < struct.calcsize(">BBi") + 1:
        raise ProtocolError("CONTROL_COMMAND payload too short")
    subtype_code, target_code, parameter = struct.unpack_from(">BBi", data, 0)
    command_id, _ = _unpack_str(data, struct.calcsize(">BBi"))
    return {
        "subtype": list(ControlSubtype)[subtype_code],
        "target_state": list(LampState)[target_code],
        "parameter": parameter,
        "command_id": command_id,
    }


def _encode_control_ack(fields: Mapping[str, object]) -> bytes:
    _require(fields, "command_id", "execution_status", "actual_state")
    return b"".join(
        [
            struct.pack(
                ">BB",
                _enum_code(CommandState, fields["execution_status"], "execution_status"),
                _enum_code(LampState, fields["actual_state"], "actual_state"),
            ),
            _pack_str(str(fields["command_id"])),
        ]
    )


def _decode_control_ack(data: bytes) -> Dict[str, object]:
    if len(data) < 3:
        raise ProtocolError("CONTROL_ACK payload too short")
    status_code, actual_code = struct.unpack_from(">BB", data, 0)
    command_id, _ = _unpack_str(data, 2)
    return {
        "execution_status": list(CommandState)[status_code],
        "actual_state": list(LampState)[actual_code],
        "command_id": command_id,
    }


def _encode_fault_report(fields: Mapping[str, object]) -> bytes:
    _require(
        fields,
        "fault_id",
        "fault_type",
        "diagnostic_classification",
        "fault_state",
        "notification_state",
        "confirmation_count",
        "severity",
    )
    return b"".join(
        [
            struct.pack(
                ">5BH",
                _enum_code(FaultType, fields["fault_type"], "fault_type"),
                _enum_code(
                    DiagnosticClassification,
                    fields["diagnostic_classification"],
                    "diagnostic_classification",
                ),
                _enum_code(FaultState, fields["fault_state"], "fault_state"),
                _enum_code(
                    NotificationState, fields["notification_state"], "notification_state"
                ),
                _enum_code(FaultSeverity, fields["severity"], "severity"),
                int(fields["confirmation_count"]),
            ),
            _pack_str(str(fields["fault_id"])),
        ]
    )


def _decode_fault_report(data: bytes) -> Dict[str, object]:
    if len(data) < struct.calcsize(">5BH") + 1:
        raise ProtocolError("FAULT_REPORT payload too short")
    codes = struct.unpack_from(">5BH", data, 0)
    fault_id, _ = _unpack_str(data, struct.calcsize(">5BH"))
    return {
        "fault_type": list(FaultType)[codes[0]],
        "diagnostic_classification": list(DiagnosticClassification)[codes[1]],
        "fault_state": list(FaultState)[codes[2]],
        "notification_state": list(NotificationState)[codes[3]],
        "severity": list(FaultSeverity)[codes[4]],
        "confirmation_count": codes[5],
        "fault_id": fault_id,
    }


def _encode_event_report(fields: Mapping[str, object]) -> bytes:
    _require(fields, "event_id", "event_type", "reason")
    return b"".join(
        [
            struct.pack(">IQ", int(fields["event_id"]), int(fields.get("severity", 0))),
            bytes([_enum_code(EventType, fields["event_type"], "event_type")]),
            _pack_str(str(fields["reason"])),
        ]
    )


def _decode_event_report(data: bytes) -> Dict[str, object]:
    if len(data) < 13:
        raise ProtocolError("EVENT_REPORT payload too short")
    event_id, severity = struct.unpack_from(">IQ", data, 0)
    event_type = list(EventType)[data[12]]
    reason, _ = _unpack_str(data, 13)
    return {
        "event_id": event_id,
        "event_type": event_type,
        "severity": severity,
        "reason": reason,
    }


def _encode_config_write(fields: Mapping[str, object]) -> bytes:
    _require(fields, "config_version", "parameters")
    params = fields["parameters"]
    if not isinstance(params, Mapping):
        raise ProtocolError("parameters must be a mapping")
    body = bytearray(struct.pack(">HB", int(fields["config_version"]), len(params)))
    for key in sorted(params):
        body += _pack_str(str(key))
        body += struct.pack(">i", int(params[key]))
    return bytes(body)


def _decode_config_write(data: bytes) -> Dict[str, object]:
    if len(data) < 3:
        raise ProtocolError("CONFIG_WRITE payload too short")
    config_version, count = struct.unpack_from(">HB", data, 0)
    offset = 3
    parameters: Dict[str, int] = {}
    for _ in range(count):
        key, offset = _unpack_str(data, offset)
        if offset + 4 > len(data):
            raise ProtocolError("truncated CONFIG_WRITE parameter")
        parameters[key] = struct.unpack_from(">i", data, offset)[0]
        offset += 4
    return {"config_version": config_version, "parameters": parameters}


def _encode_config_ack(fields: Mapping[str, object]) -> bytes:
    _require(fields, "config_version", "accepted", "reason")
    return b"".join(
        [
            struct.pack(">HB", int(fields["config_version"]), 1 if fields["accepted"] else 0),
            _pack_str(str(fields["reason"])),
        ]
    )


def _decode_config_ack(data: bytes) -> Dict[str, object]:
    if len(data) < 4:
        raise ProtocolError("CONFIG_ACK payload too short")
    config_version, accepted = struct.unpack_from(">HB", data, 0)
    reason, _ = _unpack_str(data, 3)
    return {"config_version": config_version, "accepted": bool(accepted), "reason": reason}


def _encode_time_sync(fields: Mapping[str, object]) -> bytes:
    _require(fields, "master_ticks")
    return struct.pack(">q", int(fields["master_ticks"]))


def _decode_time_sync(data: bytes) -> Dict[str, object]:
    if len(data) != 8:
        raise ProtocolError("TIME_SYNC payload must be 8 bytes")
    return {"master_ticks": struct.unpack(">q", data)[0]}


def _encode_time_ack(fields: Mapping[str, object]) -> bytes:
    _require(fields, "master_ticks", "local_ticks")
    return struct.pack(">qq", int(fields["master_ticks"]), int(fields["local_ticks"]))


def _decode_time_ack(data: bytes) -> Dict[str, object]:
    if len(data) != 16:
        raise ProtocolError("TIME_ACK payload must be 16 bytes")
    master_ticks, local_ticks = struct.unpack(">qq", data)
    return {"master_ticks": master_ticks, "local_ticks": local_ticks}


def _encode_identify_ack(fields: Mapping[str, object]) -> bytes:
    _require(fields, "product_id", "site_id", "group_id", "lamp_id", "mcu_unique_id")
    return b"".join(
        _pack_str(str(fields[name]))
        for name in ("product_id", "site_id", "group_id", "lamp_id", "mcu_unique_id")
    )


def _decode_identify_ack(data: bytes) -> Dict[str, object]:
    offset = 0
    values = []
    for _ in range(5):
        value, offset = _unpack_str(data, offset)
        values.append(value)
    return {
        "product_id": values[0],
        "site_id": values[1],
        "group_id": values[2],
        "lamp_id": values[3],
        "mcu_unique_id": values[4],
    }


def _encode_heartbeat_ack(fields: Mapping[str, object]) -> bytes:
    _require(fields, "local_ticks")
    return struct.pack(">q", int(fields["local_ticks"]))


def _decode_heartbeat_ack(data: bytes) -> Dict[str, object]:
    if len(data) != 8:
        raise ProtocolError("HEARTBEAT_ACK payload must be 8 bytes")
    return {"local_ticks": struct.unpack(">q", data)[0]}


_CODECS: Dict[MessageType, Tuple[Encoder, Decoder]] = {
    MessageType.STATUS_REQUEST: (_encode_empty, _decode_empty),
    MessageType.STATUS_RESPONSE: (_encode_status_response, _decode_status_response),
    MessageType.MEASUREMENT_REQUEST: (_encode_empty, _decode_empty),
    MessageType.MEASUREMENT_RESPONSE: (
        _encode_measurement_response,
        _decode_measurement_response,
    ),
    MessageType.CONTROL_COMMAND: (_encode_control_command, _decode_control_command),
    MessageType.CONTROL_ACK: (_encode_control_ack, _decode_control_ack),
    MessageType.FAULT_REPORT: (_encode_fault_report, _decode_fault_report),
    MessageType.EVENT_REPORT: (_encode_event_report, _decode_event_report),
    MessageType.CONFIG_READ: (_encode_empty, _decode_empty),
    MessageType.CONFIG_WRITE: (_encode_config_write, _decode_config_write),
    MessageType.CONFIG_ACK: (_encode_config_ack, _decode_config_ack),
    MessageType.TIME_SYNC: (_encode_time_sync, _decode_time_sync),
    MessageType.TIME_ACK: (_encode_time_ack, _decode_time_ack),
    MessageType.IDENTIFY: (_encode_empty, _decode_empty),
    MessageType.IDENTIFY_ACK: (_encode_identify_ack, _decode_identify_ack),
    MessageType.HEARTBEAT: (_encode_empty, _decode_empty),
    MessageType.HEARTBEAT_ACK: (_encode_heartbeat_ack, _decode_heartbeat_ack),
}


class MessageCodec:
    """Registry of payload codecs, one pair per message type."""

    @staticmethod
    def supports(message_type: MessageType) -> bool:
        return message_type in _CODECS

    @staticmethod
    def encode(message_type: MessageType, fields: Mapping[str, object]) -> bytes:
        try:
            encoder, _ = _CODECS[message_type]
        except KeyError:
            raise ProtocolError("no codec for message type %s" % message_type.value)
        return encoder(fields)

    @staticmethod
    def decode(message_type: MessageType, payload: bytes) -> Dict[str, object]:
        try:
            _, decoder = _CODECS[message_type]
        except KeyError:
            raise ProtocolError("no codec for message type %s" % message_type.value)
        return decoder(payload)


def encode_payload(message_type: MessageType, fields: Mapping[str, object]) -> bytes:
    return MessageCodec.encode(message_type, fields)


def decode_payload(message_type: MessageType, payload: bytes) -> Dict[str, object]:
    return MessageCodec.decode(message_type, payload)
