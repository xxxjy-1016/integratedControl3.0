from collections.abc import Sequence
from typing import Any

from integrated_control.devices import (
    Axis,
    Camera,
    Device,
    Gripper,
    Heater,
    Pipette,
    PositionSensor,
    SpinCoater,
    Stage,
    VacuumStation,
    Valve,
)
from integrated_control.domain.models import DeviceState, Pose2D, SpinStep
from integrated_control.domain.results import ActionResult


class SimulatedDevice(Device):
    """Provide shared readiness, fault injection, and state reporting for simulated devices."""
    def __init__(self, device_id: str) -> None:
        """Initialize simulated device dependencies and internal state."""
        self._device_id = device_id
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None

    @property
    def device_id(self) -> str:
        """Return the device id exposed by this component."""
        return self._device_id

    def initialize(self) -> ActionResult:
        """Initialize the simulated device and return its readiness or failure result."""
        self._initialized = True
        self._activity = "IDLE"
        self._fault = None
        return ActionResult.done(f"{self.device_id} initialized")

    def stop(self) -> ActionResult:
        """Request simulated device shutdown and report the implementation result; physical stop support depends on the driver."""
        self._activity = "IDLE"
        self._initialized = False
        return ActionResult.done(f"{self.device_id} stopped")

    def inject_fault(self, message: str) -> None:
        """Inject a simulated device fault for failure-path testing."""
        self._fault = message
        self._activity = "FAULT"

    def clear_fault(self) -> ActionResult:
        """Clear the injected simulation fault and restore its normal state."""
        self._fault = None
        self._activity = "IDLE"
        return ActionResult.done(f"{self.device_id} fault cleared")

    def _ready_failure(self) -> ActionResult | None:
        """Return a not-ready or fault result when the component cannot accept an operation."""
        if self._fault is not None:
            return ActionResult.failed("DEVICE_FAULT", f"{self.device_id}: {self._fault}")
        if not self._initialized:
            return ActionResult.failed(
                "DEVICE_NOT_READY", f"{self.device_id} is not initialized"
            )
        return None

    def get_state(self) -> DeviceState:
        """Return the device lifecycle, activity, measurements, and any reported fault."""
        lifecycle = "FAULT" if self._fault else (
            "READY" if self._initialized else "OFFLINE"
        )
        return DeviceState(
            self.device_id,
            lifecycle,
            self._activity,
            self._measurements(),
            self._fault,
        )

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {}


class SimulatedStage(SimulatedDevice, Stage):
    """Provide an in-memory stage implementation for simulation."""
    def __init__(
        self,
        *,
        initial_x: float = 5.0,
        initial_y: float = 8.0,
        minimum: float = -140.0,
        maximum: float = 140.0,
    ) -> None:
        """Initialize simulated stage dependencies and internal state."""
        super().__init__("stage")
        self._positions = {"x": initial_x, "y": initial_y}
        self._offsets = {"x": 0.0, "y": 0.0}
        self._minimum = minimum
        self._maximum = maximum

    def move_axis(
        self, axis: Axis, target: float, *, ignore_limit: bool = False
    ) -> ActionResult:
        """Move one stage axis to the requested coordinate using its configured offset."""
        if failure := self._ready_failure():
            return failure
        if not ignore_limit and not self._minimum <= target <= self._maximum:
            return ActionResult.failed(
                "STAGE_LIMIT",
                f"{axis.upper()} target {target} is outside "
                f"{self._minimum}..{self._maximum}",
            )
        self._activity = "MOVING"
        raw_target = target + self._offsets[axis]
        self._positions[axis] = raw_target
        self._activity = "IDLE"
        return ActionResult.done(
            f"{axis.upper()} movement completed",
            {f"logical_{axis}": target, f"raw_{axis}": raw_target},
        )

    def get_raw_position(self, axis: Axis) -> float:
        """Return the selected stage axis position before applying its coordinate offset."""
        return self._positions[axis]

    def get_offset(self, axis: Axis) -> float:
        """Return the coordinate offset currently assigned to the selected stage axis."""
        return self._offsets[axis]

    def set_offset(self, axis: Axis, value: float) -> None:
        """Update the coordinate offset assigned to the selected stage axis."""
        self._offsets[axis] = value

    def set_current_position_as_zero(self, axis: Axis) -> ActionResult:
        """Establish the selected axis current physical position as its hardware zero."""
        self._positions[axis] = 0.0
        return ActionResult.done(
            f"{axis.upper()} simulated hardware position cleared",
            {f"raw_{axis}": 0.0},
        )

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "raw_x": self._positions["x"],
            "raw_y": self._positions["y"],
            "logical_x": self._positions["x"] - self._offsets["x"],
            "logical_y": self._positions["y"] - self._offsets["y"],
            "offset_x": self._offsets["x"],
            "offset_y": self._offsets["y"],
        }


