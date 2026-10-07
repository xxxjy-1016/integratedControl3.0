from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class VacuumStation(Device):
    """Represent vacuum station and its associated operations."""
    @abstractmethod
    def open_cover(self) -> ActionResult: """Move the vacuum station lid to its configured open position."""; ...

    @abstractmethod
    def close_cover(self) -> ActionResult: """Move the vacuum station lid to its configured closed position."""; ...

    @abstractmethod
    def evacuate(self, target_pressure_kpa: float) -> ActionResult: """Request evacuation to the target pressure through the device implementation."""; ...

    @abstractmethod
    def vent(self) -> ActionResult: """Request venting of the vacuum station through the device implementation."""; ...
