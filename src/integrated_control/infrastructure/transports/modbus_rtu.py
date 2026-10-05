from collections.abc import Iterable
import time
from typing import Protocol

from integrated_control.domain.errors import ProtocolError, TransportError


class TransactionTransport(Protocol):
    def open(self) -> None: ...

    def transact_exact(self, request: bytes, *, response_size: int) -> bytes: ...

    def close(self) -> None: ...


def crc16(data: bytes) -> bytes:
    value = 0xFFFF
    for byte in data:
        value ^= byte
        for _ in range(8):
            value = (value >> 1) ^ 0xA001 if value & 1 else value >> 1
    return value.to_bytes(2, byteorder="little")


class ModbusRtuClient:
    def __init__(
        self,
        transport: TransactionTransport,
        *,
        slave_id: int = 1,
        retries: int = 3,
        continuous_failure_timeout_s: float | None = None,
        retry_interval_s: float = 0.05,
    ) -> None:
        if not 1 <= slave_id <= 247:
            raise ValueError("Modbus slave_id must be within 1..247")
        if retries < 1:
            raise ValueError("retries must be positive")
        if (
            continuous_failure_timeout_s is not None
            and continuous_failure_timeout_s <= 0
        ):
            raise ValueError("continuous failure timeout must be positive")
        if retry_interval_s < 0:
            raise ValueError("retry interval cannot be negative")
        self.transport = transport
        self.slave_id = slave_id
        self.retries = retries
        self.continuous_failure_timeout_s = continuous_failure_timeout_s
        self.retry_interval_s = retry_interval_s
        self.recovered_error_count = 0

    def open(self) -> None:
        self.transport.open()

    def close(self) -> None:
        self.transport.close()

    def read_holding_registers(
        self,
        address: int,
        count: int = 1,
        *,
        slave_id: int | None = None,
    ) -> list[int]:
        slave = slave_id or self.slave_id
        payload = bytes(
            [slave, 0x03]
            + list(address.to_bytes(2, "big"))
            + list(count.to_bytes(2, "big"))
        )
        response = self._exchange(
            payload,
            slave,
            0x03,
            response_size=5 + count * 2,
        )
        byte_count = response[2]
        expected = count * 2
        if byte_count != expected or len(response) != expected + 5:
            raise ProtocolError(
                f"Unexpected Modbus read length: expected {expected} data bytes, "
                f"received {byte_count}"
            )
        data = response[3 : 3 + byte_count]
        return [
            int.from_bytes(data[index : index + 2], "big")
            for index in range(0, len(data), 2)
        ]

    def read_data_bytes(
        self,
        address: int,
        count: int,
        *,
        slave_id: int | None = None,
    ) -> bytes:
        registers = self.read_holding_registers(
            address, count, slave_id=slave_id
        )
        return b"".join(register.to_bytes(2, "big") for register in registers)

    def write_single_register(
        self,
        address: int,
        value: int,
        *,
        slave_id: int | None = None,
    ) -> None:
        slave = slave_id or self.slave_id
        payload = bytes(
            [slave, 0x06]
            + list(address.to_bytes(2, "big"))
            + list((value & 0xFFFF).to_bytes(2, "big"))
        )
        response = self._exchange(payload, slave, 0x06, response_size=8)
        if response[:-2] != payload:
            raise ProtocolError("Modbus write echo does not match the request")

    def write_multiple_registers(
        self,
        address: int,
        values: Iterable[int],
        *,
        slave_id: int | None = None,
    ) -> None:
        slave = slave_id or self.slave_id
        registers = list(values)
        data = b"".join((value & 0xFFFF).to_bytes(2, "big") for value in registers)
        payload = bytes(
            [slave, 0x10]
            + list(address.to_bytes(2, "big"))
            + list(len(registers).to_bytes(2, "big"))
            + [len(data)]
        ) + data
        response = self._exchange(payload, slave, 0x10, response_size=8)
        expected = bytes(
            [slave, 0x10]
            + list(address.to_bytes(2, "big"))
            + list(len(registers).to_bytes(2, "big"))
        )
        if response[:-2] != expected:
            raise ProtocolError("Modbus multiple-write acknowledgement is invalid")

    def _exchange(
        self,
        payload: bytes,
        slave: int,
        function: int,
        *,
        response_size: int,
    ) -> bytes:
        request = payload + crc16(payload)
        last_error: Exception | None = None
        failures = 0
        failure_started_at: float | None = None
        while True:
            try:
                response = self.transport.transact_exact(
                    request, response_size=response_size
                )
                self._validate_response(response, slave, function)
                if failures:
                    self.recovered_error_count += failures
                return response
            except (TransportError, ProtocolError) as exc:
                last_error = exc
                failures += 1
                if self.continuous_failure_timeout_s is None:
                    if failures >= self.retries:
                        raise last_error
                else:
                    now = time.monotonic()
                    if failure_started_at is None:
                        failure_started_at = now
                    if now - failure_started_at >= self.continuous_failure_timeout_s:
                        raise last_error
                if self.retry_interval_s:
                    time.sleep(self.retry_interval_s)

    @staticmethod
    def _validate_response(response: bytes, slave: int, function: int) -> None:
        if len(response) < 5:
            raise ProtocolError(f"Incomplete Modbus response: {response.hex(' ')}")
        if crc16(response[:-2]) != response[-2:]:
            raise ProtocolError(
                f"Modbus CRC mismatch; received: {response.hex(' ')}"
            )
        if response[0] != slave:
            raise ProtocolError(
                f"Unexpected Modbus slave {response[0]}, expected {slave}"
            )
        if response[1] == function | 0x80:
            raise ProtocolError(f"Modbus exception code {response[2]}")
        if response[1] != function:
            raise ProtocolError(
                f"Unexpected Modbus function {response[1]}, expected {function}"
            )
