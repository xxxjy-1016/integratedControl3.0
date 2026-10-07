from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Heater(Device):
    """Represent heater and its associated operations."""
    @abstractmethod
    def set_temperature(self, temperature_c: float) -> ActionResult: """Set the requested heater temperature and report the operation result."""; ...

    @abstractmethod
    def place(self, slot: int, sample_id: str) -> ActionResult: """Record the specified sample as occupying the selected heater slot."""; ...

    @abstractmethod
    def remove(self, slot: int) -> ActionResult: """Remove the occupancy record from the selected heater slot."""; ...
