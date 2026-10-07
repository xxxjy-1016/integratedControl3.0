from abc import ABC, abstractmethod

from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult


class Device(ABC):
    """Common contract implemented by real and simulated devices."""

    @property
    @abstractmethod
    def device_id(self) -> str: """Return the device id exposed by this component."""; ...

    @abstractmethod
    def initialize(self) -> ActionResult: """Initialize the device and return its readiness or failure result."""; ...

    @abstractmethod
    def get_state(self) -> DeviceState: """Return the device lifecycle, activity, measurements, and any reported fault."""; ...

    @abstractmethod
    def stop(self) -> ActionResult: """Request device shutdown and report the implementation result; physical stop support depends on the driver."""; ...
