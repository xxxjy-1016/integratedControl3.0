from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Pipette(Device):
    """Represent pipette and its associated operations."""
    @abstractmethod
    def move_z(self, height: float) -> ActionResult: """Move the vertical axis to the requested position and report the operation result."""; ...

    @abstractmethod
    def attach_tip(self, tip_id: str) -> ActionResult: """Record attachment of the selected pipette tip after checking device readiness."""; ...

    @abstractmethod
    def eject_tip(self) -> ActionResult: """Eject or clear the attached pipette tip and update its tracked state."""; ...

    @abstractmethod
    def aspirate(
        self,
        volume_ul: float,
        *,
        require_liquid_detection: bool = True,
    ) -> ActionResult: """Aspirate the requested volume using the supplied pipetting settings."""; ...

    @abstractmethod
    def dispense(self, volume_ul: float | None = None) -> ActionResult: """Dispense the requested volume using the supplied pipetting settings."""; ...
