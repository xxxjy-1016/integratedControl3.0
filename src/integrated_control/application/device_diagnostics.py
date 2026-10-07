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
    """Collect stage positions, offsets, sensor readings, and system readiness for diagnostics."""
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
    cross-device concerns: lifecycle, homing and combined diagnostic state."""

    def __init__(
        self,
        devices: DeviceManager,
        homing: HomingService,
    ) -> None:
        """Initialize device diagnostics controller dependencies and internal state."""
        self.devices = devices
        self.homing = homing
        self._initialized = False

    @property
    def stage(self) -> Stage:
        """Return the stage exposed by this component."""
        return cast(Stage, self.devices.get("stage"))

    @property
    def sensor(self) -> PositionSensor:
        """Return the sensor exposed by this component."""
        return cast(PositionSensor, self.devices.get("position_sensor"))

    @property
    def gripper(self) -> Gripper:
        """Return the gripper exposed by this component."""
        return cast(Gripper, self.devices.get("gripper"))

    @property
    def pipette(self) -> Pipette:
        """Return the pipette exposed by this component."""
        return cast(Pipette, self.devices.get("pipette"))

    @property
    def spin_coater(self) -> SpinCoater:
        """Return the spin coater exposed by this component."""
        return cast(SpinCoater, self.devices.get("spin_coater"))

    @property
    def vacuum_station(self) -> VacuumStation:
        """Return the vacuum station exposed by this component."""
        return cast(VacuumStation, self.devices.get("vacuum_station"))

    @property
    def valve(self) -> Valve:
        """Return the valve exposed by this component."""
        return cast(Valve, self.devices.get("valve"))

    def initialize(self) -> ActionResult:
        """Initialize the device diagnostics controller and return its readiness or failure result."""
        result = self.devices.initialize_all()
        self._initialized = result.success
        return result

    def shutdown(self) -> ActionResult:
        """Shut down managed devices and publish the resulting system state."""
        self._initialized = False
        return self.devices.stop_all()

    def device_states(self) -> dict[str, DeviceState]:
        """Return current state snapshots for all registered devices."""
        return self.devices.states()

    def home_axis(self, axis: Axis) -> ActionResult:
        """Home the selected stage axis through the sensor-based homing service."""
        if failure := self._ready_failure():
            return failure
        return self.homing.home_axis(axis)

    def home_xy(self) -> ActionResult:
        """Home both stage axes and return the combined operation result."""
        if failure := self._ready_failure():
            return failure
        return self.homing.home_xy()

    def save_stage_offsets(self) -> ActionResult:
        """Persist the current stage offsets and origin metadata."""
        if failure := self._ready_failure():
            return failure
        return self.stage.save_offsets()

    def snapshot(self) -> MotionSnapshot:
        """Return the current device diagnostics controller state snapshot."""
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
        """Return a not-ready or fault result when the component cannot accept an operation."""
        if self._initialized:
            return None
        return ActionResult.failed(
            "DEVICE_NOT_READY", "Initialize the diagnostics controller first"
        )
