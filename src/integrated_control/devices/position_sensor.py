from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.devices.stage import Axis


class PositionSensor(Device):
    @abstractmethod
    def is_triggered(self, axis: Axis) -> bool: ...

    @abstractmethod
    def read_voltage(self, axis: Axis) -> float: ...
