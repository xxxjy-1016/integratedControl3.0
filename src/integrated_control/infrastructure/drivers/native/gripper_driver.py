from dataclasses import dataclass
import time

from integrated_control.devices.gripper import Gripper
from integrated_control.domain.errors import IntegratedControlError
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult
from integrated_control.infrastructure.transports.ascii_motion import (
    AsciiSerialTransport,
    signed_hex_command,
    wait_for_ascii_status,
)
from integrated_control.infrastructure.transports.modbus_rtu import ModbusRtuClient


@dataclass(frozen=True)
class GripperDriverConfig:
    """Store configuration values for gripper driver."""
    minimum_z: float = 0.0
    maximum_z: float = 100.0
    z_pulses_per_100: int = 15000
    movement_timeout_s: float = 10.0
    poll_interval_s: float = 0.1


class GripperDriver(Gripper):
    """Native driver migrated from ``old/hand.py``."""

    CLAMP_INIT = 0x0100
    ROTATION_INIT = 0x0101
    CLAMP_TORQUE = 0x0103
    CLAMP_TARGET = 0x0105
    ROTATION_TARGET = 0x0108
    CLAMP_STATUS = 0x0202
    ROTATION_STATUS = 0x0203
    CLAMP_POSITION = 0x0204

    Z_INIT = b">02G9158"
    Z_QUERY = b">02d4819"
    Z_ARRIVED = b">02d0172DE"

    def __init__(
        self,
        transport: AsciiSerialTransport,
        config: GripperDriverConfig | None = None,
    ) -> None:
        """Initialize gripper driver dependencies and internal state."""
        self._transport = transport
        self._client = ModbusRtuClient(transport)
        self._config = config or GripperDriverConfig()
        self._initialized = False
        self._activity = "IDLE"
        self._fault: str | None = None
        self._z: float | None = None
        self._opening: float | None = None
        self._rotation: float | None = None
        self._force: float | None = None
        self._holding = False

    @property
    def device_id(self) -> str:
        """Return the device id exposed by this component."""
        return "gripper"

    def initialize(self) -> ActionResult:
        """Initialize the gripper driver and return its readiness or failure result."""
        self._activity = "INITIALIZING"
        try:
            self._transport.open()
            self._client.write_single_register(self.CLAMP_INIT, 1)
            self._wait_modbus(self.CLAMP_STATUS, {1})
            self._client.write_single_register(self.ROTATION_INIT, 1)
            self._wait_modbus(self.ROTATION_STATUS, {1})
            self._transport.write(self.Z_INIT)
            self._wait_z()
        except (IntegratedControlError, ValueError) as exc:
            self._close_after_failure()
            return self._failure("GRIPPER_INITIALIZATION_FAILED", exc)
        self._initialized = True
        self._fault = None
        self._activity = "IDLE"
        self._z = 0.0
        self._opening = 100.0
        self._rotation = 0.0
        self._holding = False
        return ActionResult.done("Native gripper initialized")

    def move_z(self, height: float) -> ActionResult:
        """Move the vertical axis to the requested position and report the operation result."""
        if failure := self._ready_failure():
            return failure
        if not self._config.minimum_z <= height <= self._config.maximum_z:
            return ActionResult.failed(
                "GRIPPER_Z_LIMIT",
                f"Gripper Z target {height} is outside "
                f"{self._config.minimum_z}..{self._config.maximum_z}",
            )
        pulses = int(height / 100.0 * self._config.z_pulses_per_100)
        self._activity = "MOVING_Z"
        try:
            self._transport.write(signed_hex_command(b">02D", pulses, width=4))
            self._wait_z()
        except (IntegratedControlError, ValueError) as exc:
            return self._failure("GRIPPER_Z_MOVE_FAILED", exc)
        self._z = height
        self._activity = "IDLE"
        return ActionResult.done("Gripper Z movement completed", {"z": height})

    def set_opening(self, opening: float) -> ActionResult:
        """Set the gripper opening position using the supplied motion and torque settings."""
        if failure := self._ready_failure():
            return failure
        if not 0.0 <= opening <= 100.0:
            return ActionResult.failed(
                "GRIPPER_OPENING_LIMIT", "Opening must be within 0..100"
            )
        target = round(100.0 - opening)
        self._activity = "GRIPPING"
        try:
            self._client.write_single_register(self.CLAMP_TARGET, target)
            status = self._wait_modbus(self.CLAMP_STATUS, {1, 2})
            position = self._client.read_holding_registers(self.CLAMP_POSITION)[0]
        except IntegratedControlError as exc:
            return self._failure("GRIPPER_OPENING_FAILED", exc)
        self._opening = 100.0 - position
        self._holding = status == 2
        self._activity = "HOLDING" if self._holding else "IDLE"
        return ActionResult.done(
            "Gripper opening set",
            {"opening": self._opening, "holding_object": self._holding},
        )

    def open(self) -> ActionResult:
        """Open the gripper using its configured opening or clamping settings."""
        result = self.set_opening(100.0)
        if result.success:
            self._force = 0.0
        return result

    def close(self, force: float = 50.0) -> ActionResult:
        """Close the gripper using its configured opening or clamping settings."""
        if failure := self._ready_failure():
            return failure
        if not 10.0 <= force <= 100.0:
            return ActionResult.failed(
                "GRIPPER_FORCE_LIMIT", "Force must be within 10..100"
            )
        try:
            self._client.write_single_register(self.CLAMP_TORQUE, round(force))
        except IntegratedControlError as exc:
            return self._failure("GRIPPER_FORCE_FAILED", exc)
        self._force = force
        return self.set_opening(0.0)

    def rotate(self, angle: float) -> ActionResult:
        """Rotate the gripper by the requested angle and report completion or failure."""
        if failure := self._ready_failure():
            return failure
        target = round(angle)
        if not -32768 <= target <= 32767:
            return ActionResult.failed(
                "GRIPPER_ROTATION_LIMIT", "Rotation must fit a signed 16-bit value"
            )
        self._activity = "ROTATING"
        try:
            self._client.write_single_register(self.ROTATION_TARGET, target)
            self._wait_modbus(self.ROTATION_STATUS, {1})
        except IntegratedControlError as exc:
            return self._failure("GRIPPER_ROTATION_FAILED", exc)
        self._rotation = float(target)
        self._activity = "HOLDING" if self._holding else "IDLE"
        return ActionResult.done(
            "Gripper rotation completed", {"angle": self._rotation}
        )

    def stop(self) -> ActionResult:
        """Request gripper driver shutdown and report the implementation result; physical stop support depends on the driver."""
        try:
            self._transport.close()
        except IntegratedControlError as exc:
            return self._failure("GRIPPER_CLOSE_FAILED", exc)
        self._initialized = False
        self._activity = "IDLE"
        return ActionResult.done(
            "Native gripper connection closed; no undocumented emergency-stop "
            "command was sent"
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
                "z": self._z,
                "opening": self._opening,
                "rotation_deg": self._rotation,
                "force_percent": self._force,
                "holding_object": self._holding,
                "backend": "native",
            },
            self._fault,
        )

    def _wait_z(self) -> None:
        """Poll vertical-axis feedback until the requested position is reached or a timeout occurs."""
        wait_for_ascii_status(
            self._transport,
            self.Z_QUERY,
            self.Z_ARRIVED,
            timeout_s=self._config.movement_timeout_s,
            poll_interval_s=self._config.poll_interval_s,
        )

    def _wait_modbus(self, address: int, accepted: set[int]) -> int:
        """Poll Modbus operation status until completion or timeout."""
        deadline = time.monotonic() + self._config.movement_timeout_s
        while time.monotonic() < deadline:
            value = self._client.read_holding_registers(address)[0]
            if value in accepted:
                return value
            time.sleep(self._config.poll_interval_s)
        from integrated_control.domain.errors import CommunicationTimeoutError

        raise CommunicationTimeoutError(
            f"Gripper register 0x{address:04X} did not reach {sorted(accepted)}"
        )

    def _ready_failure(self) -> ActionResult | None:
        """Return a not-ready or fault result when the component cannot accept an operation."""
        if not self._initialized:
            return ActionResult.failed("DEVICE_NOT_READY", "Gripper is not initialized")
        return None

    def _close_after_failure(self) -> None:
        """Close available transports after an initialization or communication failure."""
        try:
            self._transport.close()
        except IntegratedControlError:
            pass

    def _failure(self, code: str, exc: Exception) -> ActionResult:
        """Record the driver fault and return a failed ActionResult with its error code."""
        self._fault = str(exc) or type(exc).__name__
        self._activity = "FAULT"
        return ActionResult.failed(code, self._fault)