class SimulatedPositionSensor(SimulatedDevice, PositionSensor):
    """Provide an in-memory position sensor implementation for simulation."""
    def __init__(
        self,
        stage: SimulatedStage,
        *,
        trigger_x: float = 0.0,
        trigger_y: float = 0.0,
    ) -> None:
        """Initialize simulated position sensor dependencies and internal state."""
        super().__init__("position_sensor")
        self._stage = stage
        self._triggers = {"x": trigger_x, "y": trigger_y}

    def is_triggered(self, axis: Axis) -> bool:
        """Return whether the selected position sensor reports an active trigger."""
        return self._stage.get_raw_position(axis) <= self._triggers[axis]

    def read_voltage(self, axis: Axis) -> float:
        """Read the voltage reported by the selected position sensor channel."""
        return 100.0 if self.is_triggered(axis) else -100.0

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "x_triggered": self.is_triggered("x"),
            "y_triggered": self.is_triggered("y"),
            "x_voltage_mv": self.read_voltage("x"),
            "y_voltage_mv": self.read_voltage("y"),
        }


class SimulatedGripper(SimulatedDevice, Gripper):
    """Provide an in-memory gripper implementation for simulation."""
    def __init__(self, *, max_z: float = 100.0) -> None:
        """Initialize simulated gripper dependencies and internal state."""
        super().__init__("gripper")
        self._max_z = max_z
        self._z = 0.0
        self._opening = 100.0
        self._rotation = 0.0
        self._force = 0.0
        self._holding = False

    def move_z(self, height: float) -> ActionResult:
        """Move the vertical axis to the requested position and report the operation result."""
        if failure := self._ready_failure():
            return failure
        if not 0.0 <= height <= self._max_z:
            return ActionResult.failed("GRIPPER_Z_LIMIT", "Invalid gripper Z target")
        self._z = height
        return ActionResult.done("Gripper Z movement completed", {"z": height})

    def set_opening(self, opening: float) -> ActionResult:
        """Set the gripper opening position using the supplied motion and torque settings."""
        if failure := self._ready_failure():
            return failure
        if not 0.0 <= opening <= 100.0:
            return ActionResult.failed("GRIPPER_OPENING_LIMIT", "Invalid opening")
        self._opening = opening
        self._holding = opening < 100.0
        self._activity = "HOLDING" if self._holding else "IDLE"
        return ActionResult.done("Gripper opening set", {"opening": opening})

    def open(self) -> ActionResult:
        """Open the gripper using its configured opening or clamping settings."""
        self._force = 0.0
        return self.set_opening(100.0)

    def close(self, force: float = 50.0) -> ActionResult:
        """Close the gripper using its configured opening or clamping settings."""
        if not 0.0 <= force <= 100.0:
            return ActionResult.failed("GRIPPER_FORCE_LIMIT", "Invalid force")
        self._force = force
        return self.set_opening(30.0)

    def rotate(self, angle: float) -> ActionResult:
        """Rotate the gripper by the requested angle and report completion or failure."""
        if failure := self._ready_failure():
            return failure
        target = round(angle)
        if not -32768 <= target <= 32767:
            return ActionResult.failed(
                "GRIPPER_ROTATION_LIMIT", "Rotation must fit a signed 16-bit value"
            )
        self._rotation = float(target)
        return ActionResult.done("Gripper rotation completed", {"angle": self._rotation})

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "z": self._z,
            "opening": self._opening,
            "rotation_deg": self._rotation,
            "force_percent": self._force,
            "holding_object": self._holding,
        }


