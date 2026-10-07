from dataclasses import dataclass
import time

from integrated_control.devices.stage import Axis, Stage
from integrated_control.domain.errors import (
    CommunicationTimeoutError,
    IntegratedControlError,
)
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.modbus_rtu import ModbusRtuClient
from integrated_control.infrastructure.persistence.stage_state_store import (
    StageStateStore,
)


@dataclass(frozen=True)
class StageDriverConfig:
    """Store configuration values for stage driver."""
    minimum_x: float = -140.0
    maximum_x: float = 140.0
    minimum_y: float = -100.0
    maximum_y: float = 100.0
    pulses_x: int = 40000
    pulses_y: int = 80000
    speed_x: int = 700
    acceleration_x: int = 100
    deceleration_x: int = 100
    speed_y: int = 70
    acceleration_y: int = 100
    deceleration_y: int = 100
    movement_timeout_s: float = 10.0
    poll_interval_s: float = 0.05
    hardware_zero_tolerance_pulses: int = 10


def _registers_for_signed_32(value: int) -> list[int]:
    """Encode a signed 32-bit value as the controller register pair."""
    encoded = (value & 0xFFFFFFFF).to_bytes(4, "big")
    return [int.from_bytes(encoded[:2], "big"), int.from_bytes(encoded[2:], "big")]


