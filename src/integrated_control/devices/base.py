from abc import ABC, abstractmethod

from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult


class Device(ABC):
    """Common contract implemented by real and simulated devices."""

    @property
    @abstractmethod
    def device_id(self) -> str: ...

    @abstractmethod
    def initialize(self) -> ActionResult: ...

    @abstractmethod
    def get_state(self) -> DeviceState: ...

    @abstractmethod
    def stop(self) -> ActionResult: ...
