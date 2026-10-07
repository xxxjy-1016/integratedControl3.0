from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Valve(Device):
    """Represent valve and its associated operations."""
    @abstractmethod
    def open(self) -> ActionResult: """Open the solenoid valve and report the resulting state."""; ...

    @abstractmethod
    def close(self) -> ActionResult: """Close the solenoid valve and report the resulting state."""; ...
