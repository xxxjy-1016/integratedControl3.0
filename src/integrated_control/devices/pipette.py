from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Pipette(Device):
    @abstractmethod
    def move_z(self, height: float) -> ActionResult: ...

    @abstractmethod
    def attach_tip(self, tip_id: str) -> ActionResult: ...

    @abstractmethod
    def eject_tip(self) -> ActionResult: ...

    @abstractmethod
    def aspirate(
        self,
        volume_ul: float,
        *,
        require_liquid_detection: bool = True,
    ) -> ActionResult: ...

    @abstractmethod
    def dispense(self, volume_ul: float | None = None) -> ActionResult: ...
