"""Communication protocol and state machine tests (PR-COMM-*).

Covers: frame structure, CRC validation, message type set, duplicate and
stale detection, timeout/retry, and the communication state machine.
"""


import pytest

from sslv1.comm import (
    CommunicationStateMachine,
    Frame,
    InMemoryBus,
    MAX_PAYLOAD_LENGTH,
    PROTOCOL_VERSION,
    SOF,
    BusEndpoint,
    code_for,
    decode_frame,
    decode_payload,
    encode_frame,
    encode_payload,
    message_type_for_code,
)
from sslv1.comm.crc import crc16_xmodem
from sslv1.enums import (
    CommunicationStatus,
    CommState,
    ControlSubtype,
    FaultState,
    FaultType,
    LampState,
    MessageType,
    NotificationState,
    SensorStatus,
)
from sslv1.errors import IntegrityError, ProtocolError

EXPECTED_MESSAGE_TYPES = [
    "STATUS_REQUEST", "STATUS_RESPONSE", "MEASUREMENT_REQUEST",
    "MEASUREMENT_RESPONSE", "CONTROL_COMMAND", "CONTROL_ACK", "FAULT_REPORT",
    "EVENT_REPORT", "CONFIG_READ", "CONFIG_WRITE", "CONFIG_ACK", "TIME_SYNC",
    "TIME_ACK", "IDENTIFY", "IDENTIFY_ACK", "HEARTBEAT", "HEARTBEAT_ACK",
]


# --------------------------------------------------------------------------
# frame structure and CRC
# --------------------------------------------------------------------------
def test_message_type_set_is_complete():
    assert [m.value for m in MessageType] == EXPECTED_MESSAGE_TYPES
    assert len(list(MessageType)) == 17


def test_frame_contains_every_required_field():
    frame = Frame(
        source=1,
        destination=0,
        message_type=MessageType.STATUS_RESPONSE,
        payload=b"\x01\x02",
        sequence=42,
    )
    encoded = encode_frame(frame)
    assert encoded[0] == SOF
    assert encoded[1] == PROTOCOL_VERSION
    assert encoded[2] == 1  # source
    assert encoded[3] == 0  # destination
    assert encoded[4] == code_for(MessageType.STATUS_RESPONSE)
    assert int.from_bytes(encoded[5:7], "big") == 2  # payload length
    assert encoded[7:9] == b"\x01\x02"  # payload
    assert int.from_bytes(encoded[9:11], "big") == 42  # sequence number
    assert int.from_bytes(encoded[11:13], "big") == crc16_xmodem(encoded[:-2])


def test_frame_round_trip():
    frame = Frame(source=3, destination=0, message_type=MessageType.HEARTBEAT,
                  payload=b"abc", sequence=7)
    decoded = decode_frame(encode_frame(frame))
    assert decoded == frame


def test_crc_failure_is_detected():
    frame = Frame(source=1, destination=0, message_type=MessageType.STATUS_REQUEST,
                  sequence=1)
    raw = bytearray(encode_frame(frame))
    raw[-1] ^= 0x01
    with pytest.raises(IntegrityError):
        decode_frame(bytes(raw))


def test_bad_start_of_frame_is_rejected():
    raw = bytearray(encode_frame(Frame(0, 0, MessageType.STATUS_REQUEST)))
    raw[0] = 0x00
    with pytest.raises(ProtocolError):
        decode_frame(bytes(raw))


def test_truncated_frame_is_rejected():
    with pytest.raises(ProtocolError):
        decode_frame(b"\x01\x02\x03")


def test_length_mismatch_is_rejected():
    frame = Frame(source=1, destination=0, message_type=MessageType.STATUS_REQUEST,
                  payload=b"xy", sequence=1)
    raw = bytearray(encode_frame(frame))
    raw = raw[:-1]  # drop a byte
    with pytest.raises(ProtocolError):
        decode_frame(bytes(raw))


def test_unknown_message_type_code_is_rejected():
    with pytest.raises(ProtocolError):
        message_type_for_code(200)


def test_oversized_payload_is_rejected():
    with pytest.raises(ProtocolError):
        Frame(source=1, destination=0, message_type=MessageType.STATUS_REQUEST,
              payload=b"x" * (MAX_PAYLOAD_LENGTH + 1))


