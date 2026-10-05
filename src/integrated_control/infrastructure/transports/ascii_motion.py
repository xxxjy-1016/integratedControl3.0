from __future__ import annotations

import time
from typing import Protocol

from integrated_control.domain.errors import (
    CommunicationTimeoutError,
    ProtocolError,
)
from integrated_control.infrastructure.transports.modbus_rtu import crc16


class AsciiSerialTransport(Protocol):
    """Byte-transport capabilities required by the ASCII device protocol."""

    def open(self) -> None: ...

    def write(self, request: bytes, *, reset_buffers: bool = True) -> None: ...

    def transact(
        self,
        request: bytes,
        *,
        response_size: int = 256,
        reset_buffers: bool = True,
    ) -> bytes: ...

    def close(self) -> None: ...


def append_ascii_crc(payload: bytes) -> bytes:
    """Append the controller's four-character, high-byte-first CRC field."""
    return payload + crc16(payload)[::-1].hex().upper().encode("ascii")


def signed_hex_command(prefix: bytes, value: int, *, width: int) -> bytes:
    try:
        encoded = value.to_bytes(width, "big", signed=value < 0)
    except OverflowError as exc:
        raise ValueError(f"Value {value} does not fit in {width} bytes") from exc
    # The legacy controller protocol uses lower-case hex digits in the data
    # field, while the four CRC characters are upper-case. CRC is calculated
    # over those exact ASCII bytes, so preserving the case is significant.
    return append_ascii_crc(prefix + encoded.hex().encode("ascii"))


def wait_for_ascii_status(
    transport: AsciiSerialTransport,
    query: bytes,
    expected: bytes,
    *,
    timeout_s: float,
    poll_interval_s: float,
    response_size: int = 40,
) -> bytes:
    deadline = time.monotonic() + timeout_s
    last_response = b""
    while time.monotonic() < deadline:
        try:
            last_response = transport.transact(query, response_size=response_size).strip()
        except CommunicationTimeoutError:
            last_response = b""
        if last_response == expected:
            return last_response
        if last_response and not last_response.startswith(b">"):
            raise ProtocolError(
                f"Unexpected ASCII controller response: {last_response!r}"
            )
        time.sleep(poll_interval_s)
    detail = f"; last response was {last_response!r}" if last_response else ""
    raise CommunicationTimeoutError(f"ASCII device operation timed out{detail}")
