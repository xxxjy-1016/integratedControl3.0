from dataclasses import dataclass
from typing import cast

from integrated_control.application.calibration.homing_service import HomingService
from integrated_control.application.device_manager import DeviceManager
from integrated_control.devices.gripper import Gripper
from integrated_control.devices.pipette import Pipette
from integrated_control.devices.position_sensor import PositionSensor
from integrated_control.devices.spin_coater import SpinCoater
from integrated_control.devices.stage import Axis, Stage
from integrated_control.devices.vacuum_station import VacuumStation
from integrated_control.devices.valve import Valve
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult


@dataclass(frozen=True)
class MotionSnapshot:
    raw_x: float
    raw_y: float
    logical_x: float
    logical_y: float
    offset_x: float
    offset_y: float
    sensor_x_triggered: bool
    sensor_y_triggered: bool
    sensor_x_mv: float
    sensor_y_mv: float


class DeviceDiagnosticsController:
    """Coordinates a set of devices during attended hardware diagnostics.

    Device operations stay on their domain interfaces.  This class owns only
    cross-device concerns: lifecycle, homing and combined diagnostic state.
    """

    def __init__(
        self,
        devices: DeviceManager,
        homing: HomingService,
    ) -> None:
        self.devices = devices
        self.homing = homing
        self._initialized = False

    @property
    def stage(self) -> Stage:
        return cast(Stage, self.devices.get("stage"))

    @property
    def sensor(self) -> PositionSensor:
        return cast(PositionSensor, self.devices.get("position_sensor"))

    @property
    def gripper(self) -> Gripper:
        return cast(Gripper, self.devices.get("gripper"))

    @property
    def pipette(self) -> Pipette:
        return cast(Pipette, self.devices.get("pipette"))

    @property
    def spin_coater(self) -> SpinCoater:
        return cast(SpinCoater, self.devices.get("spin_coater"))

    @property
    def vacuum_station(self) -> VacuumStation:
        return cast(VacuumStation, self.devices.get("vacuum_station"))

    @property
    def valve(self) -> Valve:
        return cast(Valve, self.devices.get("valve"))

    def initialize(self) -> ActionResult:
        result = self.devices.initialize_all()
        self._initialized = result.success
        return result

    def shutdown(self) -> ActionResult:
        self._initialized = False
        return self.devices.stop_all()

    def device_states(self) -> dict[str, DeviceState]:
        return self.devices.states()

    def home_axis(self, axis: Axis) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        return self.homing.home_axis(axis)

    def home_xy(self) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        return self.homing.home_xy()

    def save_stage_offsets(self) -> ActionResult:
        if failure := self._ready_failure():
            return failure
        return self.stage.save_offsets()

    def snapshot(self) -> MotionSnapshot:
        if not self._initialized:
            raise RuntimeError("Device diagnostics controller is not initialized")
        raw_x = self.stage.get_raw_position("x")
        raw_y = self.stage.get_raw_position("y")
        offset_x = self.stage.get_offset("x")
        offset_y = self.stage.get_offset("y")
        return MotionSnapshot(
            raw_x=raw_x,
            raw_y=raw_y,
            logical_x=raw_x - offset_x,
            logical_y=raw_y - offset_y,
            offset_x=offset_x,
            offset_y=offset_y,
            sensor_x_triggered=self.sensor.is_triggered("x"),
            sensor_y_triggered=self.sensor.is_triggered("y"),
            sensor_x_mv=self.sensor.read_voltage("x"),
            sensor_y_mv=self.sensor.read_voltage("y"),
        )

    def _ready_failure(self) -> ActionResult | None:
        if self._initialized:
            return None
        return ActionResult.failed(
            "DEVICE_NOT_READY", "Initialize the diagnostics controller first"
        )
