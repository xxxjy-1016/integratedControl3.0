from collections.abc import Iterable

from integrated_control.devices.base import Device
from integrated_control.domain.models import DeviceState
from integrated_control.domain.results import ActionResult


class DeviceManager:
    """Register devices and coordinate their initialization, shutdown, and state collection."""
    def __init__(self, devices: Iterable[Device] = ()) -> None:
        """Initialize device manager dependencies and internal state."""
        self._devices: dict[str, Device] = {}
        for device in devices:
            self.register(device)

    def register(self, device: Device) -> None:
        """Register a device under its identifier, rejecting duplicate identifiers."""
        if device.device_id in self._devices:
            raise ValueError(f"Duplicate device id: {device.device_id}")
        self._devices[device.device_id] = device

    def get(self, device_id: str) -> Device:
        """Return the device registered under the requested identifier."""
        return self._devices[device_id]

    def initialize_all(self) -> ActionResult:
        """Initialize registered devices and report the first unsuccessful initialization."""
        initialized: list[Device] = []
        for device in self._devices.values():
            result = device.initialize()
            if not result.success:
                for active_device in reversed(initialized):
                    active_device.stop()
                return ActionResult.failed(
                    result.error_code or "INITIALIZATION_FAILED",
                    f"Failed to initialize {device.device_id}: {result.message}",
                )
            initialized.append(device)
        return ActionResult.done(
            "All devices initialized", {"device_count": len(initialized)}
        )

    def stop_all(self) -> ActionResult:
        """Request shutdown of all registered devices and aggregate failures."""
        failures: list[str] = []
        for device in reversed(tuple(self._devices.values())):
            if not device.stop().success:
                failures.append(device.device_id)
        if failures:
            return ActionResult.failed("STOP_FAILED", ", ".join(failures))
        return ActionResult.done("All devices stopped")

    def states(self) -> dict[str, DeviceState]:
        """Collect state observations from all registered devices."""
        return {key: device.get_state() for key, device in self._devices.items()}
