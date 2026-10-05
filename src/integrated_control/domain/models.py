from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class DeviceState:
    device_id: str
    lifecycle: str
    activity: str
    measurements: dict[str, Any] = field(default_factory=dict)
    fault: str | None = None


@dataclass(frozen=True)
class HomingConfig:
    step: float = 1.0
    max_steps: int = 500

    def __post_init__(self) -> None:
        if self.step <= 0:
            raise ValueError("Homing step must be positive")
        if self.max_steps <= 0:
            raise ValueError("Homing max_steps must be positive")


@dataclass(frozen=True)
class Pose2D:
    x: float
    y: float
    theta: float = 0.0


@dataclass(frozen=True)
class SpinStep:
    rpm: int
    duration_s: float
    acceleration_rpm_s: float = 0.0
