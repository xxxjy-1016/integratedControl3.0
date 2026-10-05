from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Heater(Device):
    @abstractmethod
    def set_temperature(self, temperature_c: float) -> ActionResult: ...

    @abstractmethod
    def place(self, slot: int, sample_id: str) -> ActionResult: ...

    @abstractmethod
    def remove(self, slot: int) -> ActionResult: ...
