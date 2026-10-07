from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Gripper(Device):
    """Represent gripper and its associated operations."""
    @abstractmethod
    def move_z(self, height: float) -> ActionResult: """Move the vertical axis to the requested position and report the operation result."""; ...

    @abstractmethod
    def set_opening(self, opening: float) -> ActionResult: """Set the gripper opening position using the supplied motion and torque settings."""; ...

    @abstractmethod
    def open(self) -> ActionResult: """Open the gripper using its configured opening or clamping settings."""; ...

    @abstractmethod
    def close(self, force: float = 50.0) -> ActionResult: """Close the gripper using its configured opening or clamping settings."""; ...

    @abstractmethod
    def rotate(self, angle: float) -> ActionResult: """Rotate the gripper by the requested angle and report completion or failure."""; ...