class SimulatedPipette(SimulatedDevice, Pipette):
    """Provide an in-memory pipette implementation for simulation."""
    def __init__(self, *, capacity_ul: float = 1000.0, max_z: float = 100.0) -> None:
        """Initialize simulated pipette dependencies and internal state."""
        super().__init__("pipette")
        self._capacity_ul = capacity_ul
        self._max_z = max_z
        self._z = 0.0
        self._tip_id: str | None = None
        self._liquid_ul = 0.0

    def move_z(self, height: float) -> ActionResult:
        """Move the vertical axis to the requested position and report the operation result."""
        if failure := self._ready_failure():
            return failure
        if not 0.0 <= height <= self._max_z:
            return ActionResult.failed("PIPETTE_Z_LIMIT", "Invalid pipette Z target")
        self._z = height
        return ActionResult.done("Pipette Z movement completed", {"z": height})

    def attach_tip(self, tip_id: str) -> ActionResult:
        """Record attachment of the selected pipette tip after checking device readiness."""
        if failure := self._ready_failure():
            return failure
        if self._tip_id is not None:
            return ActionResult.failed("TIP_ALREADY_ATTACHED", "A tip is already attached")
        self._tip_id = tip_id
        return ActionResult.done("Pipette tip attached", {"tip_id": tip_id})

    def eject_tip(self) -> ActionResult:
        """Eject or clear the attached pipette tip and update its tracked state."""
        if failure := self._ready_failure():
            return failure
        old_tip = self._tip_id
        self._tip_id = None
        self._liquid_ul = 0.0
        return ActionResult.done("Pipette tip ejected", {"tip_id": old_tip})

    def aspirate(
        self,
        volume_ul: float,
        *,
        require_liquid_detection: bool = True,
    ) -> ActionResult:
        """Aspirate the requested volume using the supplied pipetting settings."""
        if failure := self._ready_failure():
            return failure
        if self._tip_id is None:
            return ActionResult.failed("TIP_REQUIRED", "Attach a tip before aspiration")
        if volume_ul <= 0 or self._liquid_ul + volume_ul > self._capacity_ul:
            return ActionResult.failed("PIPETTE_CAPACITY", "Requested volume is invalid")
        self._liquid_ul += volume_ul
        return ActionResult.done(
            "Aspiration completed",
            {"liquid_ul": self._liquid_ul, "liquid_detected": True},
        )

    def dispense(self, volume_ul: float | None = None) -> ActionResult:
        """Dispense the requested volume using the supplied pipetting settings."""
        if failure := self._ready_failure():
            return failure
        if self._tip_id is None:
            return ActionResult.failed("TIP_REQUIRED", "Attach a tip before dispensing")
        requested = self._liquid_ul if volume_ul is None else volume_ul
        if requested <= 0 or requested > self._liquid_ul:
            return ActionResult.failed("INSUFFICIENT_LIQUID", "Volume is unavailable")
        self._liquid_ul -= requested
        return ActionResult.done(
            "Dispense completed",
            {"dispensed_ul": requested, "remaining_ul": self._liquid_ul},
        )

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "z": self._z,
            "tip_id": self._tip_id,
            "liquid_ul": self._liquid_ul,
            "capacity_ul": self._capacity_ul,
        }


