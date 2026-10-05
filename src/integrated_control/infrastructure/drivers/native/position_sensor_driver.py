from integrated_control.devices.position_sensor import PositionSensor
from integrated_control.devices.stage import Axis
from integrated_control.domain.errors import IntegratedControlError
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.modbus_rtu import ModbusRtuClient


class PositionSensorDriver(PositionSensor):
    """Native Modbus driver migrated from old/positionSensor.py."""

    RANGE_500_MV = 0x000B

    def __init__(self, client: ModbusRtuClient) -> None:
        self._client = client
        self._initialized = False
        self._fault: str | None = None
        self._last_voltage = {"x": None, "y": None}

    @property
    def device_id(self) -> str:
        return "position_sensor"

    def initialize(self) -> ActionResult:
        try:
            self._client.open()
            self._set_range(0)
            self._set_range(1)
        except IntegratedControlError as exc:
            try:
                self._client.close()
            except IntegratedControlError:
                pass
            self._fault = str(exc) or type(exc).__name__
            return ActionResult.failed("POSITION_SENSOR_INITIALIZATION_FAILED", self._fault)
        self._initialized = True
        self._fault = None
        return ActionResult.done("Native position sensor initialized")

    def is_triggered(self, axis: Axis) -> bool:
        return self.read_voltage(axis) > 0.0

    def read_voltage(self, axis: Axis) -> float:
        if not self._initialized:
            raise RuntimeError("Position sensor is not initialized")
        channel = 0 if axis == "x" else 1
        try:
            self._set_range(channel)
            raw = self._client.read_holding_registers(channel, 1)[0]
        except IntegratedControlError as exc:
            self._fault = str(exc) or type(exc).__name__
            raise
        voltage_mv = raw / 65535.0 * 1000.0 - 500.0
        self._last_voltage[axis] = voltage_mv
        return voltage_mv

    def stop(self) -> ActionResult:
        try:
            self._client.close()
        except IntegratedControlError as exc:
            self._fault = str(exc) or type(exc).__name__
            return ActionResult.failed("POSITION_SENSOR_CLOSE_FAILED", self._fault)
        self._initialized = False
        return ActionResult.done("Native position sensor connection closed")

    def get_state(self) -> DeviceState:
        lifecycle = "FAULT" if self._fault else (
            "READY" if self._initialized else "OFFLINE"
        )
        return DeviceState(
            self.device_id,
            lifecycle,
            "IDLE" if self._fault is None else "FAULT",
            {
                "x_voltage_mv": self._last_voltage["x"],
                "y_voltage_mv": self._last_voltage["y"],
                "backend": "native",
            },
            self._fault,
        )

    def _set_range(self, channel: int) -> None:
        self._client.write_single_register(200 + channel, self.RANGE_500_MV)
