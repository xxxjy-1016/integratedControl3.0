from dataclasses import dataclass
from threading import RLock
import time
from typing import Any

from integrated_control.domain.errors import (
    CommunicationTimeoutError,
    TransportError,
)


@dataclass(frozen=True)
class SerialSettings:
    port: str
    baudrate: int
    timeout_s: float = 1.0
    response_delay_s: float = 0.05


class SerialTransport:
    """Thread-safe, lazily opened serial byte transport."""

    def __init__(
        self,
        settings: SerialSettings,
        *,
        serial_instance: Any | None = None,
    ) -> None:
        self.settings = settings
        self._serial = serial_instance
        self._owns_serial = serial_instance is None
        self._lock = RLock()

    @property
    def is_open(self) -> bool:
        return self._serial is not None and bool(
            getattr(self._serial, "is_open", True)
        )

    def open(self) -> None:
        with self._lock:
            if self.is_open:
                return
            if self._serial is not None and not self._owns_serial:
                opener = getattr(self._serial, "open", None)
                if opener is not None:
                    opener()
                return
            try:
                import serial
            except ModuleNotFoundError as exc:
                raise TransportError(
                    "pyserial is required for hardware mode; install the hardware extra"
                ) from exc
            try:
                self._serial = serial.Serial(
                    self.settings.port,
                    self.settings.baudrate,
                    timeout=self.settings.timeout_s,
                )
            except Exception as exc:
                raise TransportError(
                    f"Cannot open serial port {self.settings.port}: {exc}"
                ) from exc

    def transact(
        self,
        request: bytes,
        *,
        response_size: int = 256,
        reset_buffers: bool = True,
    ) -> bytes:
        with self._lock:
            self.open()
            assert self._serial is not None
            try:
                if reset_buffers:
                    reset_input = getattr(self._serial, "reset_input_buffer", None)
                    reset_output = getattr(self._serial, "reset_output_buffer", None)
                    if reset_input is not None:
                        reset_input()
                    if reset_output is not None:
                        reset_output()
                self._serial.write(request)
                time.sleep(self.settings.response_delay_s)
                response = bytes(self._serial.read(response_size))
            except Exception as exc:
                raise TransportError(
                    f"Serial exchange failed on {self.settings.port}: {exc}"
                ) from exc
            if not response:
                raise CommunicationTimeoutError(
                    f"No response from {self.settings.port}"
                )
            return response

    def transact_exact(
        self,
        request: bytes,
        *,
        response_size: int,
        reset_buffers: bool = True,
    ) -> bytes:
        """Write a request and collect one fixed-length binary response.

        Modbus RTU responses have a known frame length.  Unlike ``transact``,
        this method keeps reading when a non-blocking serial port delivers the
        frame in multiple chunks.
        """
        if response_size <= 0:
            raise ValueError("response_size must be positive")
        with self._lock:
            self.open()
            assert self._serial is not None
            try:
                if reset_buffers:
                    reset_input = getattr(self._serial, "reset_input_buffer", None)
                    reset_output = getattr(self._serial, "reset_output_buffer", None)
                    if reset_input is not None:
                        reset_input()
                    if reset_output is not None:
                        reset_output()
                self._serial.write(request)
                time.sleep(self.settings.response_delay_s)
                response = bytearray()
                receive_window_s = max(
                    self.settings.timeout_s,
                    self.settings.response_delay_s,
                    0.1,
                )
                deadline = time.monotonic() + receive_window_s
                while len(response) < response_size:
                    chunk = self._serial.read(response_size - len(response))
                    if chunk:
                        response.extend(chunk)
                        continue
                    if time.monotonic() >= deadline:
                        break
                    time.sleep(0.005)
            except Exception as exc:
                raise TransportError(
                    f"Serial exchange failed on {self.settings.port}: {exc}"
                ) from exc
            if not response:
                raise CommunicationTimeoutError(
                    f"No response from {self.settings.port}"
                )
            return bytes(response)

    def write(self, request: bytes, *, reset_buffers: bool = True) -> None:
        """Write a command that has no immediate response.

        Some of the workstation's ASCII controllers acknowledge completion only
        through a later status query.  Keeping that distinction in the transport
        prevents a fire-and-query command from being reported as a timeout.
        """
        with self._lock:
            self.open()
            assert self._serial is not None
            try:
                if reset_buffers:
                    reset_input = getattr(self._serial, "reset_input_buffer", None)
                    reset_output = getattr(self._serial, "reset_output_buffer", None)
                    if reset_input is not None:
                        reset_input()
                    if reset_output is not None:
                        reset_output()
                self._serial.write(request)
            except Exception as exc:
                raise TransportError(
                    f"Serial write failed on {self.settings.port}: {exc}"
                ) from exc

    def close(self) -> None:
        with self._lock:
            if self._serial is None:
                return
            try:
                self._serial.close()
            except Exception as exc:
                raise TransportError(
                    f"Cannot close serial port {self.settings.port}: {exc}"
                ) from exc
            finally:
                if self._owns_serial:
                    self._serial = None
