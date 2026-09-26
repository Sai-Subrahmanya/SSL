"""Frame encoding and decoding.

Frame layout (big-endian)::

    +--------+------------------+-----------------+---------------------+
    | SOF    | Protocol Version | Source Address  | Destination Address |
    +--------+------------------+-----------------+---------------------+
    | Message Type | Payload Length | Payload | Sequence Number | CRC |
    +-------------------------------------------------------------------+

* ``SOF``             1 byte
* ``Protocol Version`` 1 byte
* ``Source Address``   1 byte
* ``Destination Address`` 1 byte
* ``Message Type``     1 byte
* ``Payload Length``   2 bytes
* ``Payload``          N bytes
* ``Sequence Number``  2 bytes
* ``CRC``              2 bytes (CRC-16/XMODEM over every preceding byte)
"""

from __future__ import annotations

from dataclasses import dataclass

from ..enums import MessageType
from ..errors import IntegrityError, ProtocolError
from .crc import crc16_xmodem

#: Destination address meaning "every node on the bus".
BROADCAST_DESTINATION = 0xFF
#: Address used by the Group Controller (bus master).
MASTER_ADDRESS = 0x00

#: Start-of-frame delimiter.
SOF = 0xA5
#: Protocol version implemented by this layer.
PROTOCOL_VERSION = 0x01
#: Maximum payload length accepted by the frame layer.
MAX_PAYLOAD_LENGTH = 0xFFFF

_HEADER_SIZE = 7
_TRAILER_SIZE = 4  # sequence number (2) + CRC (2)

#: Wire codes are the ordinal position of each message type in the enum. The
#: mapping is stable for a given protocol version and is asserted by tests.
_MESSAGE_TYPES = tuple(MessageType)


def code_for(message_type: MessageType) -> int:
    """Return the wire code for a message type."""
    try:
        return _MESSAGE_TYPES.index(message_type)
    except ValueError:
        raise ProtocolError("unknown message type %r" % (message_type,))


def message_type_for_code(code: int) -> MessageType:
    """Return the message type for a wire code."""
    try:
        return _MESSAGE_TYPES[code]
    except IndexError:
        raise ProtocolError("unknown message type code %d" % code)


@dataclass(frozen=True)
class Frame:
    """A protocol frame."""

    source: int
    destination: int
    message_type: MessageType
    payload: bytes = b""
    sequence: int = 0
    protocol_version: int = PROTOCOL_VERSION

    def __post_init__(self) -> None:
        if not (0 <= self.source <= 255):
            raise ProtocolError("source address must fit in one byte")
        if not (0 <= self.destination <= 255):
            raise ProtocolError("destination address must fit in one byte")
        if not (0 <= self.sequence <= 0xFFFF):
            raise ProtocolError("sequence number must fit in two bytes")
        if len(self.payload) > MAX_PAYLOAD_LENGTH:
            raise ProtocolError("payload too long")

    # ------------------------------------------------------------------
    def body(self) -> bytes:
        """Every byte of the frame except the trailing CRC."""
        return b"".join(
            [
                bytes([SOF, self.protocol_version, self.source, self.destination]),
                bytes([code_for(self.message_type)]),
                len(self.payload).to_bytes(2, "big"),
                self.payload,
                self.sequence.to_bytes(2, "big"),
            ]
        )

    def crc(self) -> int:
        return crc16_xmodem(self.body())

    def encode(self) -> bytes:
        return self.body() + self.crc().to_bytes(2, "big")


def encode_frame(frame: Frame) -> bytes:
    return frame.encode()


def decode_frame(data: bytes) -> Frame:
    """Decode and integrity-check a frame.

    Raises :class:`IntegrityError` when the CRC does not match and
    :class:`ProtocolError` for structural problems. A frame that fails its
    check is never returned to the caller.
    """
    if len(data) < _HEADER_SIZE + _TRAILER_SIZE:
        raise ProtocolError("frame too short: %d bytes" % len(data))
    if data[0] != SOF:
        raise ProtocolError("bad start-of-frame byte 0x%02X" % data[0])

    protocol_version = data[1]
    source = data[2]
    destination = data[3]
    message_code = data[4]
    payload_length = int.from_bytes(data[5:7], "big")
    expected_length = _HEADER_SIZE + payload_length + _TRAILER_SIZE
    if len(data) != expected_length:
        raise ProtocolError(
            "frame length %d does not match payload length %d (expected %d)"
            % (len(data), payload_length, expected_length)
        )

    payload = data[_HEADER_SIZE : _HEADER_SIZE + payload_length]
    sequence = int.from_bytes(
        data[_HEADER_SIZE + payload_length : _HEADER_SIZE + payload_length + 2], "big"
    )
    received_crc = int.from_bytes(data[-2:], "big")

    body = data[:-2]
    if crc16_xmodem(body) != received_crc:
        raise IntegrityError("frame failed CRC check")

    frame = Frame(
        source=source,
        destination=destination,
        message_type=message_type_for_code(message_code),
        payload=payload,
        sequence=sequence,
        protocol_version=protocol_version,
    )
    return frame


class FrameError(ProtocolError):
    """Raised when a frame cannot be built or parsed."""


def describe(frame: Frame) -> str:
    return "Frame(src=%d dst=%d type=%s seq=%d len=%d)" % (
        frame.source,
        frame.destination,
        frame.message_type.value,
        frame.sequence,
        len(frame.payload),
    )