def test_address_range_is_enforced():
    with pytest.raises(ProtocolError):
        Frame(source=256, destination=0, message_type=MessageType.STATUS_REQUEST)


def test_message_type_codes_are_stable():
    codes = {m: code_for(m) for m in MessageType}
    assert len(set(codes.values())) == len(codes)


# --------------------------------------------------------------------------
# payload codecs
# --------------------------------------------------------------------------
def test_measurement_payload_round_trip():
    payload = encode_payload(
        MessageType.MEASUREMENT_RESPONSE,
        {
            "timestamp_ticks": 1234,
            "voltage_mv": 230000,
            "current_ma": 450,
            "power_mw": 103500,
            "energy_mwh": 12000,
            "light_level": 42,
            "operating_mode": __import__("sslv1.enums", fromlist=["OperatingMode"]).OperatingMode.AUTO_SENSOR,
            "commanded_state": LampState.ON,
            "switching_feedback": LampState.ON,
            "actual_state": LampState.ON,
            "sensor_status": SensorStatus.VALID,
            "communication_status": CommunicationStatus.COMM_HEALTHY,
            "controller_status": __import__("sslv1.enums", fromlist=["ControllerStatus"]).ControllerStatus.NORMAL,
        },
    )
    decoded = decode_payload(MessageType.MEASUREMENT_RESPONSE, payload)
    assert decoded["voltage_mv"] == 230000
    assert decoded["current_ma"] == 450
    assert decoded["operating_mode"].value == "AUTO_SENSOR"


def test_control_command_payload_carries_reset_energy_subtype():
    payload = encode_payload(
        MessageType.CONTROL_COMMAND,
        {
            "subtype": ControlSubtype.RESET_ENERGY,
            "target_state": LampState.UNKNOWN,
            "command_id": "cmd-1",
            "parameter": 0,
        },
    )
    decoded = decode_payload(MessageType.CONTROL_COMMAND, payload)
    assert decoded["subtype"] is ControlSubtype.RESET_ENERGY
    assert decoded["command_id"] == "cmd-1"


def test_config_write_payload_round_trip():
    payload = encode_payload(
        MessageType.CONFIG_WRITE,
        {"config_version": 3, "parameters": {"comm_timeout_ticks": 500,
                                             "fault_confirmation_count": 3}},
    )
    decoded = decode_payload(MessageType.CONFIG_WRITE, payload)
    assert decoded["config_version"] == 3
    assert decoded["parameters"]["comm_timeout_ticks"] == 500


def test_time_sync_payload_round_trip():
    payload = encode_payload(MessageType.TIME_SYNC, {"master_ticks": 98765})
    assert decode_payload(MessageType.TIME_SYNC, payload)["master_ticks"] == 98765


def test_identify_payload_round_trip():
    payload = encode_payload(
        MessageType.IDENTIFY_ACK,
        {
            "product_id": "SSL-V1",
            "site_id": "SITE-A",
            "group_id": "GRP-01",
            "lamp_id": "LAMP-01",
            "mcu_unique_id": "0a0b0c0d",
        },
    )
    decoded = decode_payload(MessageType.IDENTIFY_ACK, payload)
    assert decoded["lamp_id"] == "LAMP-01"


def test_fault_report_payload_round_trip():
    payload = encode_payload(
        MessageType.FAULT_REPORT,
        {
            "fault_id": "F-0001",
            "fault_type": FaultType.UNDER_CURRENT,
            "diagnostic_classification": __import__(
                "sslv1.enums", fromlist=["DiagnosticClassification"]
            ).DiagnosticClassification.POSSIBLE_OPEN_LOAD,
            "fault_state": FaultState.CONFIRMED,
            "notification_state": NotificationState.ACK_PENDING,
            "severity": __import__("sslv1.enums", fromlist=["FaultSeverity"]).FaultSeverity.MAJOR,
            "confirmation_count": 3,
        },
    )
    decoded = decode_payload(MessageType.FAULT_REPORT, payload)
    assert decoded["fault_state"] is FaultState.CONFIRMED
    assert decoded["confirmation_count"] == 3


