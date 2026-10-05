from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class VacuumStation(Device):
    @abstractmethod
    def open_cover(self) -> ActionResult: ...

    @abstractmethod
    def close_cover(self) -> ActionResult: ...

    @abstractmethod
    def evacuate(self, target_pressure_kpa: float) -> ActionResult: ...

    @abstractmethod
    def vent(self) -> ActionResult: ...
