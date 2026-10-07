import unittest

from integrated_control.domain.errors import ProtocolError
from integrated_control.infrastructure.transports.modbus_rtu import (
    ModbusRtuClient,
    crc16,
)
from integrated_control.infrastructure.transports.serial_transport import (
    SerialSettings,
    SerialTransport,
)


class ScriptedTransport:
    """Group checks for scripted transport."""
    def __init__(self, responses: list[bytes]) -> None:
        """Initialize scripted transport dependencies and internal state."""
        self.responses = list(responses)
        self.requests: list[bytes] = []
        self.response_sizes: list[int] = []

    def open(self) -> None:
        """Open."""
        pass

    def close(self) -> None:
        """Close."""
        pass

    def transact_exact(self, request: bytes, *, response_size: int) -> bytes:
        """Transact exact."""
        self.requests.append(request)
        self.response_sizes.append(response_size)
        return self.responses.pop(0)


def frame(payload: bytes) -> bytes:
    """Frame."""
    return payload + crc16(payload)


class ChunkedSerial:
    """Group checks for chunked serial."""
    def __init__(self, chunks: list[bytes]) -> None:
        """Initialize chunked serial dependencies and internal state."""
        self.is_open = True
        self.chunks = list(chunks)
        self.writes: list[bytes] = []

    def reset_input_buffer(self) -> None:
        """Reset input buffer."""
        pass

    def reset_output_buffer(self) -> None:
        """Reset output buffer."""
        pass

    def write(self, request: bytes) -> None:
        """Write."""
        self.writes.append(request)

    def read(self, size: int) -> bytes:
        """Read."""
        if not self.chunks:
            return b""
        chunk = self.chunks.pop(0)
        if len(chunk) <= size:
            return chunk
        self.chunks.insert(0, chunk[size:])
        return chunk[:size]

    def close(self) -> None:
        """Close."""
        self.is_open = False


class ModbusRtuClientTests(unittest.TestCase):
    """Group checks for modbus rtu client tests."""
    def test_collects_a_modbus_frame_delivered_in_multiple_chunks(self) -> None:
        """Check collects a modbus frame delivered in multiple chunks."""
        response = frame(bytes([1, 3, 4, 0x12, 0x34, 0x56, 0x78]))
        serial = ChunkedSerial(
            [response[:2], response[2:5], response[5:]]
        )
        transport = SerialTransport(
            SerialSettings(
                "COM-test", 115200, timeout_s=0.0, response_delay_s=0.0
            ),
            serial_instance=serial,
        )
        client = ModbusRtuClient(transport, retries=1)

        result = client.read_holding_registers(0x0100, 2)

        self.assertEqual([0x1234, 0x5678], result)

    def test_reads_holding_register(self) -> None:
        """Check reads holding register."""
        transport = ScriptedTransport([frame(bytes([1, 3, 2, 0x12, 0x34]))])
        client = ModbusRtuClient(transport, retries=1)

        result = client.read_holding_registers(0x0100, 1)

        self.assertEqual([0x1234], result)
        self.assertEqual(frame(bytes([1, 3, 1, 0, 0, 1])), transport.requests[0])
        self.assertEqual([7], transport.response_sizes)

    def test_writes_multiple_registers(self) -> None:
        """Check writes multiple registers."""
        acknowledgement = frame(bytes([2, 0x10, 0x23, 0x20, 0, 2]))
        transport = ScriptedTransport([acknowledgement])
        client = ModbusRtuClient(transport, retries=1)

        client.write_multiple_registers(0x2320, [0, 10000], slave_id=2)

        request = transport.requests[0]
        self.assertEqual(2, request[0])
        self.assertEqual(0x10, request[1])
        self.assertEqual(crc16(request[:-2]), request[-2:])
        self.assertEqual([8], transport.response_sizes)

    def test_recovers_from_an_isolated_crc_error(self) -> None:
        """Check recovers from an isolated crc error."""
        good_response = frame(bytes([1, 3, 2, 0x12, 0x34]))
        damaged_response = bytearray(good_response)
        damaged_response[3] ^= 0x80
        transport = ScriptedTransport([bytes(damaged_response), good_response])
        client = ModbusRtuClient(
            transport,
            retries=3,
            retry_interval_s=0.0,
        )

        result = client.read_holding_registers(0x0100, 1)

        self.assertEqual([0x1234], result)
        self.assertEqual(1, client.recovered_error_count)
        self.assertEqual(2, len(transport.requests))

    def test_raises_after_configured_consecutive_failures(self) -> None:
        """Check raises after configured consecutive failures."""
        good_response = frame(bytes([1, 3, 2, 0x12, 0x34]))
        damaged_response = bytearray(good_response)
        damaged_response[3] ^= 0x80
        transport = ScriptedTransport([bytes(damaged_response)] * 100)
        client = ModbusRtuClient(
            transport,
            continuous_failure_timeout_s=0.01,
            retry_interval_s=0.01,
        )

        with self.assertRaisesRegex(ProtocolError, "CRC mismatch"):
            client.read_holding_registers(0x0100, 1)

        self.assertGreaterEqual(len(transport.requests), 2)


if __name__ == "__main__":
    unittest.main()
