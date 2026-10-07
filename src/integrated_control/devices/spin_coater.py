from abc import abstractmethod
from collections.abc import Sequence

from integrated_control.devices.base import Device
from integrated_control.domain.models import SpinStep
from integrated_control.domain.results import ActionResult


class SpinCoater(Device):
    """Represent spin coater and its associated operations."""
    @abstractmethod
    def home(self) -> ActionResult: """Move the device to its configured home position and report completion."""; ...

    @abstractmethod
    def run(self, recipe: Sequence[SpinStep]) -> ActionResult: """Execute the supplied spin recipe and report completion or failure."""; ...
