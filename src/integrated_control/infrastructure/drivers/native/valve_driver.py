from integrated_control.devices.valve import Valve
from integrated_control.domain.errors import IntegratedControlError
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.modbus_rtu import ModbusRtuClient


class ValveDriver(Valve):
    """Native Modbus valve driver migrated from ``old/valve.py``."""

    POWER_REGISTER = 0x0000

    def __init__(self, client: ModbusRtuClient, *, device_id: str = "valve") -> None:
        self._client = client
        self._device_id = device_id
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None
        self._is_open = False

    @property
    def device_id(self) -> str:
        return self._device_id

    def initialize(self) -> ActionResult:
        self._activity = "INITIALIZING"
        try:
            self._client.open()
            self._client.write_single_register(self.POWER_REGISTER, 0)
        except IntegratedControlError as exc:
            try:
                self._client.close()
            except IntegratedControlError:
                pass
            return self._failure("VALVE_INITIALIZATION_FAILED", exc)
        self._initialized = True
        self._fault = None
        self._is_open = False
        self._activity = "IDLE"
        return ActionResult.done("Native valve initialized in the closed state")

    def open(self) -> ActionResult:
        return self._set_state(True)

    def close(self) -> ActionResult:
        return self._set_state(False)

    def stop(self) -> ActionResult:
        close_error: IntegratedControlError | None = None
        if self._initialized:
            try:
                self._client.write_single_register(self.POWER_REGISTER, 0)
                self._is_open = False
            except IntegratedControlError as exc:
                close_error = exc
        try:
            self._client.close()
        except IntegratedControlError as exc:
            close_error = close_error or exc
        self._initialized = False
        if close_error is not None:
            return self._failure("VALVE_STOP_FAILED", close_error)
        self._activity = "IDLE"
        return ActionResult.done("Native valve closed and connection released")

    def get_state(self) -> DeviceState:
        lifecycle = "FAULT" if self._fault else (
            "READY" if self._initialized else "OFFLINE"
        )
        return DeviceState(
            self.device_id,
            lifecycle,
            self._activity,
            {"is_open": self._is_open, "backend": "native"},
            self._fault,
        )

    def _set_state(self, is_open: bool) -> ActionResult:
        if not self._initialized:
            return ActionResult.failed("DEVICE_NOT_READY", "Valve is not initialized")
        self._activity = "OPENING" if is_open else "CLOSING"
        try:
            self._client.write_single_register(
                self.POWER_REGISTER, 1 if is_open else 0
            )
        except IntegratedControlError as exc:
            return self._failure("VALVE_COMMAND_FAILED", exc)
        self._is_open = is_open
        self._activity = "OPEN" if is_open else "IDLE"
        return ActionResult.done(
            f"{self.device_id} {'opened' if is_open else 'closed'}",
            {"is_open": is_open},
        )

    def _failure(self, code: str, exc: Exception) -> ActionResult:
        self._fault = str(exc) or type(exc).__name__
        self._activity = "FAULT"
        return ActionResult.failed(code, self._fault)
