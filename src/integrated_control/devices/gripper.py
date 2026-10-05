from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Gripper(Device):
    @abstractmethod
    def move_z(self, height: float) -> ActionResult: ...

    @abstractmethod
    def set_opening(self, opening: float) -> ActionResult: ...

    @abstractmethod
    def open(self) -> ActionResult: ...

    @abstractmethod
    def close(self, force: float = 50.0) -> ActionResult: ...

    @abstractmethod
    def rotate(self, angle: float) -> ActionResult: ...
