from abc import abstractmethod
from collections.abc import Sequence

from integrated_control.devices.base import Device
from integrated_control.domain.models import SpinStep
from integrated_control.domain.results import ActionResult


class SpinCoater(Device):
    @abstractmethod
    def home(self) -> ActionResult: ...

    @abstractmethod
    def run(self, recipe: Sequence[SpinStep]) -> ActionResult: ...
