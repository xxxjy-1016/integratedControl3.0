from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Camera(Device):
    @abstractmethod
    def capture(self, station: str) -> ActionResult: ...

    @abstractmethod
    def locate(self, station: str, target: str) -> ActionResult: ...
