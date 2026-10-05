from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Valve(Device):
    @abstractmethod
    def open(self) -> ActionResult: ...

    @abstractmethod
    def close(self) -> ActionResult: ...
