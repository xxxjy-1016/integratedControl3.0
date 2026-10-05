from dataclasses import dataclass
import time
from typing import Callable, Protocol

from integrated_control.devices.vacuum_station import VacuumStation
from integrated_control.domain.errors import IntegratedControlError
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.modbus_rtu import crc16


class WriteOnlySerialTransport(Protocol):
    def open(self) -> None: ...

    def write(self, request: bytes, *, reset_buffers: bool = True) -> None: ...

    def close(self) -> None: ...


@dataclass(frozen=True)
class VacuumStationDriverConfig:
    open_position: int = 0
    close_position: int = 250
    initial_speed: int = 10
    open_speed: int = -120
    close_speed: int = 105
    acceleration_time: int = 50
    deceleration_time: int = 50
    command_delay_s: float = 0.2
    open_motion_time_s: float = 2.8
    close_motion_time_s: float = 3.3


class VacuumStationDriver(VacuumStation):
    """Timed lid-motion driver migrated from old_code/evacuationSpace.py."""

    def __init__(
        self,
        transport: WriteOnlySerialTransport,
        config: VacuumStationDriverConfig | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._transport = transport
        self._config = config or VacuumStationDriverConfig()
        self._sleep = sleep
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None
        self._cover_open: bool | None = None

    @property
    def device_id(self) -> str:
        return "vacuum_station"

    def initialize(self) -> ActionResult:
        self._activity = "INITIALIZING"
        try:
            self._transport.open()
            self._expected_stop()
        except IntegratedControlError as exc:
            self._close_after_failure()
            return self._failure("VACUUM_STATION_INITIALIZATION_FAILED", exc)
        self._initialized = True
        self._fault = None
        self._activity = "IDLE"
        return ActionResult.done(
            "Native vacuum-station lid initialized; cover position is unknown"
        )

    def open_cover(self) -> ActionResult:
        return self._move_cover(
            opening=True,
            speed=self._config.open_speed,
            position=self._config.open_position,
            motion_time_s=self._config.open_motion_time_s,
        )

    def close_cover(self) -> ActionResult:
        return self._move_cover(
            opening=False,
            speed=self._config.close_speed,
            position=self._config.close_position,
            motion_time_s=self._config.close_motion_time_s,
        )

    def evacuate(self, target_pressure_kpa: float) -> ActionResult:
        if not self._initialized:
            return ActionResult.failed(
                "DEVICE_NOT_READY", "Vacuum station is not initialized"
            )
        return ActionResult.failed(
            "VACUUM_PRESSURE_CONTROL_UNAVAILABLE",
            "old_code only documents the COM15 lid motor; use the valve driver "
            "for the vacuum line",
        )

    def vent(self) -> ActionResult:
        if not self._initialized:
            return ActionResult.failed(
                "DEVICE_NOT_READY", "Vacuum station is not initialized"
            )
        return ActionResult.failed(
            "VACUUM_VENT_CONTROL_UNAVAILABLE",
            "No vent command is documented in old_code/evacuationSpace.py",
        )

    def stop(self) -> ActionResult:
        error: IntegratedControlError | None = None
        if self._initialized:
            try:
                self._expected_stop()
            except IntegratedControlError as exc:
                error = exc
        try:
            self._transport.close()
        except IntegratedControlError as exc:
            error = error or exc
        self._initialized = False
        self._activity = "IDLE"
        if error is not None:
            return self._failure("VACUUM_STATION_STOP_FAILED", error)
        return ActionResult.done("Vacuum-station lid stopped and connection closed")

    def get_state(self) -> DeviceState:
        lifecycle = "FAULT" if self._fault else (
            "READY" if self._initialized else "OFFLINE"
        )
        return DeviceState(
            self.device_id,
            lifecycle,
            self._activity,
            {
                "cover_open": self._cover_open,
                "position_feedback": False,
                "backend": "native",
            },
            self._fault,
        )

    def _move_cover(
        self,
        *,
        opening: bool,
        speed: int,
        position: int,
        motion_time_s: float,
    ) -> ActionResult:
        if not self._initialized:
            return ActionResult.failed(
                "DEVICE_NOT_READY", "Vacuum station is not initialized"
            )
        self._activity = "OPENING" if opening else "CLOSING"
        try:
            self._expected_stop()
            self._set_motion_arguments(speed)
            self._write_register(0x0039, 1)
            self._write_signed_position(position)
            self._write_register(0x0037, 1)
            self._sleep(motion_time_s)
            self._write_register(0x0038, 0)
        except IntegratedControlError as exc:
            return self._failure("VACUUM_COVER_MOVE_FAILED", exc)
        self._cover_open = opening
        self._activity = "OPEN" if opening else "CLOSED"
        return ActionResult.done(
            f"Vacuum-station cover {'opened' if opening else 'closed'}",
            {"cover_open": opening, "position_feedback": False},
        )

    def _set_motion_arguments(self, speed: int) -> None:
        # Preserve the exact write order and register choices in old_code.
        self._write_register(0x001E, 2000)
        self._write_register(0x001F, 1000)
        self._write_register(0x0030, self._config.initial_speed)
        self._write_register(0x0033, speed)
        self._write_register(0x0030, self._config.acceleration_time)
        self._write_register(0x0030, self._config.deceleration_time)

    def _write_signed_position(self, position: int) -> None:
        encoded = position & 0xFFFFFFFF
        self._write_register(0x0034, encoded & 0xFFFF)
        self._write_register(0x0035, (encoded >> 16) & 0xFFFF)

    def _expected_stop(self) -> None:
        self._write_register(0x0038, 2)

    def _write_register(self, address: int, value: int) -> None:
        payload = bytes(
            [1, 0x06]
            + list(address.to_bytes(2, "big"))
            + list((value & 0xFFFF).to_bytes(2, "big"))
        )
        self._transport.write(payload + crc16(payload))
        self._sleep(self._config.command_delay_s)

    def _close_after_failure(self) -> None:
        try:
            self._transport.close()
        except IntegratedControlError:
            pass

    def _failure(self, code: str, exc: Exception) -> ActionResult:
        self._fault = str(exc) or type(exc).__name__
        self._activity = "FAULT"
        return ActionResult.failed(code, self._fault)