class SimulatedSpinCoater(SimulatedDevice, SpinCoater):
    """Provide an in-memory spin coater implementation for simulation."""
    def __init__(self, *, max_rpm: int = 10000) -> None:
        """Initialize simulated spin coater dependencies and internal state."""
        super().__init__("spin_coater")
        self._max_rpm = max_rpm
        self._rpm = 0
        self._angle = 0.0
        self._last_recipe: list[SpinStep] = []

    def home(self) -> ActionResult:
        """Move the device to its configured home position and report completion."""
        if failure := self._ready_failure():
            return failure
        self._angle = 0.0
        self._rpm = 0
        return ActionResult.done("Spin coater homed", {"angle": 0.0})

    def run(self, recipe: Sequence[SpinStep]) -> ActionResult:
        """Execute the supplied spin recipe and report completion or failure."""
        if failure := self._ready_failure():
            return failure
        if not recipe:
            return ActionResult.failed("EMPTY_RECIPE", "Spin recipe is empty")
        if any(
            step.rpm < 0 or step.rpm > self._max_rpm or step.duration_s <= 0
            for step in recipe
        ):
            return ActionResult.failed("INVALID_SPIN_STEP", "Spin step is invalid")
        self._last_recipe = list(recipe)
        for step in recipe:
            self._rpm = step.rpm
            self._angle = (self._angle + step.rpm * 6.0 * step.duration_s) % 360.0
        self._rpm = 0
        return ActionResult.done(
            "Spin recipe completed",
            {"steps": len(recipe), "final_angle": self._angle},
        )

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "rpm": self._rpm,
            "angle_deg": self._angle,
            "last_recipe_steps": len(self._last_recipe),
            "max_rpm": self._max_rpm,
        }


class SimulatedHeater(SimulatedDevice, Heater):
    """Provide an in-memory heater implementation for simulation."""
    def __init__(self, *, slots: int = 8, maximum_temperature_c: float = 200.0) -> None:
        """Initialize simulated heater dependencies and internal state."""
        super().__init__("heater")
        self._slots = {index: None for index in range(1, slots + 1)}
        self._temperature_c = 25.0
        self._setpoint_c = 25.0
        self._maximum_temperature_c = maximum_temperature_c

    def set_temperature(self, temperature_c: float) -> ActionResult:
        """Set the requested heater temperature and report the operation result."""
        if failure := self._ready_failure():
            return failure
        if not 0.0 <= temperature_c <= self._maximum_temperature_c:
            return ActionResult.failed("HEATER_TEMPERATURE_LIMIT", "Invalid temperature")
        self._setpoint_c = temperature_c
        self._temperature_c = temperature_c
        return ActionResult.done("Heater reached setpoint", {"temperature_c": temperature_c})

    def place(self, slot: int, sample_id: str) -> ActionResult:
        """Record the specified sample as occupying the selected heater slot."""
        if failure := self._ready_failure():
            return failure
        if slot not in self._slots:
            return ActionResult.failed("INVALID_HEATER_SLOT", "Unknown heater slot")
        if self._slots[slot] is not None:
            return ActionResult.failed("HEATER_SLOT_OCCUPIED", "Heater slot is occupied")
        self._slots[slot] = sample_id
        return ActionResult.done("Sample placed on heater", {"slot": slot})

    def remove(self, slot: int) -> ActionResult:
        """Remove the occupancy record from the selected heater slot."""
        if failure := self._ready_failure():
            return failure
        if slot not in self._slots or self._slots[slot] is None:
            return ActionResult.failed("HEATER_SLOT_EMPTY", "Heater slot is empty")
        sample_id = self._slots[slot]
        self._slots[slot] = None
        return ActionResult.done("Sample removed from heater", {"sample_id": sample_id})

    def stop(self) -> ActionResult:
        """Request simulated heater shutdown and report the implementation result; physical stop support depends on the driver."""
        self._setpoint_c = 25.0
        self._temperature_c = 25.0
        return super().stop()

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "setpoint_c": self._setpoint_c,
            "temperature_c": self._temperature_c,
            "slots": dict(self._slots),
        }