class StageDriver(Stage):
    """Native Modbus driver migrated from old_code/leg2.py."""

    X_SLAVE = 2
    Y_SLAVE = 1

    X_STATUS = 0x2303
    X_CLEAR_POSITION = 0x2101
    POSITION_ACTUAL = 0x6064
    CONTROLWORD = 0x6040
    STATUSWORD = 0x6041
    MODE_OF_OPERATION = 0x6060
    MODE_DISPLAY = 0x6061
    HOME_OFFSET = 0x607C
    HOMING_METHOD = 0x6098

    POSITION_MODE = 1
    HOMING_MODE = 6
    HOMING_CURRENT_POSITION = 0

    def __init__(
        self,
        client: ModbusRtuClient,
        config: StageDriverConfig | None = None,
        state_store: StageStateStore | None = None,
    ) -> None:
        """Initialize stage driver dependencies and internal state."""
        self._client = client
        self._config = config or StageDriverConfig()
        self._state_store = state_store
        self._offsets = {"x": 0.0, "y": 0.0}
        self._at_origin = True if state_store is None else False
        self._last_raw: dict[Axis, float | None] = {"x": None, "y": None}
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None

    @property
    def device_id(self) -> str:
        """Return the device id exposed by this component."""
        return "stage"

    def initialize(self) -> ActionResult:
        """Initialize the stage driver and return its readiness or failure result."""
        self._activity = "INITIALIZING"
        try:
            self._load_persistent_state()
            self._client.open()
            self._initialize_x()
            self._initialize_y()
            self._configure_motion()
        except IntegratedControlError as exc:
            try:
                self._client.close()
            except IntegratedControlError:
                pass
            return self._failure("STAGE_INITIALIZATION_FAILED", exc)
        self._initialized = True
        self._fault = None
        self._activity = "IDLE"
        return ActionResult.done("Native stage initialized")

    def move_axis(
        self,
        axis: Axis,
        target: float,
        *,
        ignore_limit: bool = False,
    ) -> ActionResult:
        """Move one stage axis to the requested coordinate using its configured offset."""
        if not self._initialized:
            return ActionResult.failed("DEVICE_NOT_READY", "Stage is not initialized")
        actual_target = target + self._offsets[axis]
        return self._move_to_raw(
            axis,
            actual_target,
            logical_target=target,
            ignore_limit=ignore_limit,
        )

    def move_axis_raw(
        self,
        axis: Axis,
        target: float,
        *,
        ignore_limit: bool = False,
    ) -> ActionResult:
        """Move one stage axis to a raw coordinate without applying its configured offset."""
        return self._move_to_raw(
            axis,
            target,
            logical_target=None,
            ignore_limit=ignore_limit,
        )

    def _move_to_raw(
        self,
        axis: Axis,
        actual_target: float,
        *,
        logical_target: float | None,
        ignore_limit: bool,
    ) -> ActionResult:
        """Command raw stage movement, enforce physical limits, and wait for arrival."""
        if not self._initialized:
            return ActionResult.failed("DEVICE_NOT_READY", "Stage is not initialized")
        minimum, maximum = self._limits(axis)
        if not ignore_limit and not minimum <= actual_target <= maximum:
            return ActionResult.failed(
                "STAGE_LIMIT",
                f"{axis.upper()} target {actual_target} is outside {minimum}..{maximum}",
            )

        self._activity = "MOVING"
        try:
            self._set_persisted_origin(False)
            if axis == "x":
                pulses = int(actual_target / 100.0 * self._config.pulses_x)
                self._client.write_multiple_registers(
                    0x2320,
                    _registers_for_signed_32(pulses),
                    slave_id=self.X_SLAVE,
                )
                self._client.write_single_register(0x2316, 0, slave_id=self.X_SLAVE)
                self._client.write_single_register(0x2316, 1, slave_id=self.X_SLAVE)
            else:
                pulses = int(actual_target / 100.0 * self._config.pulses_y)
                self._client.write_multiple_registers(
                    0x607A,
                    _registers_for_signed_32(pulses),
                    slave_id=self.Y_SLAVE,
                )
                self._client.write_single_register(0x6040, 0x009F, slave_id=self.Y_SLAVE)
                self._client.write_single_register(0x6040, 0x008F, slave_id=self.Y_SLAVE)
            self._wait_until_arrived(axis)
            raw_position = self.get_raw_position(axis)
        except IntegratedControlError as exc:
            return self._failure("STAGE_MOVE_FAILED", exc)

        self._activity = "IDLE"
        if logical_target is not None:
            try:
                self._update_origin_from_actual_positions()
            except IntegratedControlError as exc:
                return self._failure("STAGE_POSITION_STATE_UPDATE_FAILED", exc)
        return ActionResult.done(
            f"{axis.upper()} movement completed",
            {
                f"logical_{axis}": (
                    logical_target
                    if logical_target is not None
                    else raw_position - self._offsets[axis]
                ),
                f"raw_{axis}": raw_position,
            },
        )

    def get_raw_position(self, axis: Axis) -> float:
        """Return the selected stage axis position before applying its coordinate offset."""
        slave = self.X_SLAVE if axis == "x" else self.Y_SLAVE
        pulses_per_travel = (
            self._config.pulses_x if axis == "x" else self._config.pulses_y
        )
        pulses = self._read_position_pulses(slave)
        position = pulses / pulses_per_travel * 100.0
        self._last_raw[axis] = position
        return position

    def get_offset(self, axis: Axis) -> float:
        """Return the coordinate offset currently assigned to the selected stage axis."""
        return self._offsets[axis]

    def set_offset(self, axis: Axis, value: float) -> None:
        """Update the coordinate offset assigned to the selected stage axis."""
        self._offsets[axis] = float(value)

    def needs_startup_homing(self) -> bool:
        """Return whether startup homing is required."""
        return not self._at_origin

    def reload_saved_offsets(self) -> ActionResult:
        """Restore stage offsets from the persisted calibration state."""
        try:
            self._load_persistent_state(preserve_origin=True)
        except IntegratedControlError as exc:
            return self._failure("STAGE_OFFSET_RELOAD_FAILED", exc)
        return ActionResult.done(
            "Saved stage offsets reloaded",
            {"offset_x": self._offsets["x"], "offset_y": self._offsets["y"]},
        )

    def save_offsets(self) -> ActionResult:
        """Persist the current axis offsets and stage-origin metadata."""
        if self._state_store is None:
            return super().save_offsets()
        try:
            state = self._state_store.save_offsets(
                self._offsets["x"], self._offsets["y"]
            )
        except IntegratedControlError as exc:
            return self._failure("STAGE_OFFSET_SAVE_FAILED", exc)
        return ActionResult.done(
            "Stage offsets saved",
            {"offset_x": state.offset_x, "offset_y": state.offset_y},
        )

    def mark_at_origin(self, value: bool) -> ActionResult:
        """Update the saved stage-origin flag for startup homing decisions."""
        try:
            self._set_persisted_origin(value)
        except IntegratedControlError as exc:
            return self._failure("STAGE_ORIGIN_STATE_SAVE_FAILED", exc)
        return ActionResult.done(
            "Stage origin state saved", {"stage_at_origin": self._at_origin}
        )

    def set_current_position_as_zero(self, axis: Axis) -> ActionResult:
        """Establish the selected axis current physical position as its hardware zero."""
        if not self._initialized:
            return ActionResult.failed("DEVICE_NOT_READY", "Stage is not initialized")
        self._activity = "HARDWARE_ZEROING"
        try:
            self._set_persisted_origin(False)
            if axis == "x":
                pulses, details = self._clear_x_position()
            else:
                pulses, details = self._clear_y_position()
        except IntegratedControlError as exc:
            return self._failure(f"STAGE_{axis.upper()}_HARDWARE_ZERO_FAILED", exc)

        if abs(pulses) > self._config.hardware_zero_tolerance_pulses:
            return self._failure(
                f"STAGE_{axis.upper()}_HARDWARE_ZERO_FAILED",
                RuntimeError(
                    f"{axis.upper()} position remained at {pulses} pulses after zeroing"
                ),
            )
        self._last_raw[axis] = self._pulses_to_position(axis, pulses)
        self._fault = None
        self._activity = "IDLE"
        return ActionResult.done(
            f"{axis.upper()} drive position cleared",
            {"axis": axis, "position_pulses": pulses, **details},
        )

    def stop(self) -> ActionResult:
        """Request stage driver shutdown and report the implementation result; physical stop support depends on the driver."""
        try:
            self._client.close()
        except IntegratedControlError as exc:
            return self._failure("STAGE_CLOSE_FAILED", exc)
        self._initialized = False
        self._activity = "IDLE"
        return ActionResult.done(
            "Native stage connection closed; no undocumented motion-stop command was sent"
        )

    def get_state(self) -> DeviceState:
        """Return the device lifecycle, activity, measurements, and any reported fault."""
        lifecycle = "FAULT" if self._fault else (
            "READY" if self._initialized else "OFFLINE"
        )
        return DeviceState(
            self.device_id,
            lifecycle,
            self._activity,
            {
                "raw_x": self._last_raw["x"],
                "raw_y": self._last_raw["y"],
                "offset_x": self._offsets["x"],
                "offset_y": self._offsets["y"],
                "position_unit": "percent_of_travel",
                "backend": "native",
                "stage_at_origin": self._at_origin,
            },
            self._fault,
        )

    def _initialize_x(self) -> None:
        """Configure and enable the native X-axis controller."""
        self._client.write_single_register(0x2109, 1, slave_id=self.X_SLAVE)
        self._client.write_single_register(0x2311, 1, slave_id=self.X_SLAVE)
        self._client.write_single_register(0x2310, 3, slave_id=self.X_SLAVE)

    def _initialize_y(self) -> None:
        """Configure and enable the native Y-axis controller."""
        for value in (0x0006, 0x0007, 0x000F):
            self._client.write_single_register(0x6040, value, slave_id=self.Y_SLAVE)
        self._client.write_single_register(0x6060, 1, slave_id=self.Y_SLAVE)

    def _configure_motion(self) -> None:
        """Write axis motion parameters from the configured speed and ramp settings."""
        self._client.write_single_register(
            0x2321, self._config.speed_x, slave_id=self.X_SLAVE
        )
        self._client.write_single_register(
            0x2322, self._config.acceleration_x, slave_id=self.X_SLAVE
        )
        self._client.write_single_register(
            0x2323, self._config.deceleration_x, slave_id=self.X_SLAVE
        )
        self._client.write_multiple_registers(
            0x6081,
            _registers_for_signed_32(self._config.speed_y),
            slave_id=self.Y_SLAVE,
        )
        self._client.write_single_register(
            0x6083, self._config.acceleration_y, slave_id=self.Y_SLAVE
        )
        self._client.write_single_register(
            0x6084, self._config.deceleration_y, slave_id=self.Y_SLAVE
        )

    def _wait_until_arrived(self, axis: Axis) -> None:
        """Poll axis feedback until motion completes or the configured timeout expires."""
        deadline = time.monotonic() + self._config.movement_timeout_s
        while time.monotonic() < deadline:
            if axis == "x":
                arrived = self._client.read_holding_registers(
                    self.X_STATUS, 1, slave_id=self.X_SLAVE
                )[0] & (1 << 6) != 0
            else:
                status = self._client.read_holding_registers(
                    self.STATUSWORD, 1, slave_id=self.Y_SLAVE
                )[0]
                arrived = bool(status & (1 << 10))
            if arrived:
                return
            time.sleep(self._config.poll_interval_s)
        raise CommunicationTimeoutError(f"{axis.upper()} stage movement timed out")

    def _clear_x_position(self) -> tuple[int, dict[str, int]]:
        """Clear the X position using its hardware position-reset register."""
        status = self._client.read_holding_registers(
            self.X_STATUS, 1, slave_id=self.X_SLAVE
        )[0]
        if status & 1:
            raise CommunicationTimeoutError(
                "X axis must be stopped before clearing its position"
            )
        self._client.write_single_register(
            self.X_CLEAR_POSITION, 1, slave_id=self.X_SLAVE
        )
        pulses = self._read_position_pulses(self.X_SLAVE)
        return pulses, {"statusword": status}

    def _clear_y_position(self) -> tuple[int, dict[str, int]]:
        """Clear the Y position using its controller homing-mode sequence."""
        self._client.write_single_register(
            self.MODE_OF_OPERATION, self.HOMING_MODE, slave_id=self.Y_SLAVE
        )
        mode_display = self._client.read_holding_registers(
            self.MODE_DISPLAY, 1, slave_id=self.Y_SLAVE
        )[0] & 0xFF
        if mode_display != self.HOMING_MODE:
            self._client.write_single_register(
                self.MODE_OF_OPERATION, self.POSITION_MODE, slave_id=self.Y_SLAVE
            )
            raise CommunicationTimeoutError(
                f"Y drive did not enter homing mode; mode display is {mode_display}"
            )

        status = 0
        try:
            self._client.write_multiple_registers(
                self.HOME_OFFSET, [0, 0], slave_id=self.Y_SLAVE
            )
            self._client.write_single_register(
                self.HOMING_METHOD,
                self.HOMING_CURRENT_POSITION,
                slave_id=self.Y_SLAVE,
            )
            self._client.write_single_register(
                self.CONTROLWORD, 0x000F, slave_id=self.Y_SLAVE
            )
            self._client.write_single_register(
                self.CONTROLWORD, 0x001F, slave_id=self.Y_SLAVE
            )
            deadline = time.monotonic() + self._config.movement_timeout_s
            while time.monotonic() < deadline:
                status = self._client.read_holding_registers(
                    self.STATUSWORD, 1, slave_id=self.Y_SLAVE
                )[0]
                if status & (1 << 13):
                    raise CommunicationTimeoutError(
                        f"Y drive reported a homing error; statusword=0x{status:04X}"
                    )
                if status & (1 << 12):
                    break
                time.sleep(self._config.poll_interval_s)
            else:
                raise CommunicationTimeoutError(
                    f"Y hardware zero timed out; statusword=0x{status:04X}"
                )
        finally:
            self._client.write_single_register(
                self.CONTROLWORD, 0x000F, slave_id=self.Y_SLAVE
            )
            self._client.write_single_register(
                self.MODE_OF_OPERATION, self.POSITION_MODE, slave_id=self.Y_SLAVE
            )

        pulses = self._read_position_pulses(self.Y_SLAVE)
        return pulses, {"mode_display": mode_display, "statusword": status}

    def _read_position_pulses(self, slave: int) -> int:
        """Read the selected axis raw position as signed controller pulses."""
        raw = self._client.read_data_bytes(
            self.POSITION_ACTUAL, 2, slave_id=slave
        )
        return int.from_bytes(raw, "big", signed=True)

    def _pulses_to_position(self, axis: Axis, pulses: int) -> float:
        """Convert signed controller pulses to the configured axis coordinate units."""
        pulses_per_travel = (
            self._config.pulses_x if axis == "x" else self._config.pulses_y
        )
        return pulses / pulses_per_travel * 100.0

    def _load_persistent_state(self, *, preserve_origin: bool = False) -> None:
        """Load saved stage offsets and origin metadata into the driver."""
        if self._state_store is None:
            return
        state = self._state_store.load()
        self._offsets["x"] = state.offset_x
        self._offsets["y"] = state.offset_y
        if not preserve_origin:
            self._at_origin = state.stage_at_origin

    def _set_persisted_origin(self, value: bool) -> None:
        """Update and save the stage-origin flag without changing axis offsets."""
        if self._state_store is not None:
            self._state_store.save_origin(value)
        self._at_origin = bool(value)

    def _update_origin_from_actual_positions(self) -> None:
        # Refresh both axes so the persisted flag always describes current
        # hardware feedback rather than an earlier cached position.
        """Reconcile the origin flag with the current physical axis positions."""
        self.get_raw_position("x")
        self.get_raw_position("y")
        tolerance = {
            "x": (
                self._config.hardware_zero_tolerance_pulses
                / self._config.pulses_x
                * 100.0
            ),
            "y": (
                self._config.hardware_zero_tolerance_pulses
                / self._config.pulses_y
                * 100.0
            ),
        }
        at_origin = all(
            abs(float(self._last_raw[axis]) - self._offsets[axis])
            <= tolerance[axis]
            for axis in ("x", "y")
        )
        self._set_persisted_origin(at_origin)

    def _limits(self, axis: Axis) -> tuple[float, float]:
        """Return the configured lower and upper travel limits for the selected axis."""
        if axis == "x":
            return self._config.minimum_x, self._config.maximum_x
        return self._config.minimum_y, self._config.maximum_y

    def _failure(self, code: str, exc: Exception) -> ActionResult:
        """Record the driver fault and return a failed ActionResult with its error code."""
        self._fault = str(exc) or type(exc).__name__
        self._activity = "FAULT"
        return ActionResult.failed(code, self._fault)
