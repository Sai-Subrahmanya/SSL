"""Communication package for the Smart Street Light V1 digital prototype.

This is a **protocol/domain simulation layer**, not a physical RS-485 driver.
It implements the architectural baseline from
``docs/05_communication_architecture.md``:

* frame structure (SOF, protocol version, source, destination, message type,
  payload length, payload, sequence number, CRC),
* the initial message type set,
* sequence numbering, duplicate detection and stale-message detection,
* CRC integrity verification,
* timeout and retry handling,
* the communication state machine.

No UART, transceiver, timing or electrical behaviour is modelled.
"""

from ..enums import MessageType  # noqa: F401  (re-exported)
from .crc import crc16_xmodem
from .frame import (
    MAX_PAYLOAD_LENGTH,
    PROTOCOL_VERSION,
    SOF,
    Frame,
    FrameError,
    code_for,
    decode_frame,
    encode_frame,
    message_type_for_code,
)
from .protocol import (
    MessageCodec,
    decode_payload,
    encode_payload,
)
from .state_machine import CommunicationStateMachine
from ..enums import MessageType
from .bus import BusEndpoint, InMemoryBus

__all__ = [
    "crc16_xmodem",
    "MessageType",
    "Frame",
    "FrameError",
    "SOF",
    "PROTOCOL_VERSION",
    "MAX_PAYLOAD_LENGTH",
    "encode_frame",
    "decode_frame",
    "code_for",
    "message_type_for_code",
    "MessageCodec",
    "encode_payload",
    "decode_payload",
    "CommunicationStateMachine",
    "BusEndpoint",
    "InMemoryBus",
]
