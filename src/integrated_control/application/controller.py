from integrated_control.application.device_manager import DeviceManager
from integrated_control.application.safety_supervisor import SafetySupervisor
from integrated_control.application.state_store import StateStore, SystemSnapshot
from integrated_control.application.calibration.homing_service import HomingService
from integrated_control.domain.enums import SystemState
from integrated_control.domain.results import ActionResult
from integrated_control.devices.stage import Stage
from typing import cast


class SystemController:
    def __init__(
        self,
        devices: DeviceManager,
        homing: HomingService,
        state_store: StateStore | None = None,
    ) -> None:
        self.devices = devices
        self._homing = homing
        self._state = state_store or StateStore()
        self._safety = SafetySupervisor(devices)
        self._stage = cast(Stage, devices.get("stage"))

    @property
    def snapshot(self) -> SystemSnapshot:
        return self._state.get()

    def start(self) -> ActionResult:
        self._state.set(SystemState.INITIALIZING, "Initializing devices")
        initialized = self.devices.initialize_all()
        if not initialized.success:
            return self._fault(initialized)

        if self._stage.needs_startup_homing():
            self._state.set(SystemState.HOMING, "Homing X/Y stage")
            homed = self._homing.home_xy()
            if not homed.success:
                self.devices.stop_all()
                return self._fault(homed)
        else:
            homed = ActionResult.done(
                "Saved stage origin is valid; startup homing skipped",
                {"stage_at_origin": True},
            )

        ready = self._safety.verify_ready()
        if not ready.success:
            self.devices.stop_all()
            return self._fault(ready)

        self._state.set(SystemState.READY, "System ready")
        return ActionResult.done(
            "PC control application started",
            {
                **homed.measurements,
                "device_count": len(self.devices.states()),
            },
        )

    def shutdown(self) -> ActionResult:
        result = self.devices.stop_all()
        if result.success:
            self._state.set(SystemState.STOPPED, "System stopped")
        else:
            self._fault(result)
        return result

    def _fault(self, result: ActionResult) -> ActionResult:
        self._state.set(SystemState.FAULT, result.message, result.error_code)
        return result
