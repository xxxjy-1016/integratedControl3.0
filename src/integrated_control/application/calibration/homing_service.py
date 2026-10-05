from integrated_control.devices.position_sensor import PositionSensor
from integrated_control.devices.stage import Axis, Stage
from integrated_control.domain.errors import IntegratedControlError
from integrated_control.domain.models import HomingConfig
from integrated_control.domain.results import ActionResult


class HomingService:
    """Find the external sensor edge, then zero the drive coordinate."""

    RELEASE_STEP = 0.02
    RELEASE_MAX_STEPS = 100

    def __init__(
        self,
        stage: Stage,
        sensor: PositionSensor,
        config: HomingConfig | None = None,
    ) -> None:
        self._stage = stage
        self._sensor = sensor
        self._config = config or HomingConfig()

    def home_xy(self) -> ActionResult:
        for axis in ("x", "y"):
            result = self.home_axis(axis)
            if not result.success:
                return result

        marked = self._stage.mark_at_origin(True)
        if not marked.success:
            return marked
        return ActionResult.done(
            "X/Y homing and drive position clearing completed",
            {
                "logical_x": self._stage.get_position("x"),
                "logical_y": self._stage.get_position("y"),
                "offset_x": self._stage.get_offset("x"),
                "offset_y": self._stage.get_offset("y"),
                "stage_at_origin": True,
            },
        )

    def home_axis(self, axis: Axis) -> ActionResult:
        """Home one axis and write the detected edge into the drive as zero."""
        marked = self._stage.mark_at_origin(False)
        if not marked.success:
            return marked
        try:
            start = self._stage.get_raw_position(axis)
            trigger_position = start

            if not self._sensor.is_triggered(axis):
                trigger_position = self._search_for_trigger(axis, start)
                if trigger_position is None:
                    return ActionResult.failed(
                        f"HOMING_{axis.upper()}_NOT_TRIGGERED",
                        f"{axis.upper()} sensor did not trigger within "
                        f"{self._config.max_steps} steps",
                    )

            release_position = self._search_for_release(axis, trigger_position)
            if release_position is None:
                return ActionResult.failed(
                    f"HOMING_{axis.upper()}_RELEASE_NOT_FOUND",
                    f"{axis.upper()} sensor remained triggered after "
                    f"{self.RELEASE_MAX_STEPS} release steps",
                )

            zeroed = self._stage.set_current_position_as_zero(axis)
            if not zeroed.success:
                return zeroed

            reloaded = self._stage.reload_saved_offsets()
            if not reloaded.success:
                return reloaded

            moved_to_origin = self._stage.move_axis(axis, 0.0)
            if not moved_to_origin.success:
                return moved_to_origin

            # A one-axis manual home cannot establish the state of the other axis.
            unmarked = self._stage.mark_at_origin(False)
            if not unmarked.success:
                return unmarked
            return ActionResult.done(
                f"{axis.upper()} homing completed with drive hardware zero",
                {
                    "sensor_release_raw": release_position,
                    "logical_position": self._stage.get_position(axis),
                    **zeroed.measurements,
                },
            )
        except IntegratedControlError as exc:
            return ActionResult.failed(
                f"HOMING_{axis.upper()}_COMMUNICATION_ERROR",
                str(exc),
            )

    def _search_for_trigger(self, axis: Axis, start: float) -> float | None:
        for step_index in range(1, self._config.max_steps + 1):
            target = start - step_index * self._config.step
            print(f"[stage home] try {axis.upper()} raw={target:.2f}")
            moved = self._stage.move_axis_raw(axis, target, ignore_limit=True)
            if not moved.success:
                raise IntegratedControlError(moved.message)
            if self._sensor.is_triggered(axis):
                position = self._stage.get_raw_position(axis)
                print(f"[stage home] {axis.upper()} sensor triggered, raw={position:.4f}")
                return position
        return None

    def _search_for_release(self, axis: Axis, start: float) -> float | None:
        for step_index in range(1, self.RELEASE_MAX_STEPS + 1):
            target = start + step_index * self.RELEASE_STEP
            print(f"[stage home] release {axis.upper()} sensor, raw={target:.4f}")
            moved = self._stage.move_axis_raw(axis, target, ignore_limit=True)
            if not moved.success:
                raise IntegratedControlError(moved.message)
            if not self._sensor.is_triggered(axis):
                position = self._stage.get_raw_position(axis)
                print(f"[stage home] {axis.upper()} sensor released, raw={position:.4f}")
                return position
        return None