def test_empty_payload_codec_rejects_data():
    with pytest.raises(ProtocolError):
        decode_payload(MessageType.STATUS_REQUEST, b"\x00")


def test_malformed_payload_is_rejected():
    with pytest.raises(ProtocolError):
        decode_payload(MessageType.CONTROL_ACK, b"\x01")


# --------------------------------------------------------------------------
# bus behaviour
# --------------------------------------------------------------------------
class Recorder(BusEndpoint):
    def __init__(self):
        self.frames = []

    def receive(self, frame):
        self.frames.append(frame)


def test_bus_delivers_to_the_addressed_node():
    bus = InMemoryBus()
    node = Recorder()
    other = Recorder()
    bus.attach(1, node)
    bus.attach(2, other)
    bus.send(Frame(source=0, destination=1, message_type=MessageType.STATUS_REQUEST,
                   sequence=1))
    assert len(node.frames) == 1
    assert other.frames == []


def test_bus_drops_frames_from_a_silent_node():
    bus = InMemoryBus()
    node = Recorder()
    bus.attach(1, node)
    bus.set_silent(1)
    delivered = bus.send(
        Frame(source=0, destination=1, message_type=MessageType.STATUS_REQUEST,
              sequence=1)
    )
    assert delivered is False
    assert node.frames == []
    assert bus.stats.dropped == 1


def test_bus_reports_undeliverable_destinations():
    bus = InMemoryBus()
    delivered = bus.send(
        Frame(source=0, destination=99, message_type=MessageType.STATUS_REQUEST,
              sequence=1)
    )
    assert delivered is False
    assert bus.stats.undeliverable == 1


def test_bus_corruption_is_detectable():
    bus = InMemoryBus()
    node = Recorder()
    bus.attach(1, node)
    bus.corrupt_next_frame()
    with pytest.raises(IntegrityError):
        bus.send(Frame(source=0, destination=1, message_type=MessageType.STATUS_REQUEST,
                       sequence=1))
    assert bus.stats.corrupted == 1


def test_duplicate_address_is_rejected():
    bus = InMemoryBus()
    bus.attach(1, Recorder())
    with pytest.raises(ProtocolError):
        bus.attach(1, Recorder())


# --------------------------------------------------------------------------
# 21./22./23. communication state machine
# --------------------------------------------------------------------------
def test_healthy_to_retry_to_degraded_to_fault():
    machine = CommunicationStateMachine(retry_limit=2)
    assert machine.state is CommState.COMM_HEALTHY
    machine.record_failure()
    assert machine.state is CommState.RETRY
    machine.record_failure()
    assert machine.state is CommState.RETRY
    machine.record_failure()  # exceeds the retry limit
    assert machine.state is CommState.DEGRADED
    machine.record_failure()
    assert machine.state is CommState.COMM_FAULT


def test_recovery_returns_to_healthy():
    machine = CommunicationStateMachine(retry_limit=1)
    machine.record_failure()
    machine.record_failure()
    machine.record_failure()
    assert machine.state is CommState.COMM_FAULT

    machine.begin_recovery()
    assert machine.state is CommState.RECOVERY
    machine.record_success()
    assert machine.state is CommState.COMM_HEALTHY


def test_retry_recovers_to_healthy():
    machine = CommunicationStateMachine(retry_limit=3)
    machine.record_failure()
    assert machine.state is CommState.RETRY
    machine.record_success()
    assert machine.state is CommState.COMM_HEALTHY


def test_illegal_communication_transition_is_rejected():
    machine = CommunicationStateMachine()
    machine._state = CommState.COMM_HEALTHY
    from sslv1.errors import IllegalTransitionError

    with pytest.raises(IllegalTransitionError):
        machine._move(CommState.COMM_FAULT, "invalid jump")


def test_state_machine_records_history():
    machine = CommunicationStateMachine(retry_limit=1)
    machine.record_failure()
    machine.record_failure()
    machine.record_success()
    assert [t.to_state for t in machine.history] == [
        CommState.RETRY, CommState.DEGRADED, CommState.COMM_HEALTHY,
    ]
    assert machine.history[0].from_state is CommState.COMM_HEALTHY
