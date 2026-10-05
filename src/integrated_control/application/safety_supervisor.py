from integrated_control.application.device_manager import DeviceManager
from integrated_control.domain.results import ActionResult


class SafetySupervisor:
    """Software-level readiness checks; not a replacement for hardware safety."""

    def __init__(self, devices: DeviceManager) -> None:
        self._devices = devices

    def verify_ready(self) -> ActionResult:
        failed = [
            device_id
            for device_id, state in self._devices.states().items()
            if state.lifecycle != "READY"
        ]
        if failed:
            return ActionResult.failed(
                "DEVICE_NOT_READY", f"Devices not ready: {', '.join(failed)}"
            )
        return ActionResult.done("All software readiness checks passed")