class SimulatedVacuumStation(SimulatedDevice, VacuumStation):
    """Provide an in-memory vacuum station implementation for simulation."""
    def __init__(self) -> None:
        """Initialize simulated vacuum station dependencies and internal state."""
        super().__init__("vacuum_station")
        self._cover_open = True
        self._pressure_kpa = 101.3

    def open_cover(self) -> ActionResult:
        """Move the vacuum station lid to its configured open position."""
        if failure := self._ready_failure():
            return failure
        if self._pressure_kpa < 95.0:
            return ActionResult.failed("CHAMBER_UNDER_VACUUM", "Vent before opening")
        self._cover_open = True
        return ActionResult.done("Chamber cover opened")

    def close_cover(self) -> ActionResult:
        """Move the vacuum station lid to its configured closed position."""
        if failure := self._ready_failure():
            return failure
        self._cover_open = False
        return ActionResult.done("Chamber cover closed")

    def evacuate(self, target_pressure_kpa: float) -> ActionResult:
        """Request evacuation to the target pressure through the device implementation."""
        if failure := self._ready_failure():
            return failure
        if self._cover_open:
            return ActionResult.failed("COVER_OPEN", "Close the cover before evacuation")
        if not 0.0 <= target_pressure_kpa < self._pressure_kpa:
            return ActionResult.failed("INVALID_PRESSURE", "Invalid target pressure")
        self._pressure_kpa = target_pressure_kpa
        return ActionResult.done("Evacuation completed", {"pressure_kpa": target_pressure_kpa})

    def vent(self) -> ActionResult:
        """Request venting of the vacuum station through the device implementation."""
        if failure := self._ready_failure():
            return failure
        self._pressure_kpa = 101.3
        return ActionResult.done("Chamber vented", {"pressure_kpa": 101.3})

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {"cover_open": self._cover_open, "pressure_kpa": self._pressure_kpa}


class SimulatedValve(SimulatedDevice, Valve):
    """Provide an in-memory valve implementation for simulation."""
    def __init__(self, device_id: str = "valve") -> None:
        """Initialize simulated valve dependencies and internal state."""
        super().__init__(device_id)
        self._is_open = False

    def open(self) -> ActionResult:
        """Open the solenoid valve and report the resulting state."""
        if failure := self._ready_failure():
            return failure
        self._is_open = True
        return ActionResult.done(f"{self.device_id} opened", {"is_open": True})

    def close(self) -> ActionResult:
        """Close the solenoid valve and report the resulting state."""
        if failure := self._ready_failure():
            return failure
        self._is_open = False
        return ActionResult.done(f"{self.device_id} closed", {"is_open": False})

    def stop(self) -> ActionResult:
        """Request simulated valve shutdown and report the implementation result; physical stop support depends on the driver."""
        self._is_open = False
        return super().stop()

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {"is_open": self._is_open}


class SimulatedCamera(SimulatedDevice, Camera):
    """Provide an in-memory camera implementation for simulation."""
    def __init__(self, detections: dict[tuple[str, str], Pose2D] | None = None) -> None:
        """Initialize simulated camera dependencies and internal state."""
        super().__init__("camera")
        self._detections = detections or {}
        self._frame_id = 0
        self._last_station: str | None = None

    def capture(self, station: str) -> ActionResult:
        """Capture an image and return the camera implementation result."""
        if failure := self._ready_failure():
            return failure
        self._frame_id += 1
        self._last_station = station
        return ActionResult.done(
            "Image captured", {"station": station, "frame_id": self._frame_id}
        )

    def locate(self, station: str, target: str) -> ActionResult:
        """Locate the requested target through the camera implementation."""
        capture_result = self.capture(station)
        if not capture_result.success:
            return capture_result
        pose = self._detections.get((station, target))
        if pose is None:
            return ActionResult.failed("TARGET_NOT_FOUND", "Vision target not found")
        return ActionResult.done(
            "Vision target located",
            {
                "station": station,
                "target": target,
                "x": pose.x,
                "y": pose.y,
                "theta": pose.theta,
                "confidence": 1.0,
            },
        )

    def _measurements(self) -> dict[str, Any]:
        """Return this simulated device current measurement and tracking fields."""
        return {
            "frame_id": self._frame_id,
            "last_station": self._last_station,
            "configured_targets": len(self._detections),
        }
