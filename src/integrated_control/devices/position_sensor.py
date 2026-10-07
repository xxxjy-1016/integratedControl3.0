from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.devices.stage import Axis


class PositionSensor(Device):
    """Represent position sensor and its associated operations."""
    @abstractmethod
    def is_triggered(self, axis: Axis) -> bool: """Return whether the selected position sensor reports an active trigger."""; ...

    @abstractmethod
    def read_voltage(self, axis: Axis) -> float: """Read the voltage reported by the selected position sensor channel."""; ...
