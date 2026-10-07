from collections.abc import Sequence
from dataclasses import dataclass
import math
import time
from typing import Callable

from integrated_control.devices.spin_coater import SpinCoater
from integrated_control.domain.errors import IntegratedControlError, ProtocolError
from integrated_control.domain.models import DeviceState, SpinStep
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.modbus_rtu import ModbusRtuClient


@dataclass(frozen=True)
class SpinCoaterDriverConfig:
    """Store configuration values for spin coater driver."""
    max_rpm: int = 10000
    electronic_gear_ratio: int = 10000
    maximum_single_revolution_position: int = 8388608
    glass_origin_position: int = 3458608
    home_motion_time_s: float = 2.0
    home_poll_start_delay_s: float = 1.5
    home_poll_interval_s: float = 0.25
    home_position_tolerance_counts: int = 10000
    communication_compensation_s: float = 0.6

    def __post_init__(self) -> None:
        """Validate and normalize the initialized spin coater driver config fields."""
        if self.maximum_single_revolution_position <= 0:
            raise ValueError("Single-revolution counts must be positive")
        if not 0 <= self.glass_origin_position < self.maximum_single_revolution_position:
            raise ValueError("Glass origin must be within one revolution")
        if self.home_motion_time_s <= 0 or self.home_poll_interval_s <= 0:
            raise ValueError("Home timeout and poll interval must be positive")
        if self.home_poll_start_delay_s < 0:
            raise ValueError("Home poll start delay cannot be negative")
        if not 0 <= self.home_position_tolerance_counts < (
            self.maximum_single_revolution_position // 2
        ):
            raise ValueError("Home position tolerance is invalid")


