from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceState:
    """Store device identity, lifecycle, activity, measurements, fault, acquisition time, and validity.

    Missing measurements are allowed; a known fault makes the observation invalid."""
    device_id: str
    lifecycle: str
    activity: str
    measurements: dict[str, Any] = field(default_factory=dict)
    fault: str | None = None
    updated_at: float | None = None
    valid: bool = True

    def __post_init__(self) -> None:
        # Missing measurements are permitted; a reported fault is not.
        """Validate and normalize the initialized device state fields."""
        if self.fault or self.lifecycle == "FAULT" or self.activity == "FAULT":
            object.__setattr__(self, "valid", False)


@dataclass(frozen=True)
class HomingConfig:
    """Store configuration values for homing."""
    step: float = 1.0
    max_steps: int = 500

    def __post_init__(self) -> None:
        """Validate and normalize the initialized homing config fields."""
        if self.step <= 0:
            raise ValueError("Homing step must be positive")
        if self.max_steps <= 0:
            raise ValueError("Homing max_steps must be positive")


@dataclass(frozen=True)
class Pose2D:
    """Store planar X/Y coordinates and orientation theta."""
    x: float
    y: float
    theta: float = 0.0


@dataclass(frozen=True)
class SpinStep:
    """Store one spin segment target speed, duration, and acceleration rate."""
    rpm: int
    duration_s: float
    acceleration_rpm_s: float = 0.0
