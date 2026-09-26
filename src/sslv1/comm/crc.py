"""CRC-16/XMODEM used for frame integrity.

Polynomial 0x1021, initial value 0x0000, no reflection, no final XOR. This is
a deterministic, dependency-free implementation.
"""

from __future__ import annotations

_CRC16_POLY = 0x1021


def crc16_xmodem(data: bytes, initial: int = 0x0000) -> int:
    """Compute the CRC-16/XMODEM of ``data``."""
    crc = initial & 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ _CRC16_POLY) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return crc & 0xFFFF