class SpinCoaterDriver(SpinCoater):
    """Native Modbus driver migrated from old_code/spinCoater2.py."""

    MODE = 0x0101
    ELECTRONIC_GEAR_RATIO = 0x0201
    INNER_SPEED_MODE = 0x4101
    SPEED = 0x4102
    ACCELERATION_TIME = 0x4103
    DECELERATION_TIME = 0x4104
    POSITION_MOVING_TYPE = 0x5301
    POSITION_CONTROL_TYPE = 0x5302
    INNER_MULTI_POSITION_MODE = 0x4001
    POSITION_1 = 0x5305
    SINGLE_REVOLUTION_POSITION = 0xD013

    DIGITAL_INPUT_FUNCTIONS = {
        0x6001: 21,
        0x6003: 22,
        0x6005: 23,
        0x6007: 24,
        0x6009: 19,
        0x600B: 1,
    }
    POSITION_COMMANDS = (0x6002, 0x6004, 0x6006, 0x6008)
    POSITION_SELECT = 0x600A
    SERVO_ON = 0x600C

    def __init__(
        self,
        client: ModbusRtuClient,
        config: SpinCoaterDriverConfig | None = None,
        *,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Initialize spin coater driver dependencies and internal state."""
        self._client = client
        self._config = config or SpinCoaterDriverConfig()
        self._sleep = sleep
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None
        self._rpm = 0
        self._angle_homed = False
        self._last_recipe: list[SpinStep] = []

    @property
    def device_id(self) -> str:
        """Return the device id exposed by this component."""
        return "spin_coater"

    def initialize(self) -> ActionResult:
        """Initialize the spin coater driver and return its readiness or failure result."""
        self._activity = "INITIALIZING"
        try:
            self._client.open()
            for address, value in self.DIGITAL_INPUT_FUNCTIONS.items():
                self._client.write_single_register(address, value)
            self._client.write_single_register(self.SERVO_ON, 0)
            self._write_u32_low_word_first(
                self.ELECTRONIC_GEAR_RATIO,
                self._config.electronic_gear_ratio,
            )
            self._set_speed_mode()
        except IntegratedControlError as exc:
            self._close_after_failure()
            return self._failure("SPIN_COATER_INITIALIZATION_FAILED", exc)
        self._initialized = True
        self._fault = None
        self._activity = "IDLE"
        return ActionResult.done("Native spin coater initialized")

    def home(self) -> ActionResult:
        """Move the device to its configured home position and report completion."""
        if failure := self._ready_failure():
            return failure
        self._activity = "HOMING"
        self._angle_homed = False
        old_ratio: int | None = None
        operation_error: IntegratedControlError | None = None
        final_position: int | None = None
        try:
            old_ratio = self._read_u32_low_word_first(
                self.ELECTRONIC_GEAR_RATIO
            )
            self._write_u32_low_word_first(
                self.ELECTRONIC_GEAR_RATIO,
                self._config.maximum_single_revolution_position,
            )
            self._client.write_single_register(self.MODE, 0)
            self._client.write_single_register(
                self.INNER_MULTI_POSITION_MODE, 1
            )
            self._client.write_single_register(self.POSITION_MOVING_TYPE, 0)
            self._client.write_single_register(self.POSITION_CONTROL_TYPE, 4)
            current = self._read_u32_low_word_first(
                self.SINGLE_REVOLUTION_POSITION
            )
            target = self._positive_position_delta(
                current,
                self._config.glass_origin_position,
            )
            if not self._position_is_home(current):
                self._write_u32_low_word_first(self.POSITION_1, target)
                # The legacy controller enables the servo before raising
                # POSINSEL.  Reversing these calls can make the drive ignore
                # the one-shot position-start signal.
                self._client.write_single_register(self.SERVO_ON, 1)
                self._select_position(1)
                final_position = self._wait_for_home_position()
            else:
                final_position = current
        except IntegratedControlError as exc:
            operation_error = exc

        cleanup_error = self._restore_after_home(old_ratio)
        if operation_error is not None:
            if cleanup_error is not None:
                operation_error = ProtocolError(
                    f"{operation_error}; restore failed: {cleanup_error}"
                )
            return self._failure("SPIN_COATER_HOME_FAILED", operation_error)
        if cleanup_error is not None:
            return self._failure("SPIN_COATER_HOME_RESTORE_FAILED", cleanup_error)

        self._rpm = 0
        self._angle_homed = True
        self._fault = None
        self._activity = "IDLE"
        return ActionResult.done(
            "Spin coater returned to the glass origin",
            {
                "position": final_position,
                "target_position": self._config.glass_origin_position,
                "tolerance_counts": (
                    self._config.home_position_tolerance_counts
                ),
            },
        )

    def run(self, recipe: Sequence[SpinStep]) -> ActionResult:
        """Run the spin coater driver operation sequence."""
        if failure := self._ready_failure():
            return failure
        if not recipe:
            return ActionResult.failed("EMPTY_RECIPE", "Spin recipe is empty")
        for step in recipe:
            if not 0 < step.rpm <= self._config.max_rpm:
                return ActionResult.failed(
                    "INVALID_SPIN_STEP",
                    f"RPM must be within 1..{self._config.max_rpm}",
                )
            if step.duration_s <= 0 or step.acceleration_rpm_s <= 0:
                return ActionResult.failed(
                    "INVALID_SPIN_STEP",
                    "Duration and acceleration must be positive",
                )

        self._activity = "SPINNING"
        current_rpm = 0
        try:
            self._set_speed_mode()
            self._client.write_single_register(self.SERVO_ON, 1)
            for index, step in enumerate(recipe):
                acceleration_s = abs(step.rpm - current_rpm) / step.acceleration_rpm_s
                deceleration_s = (
                    step.rpm / step.acceleration_rpm_s
                    if index == len(recipe) - 1
                    else 0.0
                )
                constant_s = step.duration_s - acceleration_s - deceleration_s
                if constant_s < 0:
                    raise ValueError(
                        "Spin duration is shorter than acceleration and deceleration"
                    )
                ramp_ms = round(acceleration_s * 1000.0)
                deceleration_ms = round(
                    (deceleration_s or acceleration_s) * 1000.0
                )
                self._write_speed(step.rpm, ramp_ms, deceleration_ms)
                self._rpm = step.rpm
                current_rpm = step.rpm
                self._sleep(
                    max(
                        0.0,
                        constant_s - self._config.communication_compensation_s,
                    )
                )
                if index == len(recipe) - 1:
                    self._write_speed(0, ramp_ms, deceleration_ms)
                    self._sleep(deceleration_s)
                    self._client.write_single_register(self.SERVO_ON, 0)
                    self._rpm = 0
        except ValueError as exc:
            self._safe_servo_off()
            self._activity = "IDLE"
            return ActionResult.failed("INVALID_SPIN_STEP", str(exc))
        except IntegratedControlError as exc:
            self._safe_servo_off()
            return self._failure("SPIN_COATER_RUN_FAILED", exc)

        self._last_recipe = list(recipe)
        homed = self.home()
        if not homed.success:
            return homed
        return ActionResult.done(
            "Spin recipe completed",
            {"steps": len(recipe), "rpm": 0, "homed": True},
        )

    def stop(self) -> ActionResult:
        """Request spin coater driver shutdown and report the implementation result; physical stop support depends on the driver."""
        error: IntegratedControlError | None = None
        if self._initialized:
            try:
                self._client.write_single_register(self.SERVO_ON, 0)
            except IntegratedControlError as exc:
                error = exc
        try:
            self._client.close()
        except IntegratedControlError as exc:
            error = error or exc
        self._initialized = False
        self._rpm = 0
        self._activity = "IDLE"
        if error is not None:
            return self._failure("SPIN_COATER_STOP_FAILED", error)
        return ActionResult.done("Spin coater servo disabled and connection closed")

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
                "rpm": self._rpm,
                "homed": self._angle_homed,
                "last_recipe_steps": len(self._last_recipe),
                "max_rpm": self._config.max_rpm,
                "recovered_communication_errors": getattr(
                    self._client, "recovered_error_count", 0
                ),
                "backend": "native",
            },
            self._fault,
        )

    def _set_speed_mode(self) -> None:
        """Select the spin coater speed-control mode."""
        self._client.write_single_register(self.MODE, 1)
        self._client.write_single_register(self.INNER_SPEED_MODE, 0)

    def _write_speed(self, rpm: int, acceleration_ms: int, deceleration_ms: int) -> None:
        """Write the spin coater speed target to its controller registers."""
        self._client.write_single_register(self.ACCELERATION_TIME, acceleration_ms)
        self._client.write_single_register(self.DECELERATION_TIME, deceleration_ms)
        self._client.write_single_register(self.SPEED, rpm)

    def _select_position(self, position_id: int) -> None:
        """Select the position register used for spin coater feedback."""
        bits = [
            (position_id >> shift) & 1
            for shift in (3, 2, 1, 0)
        ]
        self._client.write_single_register(self.POSITION_SELECT, 0)
        for address, bit in zip(self.POSITION_COMMANDS, bits):
            self._client.write_single_register(address, bit)
        self._client.write_single_register(self.POSITION_SELECT, 1)

    def _positive_position_delta(self, current: int, target: int) -> int:
        """Calculate forward position travel with the configured wraparound convention."""
        return (
            target - current
        ) % self._config.maximum_single_revolution_position

    def _position_is_home(self, position: int) -> bool:
        """Check whether spin coater position feedback is within the home tolerance."""
        revolution = self._config.maximum_single_revolution_position
        difference = abs(position - self._config.glass_origin_position) % revolution
        circular_error = min(difference, revolution - difference)
        return circular_error <= self._config.home_position_tolerance_counts

    def _wait_for_home_position(self) -> int:
        """Poll spin coater position until home is reached or the timeout expires."""
        poll_interval = self._config.home_poll_interval_s
        initial_delay = min(
            self._config.home_poll_start_delay_s,
            self._config.home_motion_time_s,
        )
        if initial_delay:
            self._sleep(initial_delay)
        remaining_time = self._config.home_motion_time_s - initial_delay
        attempts = max(
            1,
            math.ceil(remaining_time / poll_interval) + 1,
        )
        position = -1
        for attempt in range(attempts):
            if attempt:
                self._sleep(poll_interval)
            position = self._read_u32_low_word_first(
                self.SINGLE_REVOLUTION_POSITION
            )
            if self._position_is_home(position):
                return position
        raise ProtocolError(
            "Spin coater did not reach the glass origin: "
            f"target={self._config.glass_origin_position}, "
            f"actual={position}, "
            f"tolerance={self._config.home_position_tolerance_counts}"
        )

    def _restore_after_home(
        self, old_ratio: int | None
    ) -> IntegratedControlError | None:
        """Restore normal spin configuration after the homing operation."""
        errors: list[IntegratedControlError] = []
        try:
            self._client.write_single_register(self.SERVO_ON, 0)
        except IntegratedControlError as exc:
            errors.append(exc)
        if old_ratio is not None:
            try:
                self._write_u32_low_word_first(
                    self.ELECTRONIC_GEAR_RATIO, old_ratio
                )
            except IntegratedControlError as exc:
                errors.append(exc)
        try:
            self._set_speed_mode()
        except IntegratedControlError as exc:
            errors.append(exc)
        if not errors:
            return None
        return ProtocolError("; ".join(str(error) for error in errors))

    def _read_u32_low_word_first(self, address: int) -> int:
        """Read a 32-bit register value encoded with the low 16-bit word first."""
        low, high = self._client.read_holding_registers(address, 2)
        return high * 65536 + low

    def _write_u32_low_word_first(self, address: int, value: int) -> None:
        """Write a 32-bit value using low-word-first register ordering."""
        self._client.write_multiple_registers(
            address,
            [value & 0xFFFF, (value >> 16) & 0xFFFF],
        )

    def _safe_servo_off(self) -> None:
        """Attempt to disable the servo during failure cleanup without hiding the original error."""
        try:
            self._client.write_single_register(self.SERVO_ON, 0)
        except IntegratedControlError:
            pass
        self._rpm = 0

    def _ready_failure(self) -> ActionResult | None:
        """Return a not-ready or fault result when the component cannot accept an operation."""
        if not self._initialized:
            return ActionResult.failed(
                "DEVICE_NOT_READY", "Spin coater is not initialized"
            )
        return None

    def _close_after_failure(self) -> None:
        """Close available transports after an initialization or communication failure."""
        try:
            self._client.close()
        except IntegratedControlError:
            pass

    def _failure(self, code: str, exc: Exception) -> ActionResult:
        """Record the driver fault and return a failed ActionResult with its error code."""
        self._fault = str(exc) or type(exc).__name__
        self._activity = "FAULT"
        return ActionResult.failed(code, self._fault)
