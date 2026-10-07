from abc import abstractmethod

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult


class Camera(Device):
    """Camera extension point shared by simulated and future hardware drivers.

    Actor will call this interface for optional visual checkpoints. A capture
    result contains an image reference, not a verified sample-state change.
    Locate returns an observation for Actor to validate before updating Views.
    Neither method writes task or resource state. Existing method signatures
    stay unchanged so hardware drivers can replace SimulatedCamera."""
    @abstractmethod
    def capture(self, station: str) -> ActionResult: """Capture an image and return the camera implementation result."""; ...

    @abstractmethod
    def locate(self, station: str, target: str) -> ActionResult: """Locate the requested target through the camera implementation."""; ...
