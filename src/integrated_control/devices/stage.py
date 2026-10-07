from abc import abstractmethod
from typing import Literal

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult

Axis = Literal["x", "y"]


class Stage(Device):
    """Represent stage and its associated operations."""
    @abstractmethod
    def move_axis(
        self, axis: Axis, target: float, *, ignore_limit: bool = False
    ) -> ActionResult: """Move one stage axis to the requested coordinate using its configured offset."""; ...

    @abstractmethod
    def get_raw_position(self, axis: Axis) -> float: """Return the selected stage axis position before applying its coordinate offset."""; ...

    @abstractmethod
    def get_offset(self, axis: Axis) -> float: """Return the coordinate offset currently assigned to the selected stage axis."""; ...

    @abstractmethod
    def set_offset(self, axis: Axis, value: float) -> None: """Update the coordinate offset assigned to the selected stage axis."""; ...

    def move_axis_raw(
        self, axis: Axis, target: float, *, ignore_limit: bool = False
    ) -> ActionResult:
        """Move one stage axis to a raw coordinate without applying its configured offset."""
        return self.move_axis(
            axis,
            target - self.get_offset(axis),
            ignore_limit=ignore_limit,
        )

    def set_current_position_as_zero(self, axis: Axis) -> ActionResult:
        """Establish the selected axis current physical position as its hardware zero."""
        return ActionResult.failed(
            "STAGE_HARDWARE_ZERO_UNSUPPORTED",
            f"{axis.upper()} axis does not support hardware position clearing",
        )

    def needs_startup_homing(self) -> bool:
        """Return whether startup homing is required."""
        return False

    def reload_saved_offsets(self) -> ActionResult:
        """Restore stage offsets from the persisted calibration state."""
        return ActionResult.done("Stage offsets do not require reloading")

    def save_offsets(self) -> ActionResult:
        """Persist the current axis offsets and stage-origin metadata."""
        return ActionResult.done(
            "Stage offsets are not backed by persistent storage",
            {"offset_x": self.get_offset("x"), "offset_y": self.get_offset("y")},
        )

    def mark_at_origin(self, value: bool) -> ActionResult:
        """Update the saved stage-origin flag for startup homing decisions."""
        return ActionResult.done(
            "Stage origin state updated", {"stage_at_origin": bool(value)}
        )

    def get_position(self, axis: Axis) -> float:
        """Return the user-facing position after applying the homing offset."""
        return self.get_raw_position(axis) - self.get_offset(axis)

    def jog(self, axis: Axis, distance: float) -> ActionResult:
        """Move one axis relative to its current logical position."""
        return self.move_axis(axis, self.get_position(axis) + distance)

    def move_xy(self, x: float, y: float) -> ActionResult:
        """Move X then Y, stopping immediately when either movement fails."""
        x_result = self.move_axis("x", x)
        if not x_result.success:
            return x_result
        y_result = self.move_axis("y", y)
        if not y_result.success:
            return y_result
        return ActionResult.done(
            "X/Y movement completed",
            {
                "logical_x": self.get_position("x"),
                "logical_y": self.get_position("y"),
                "raw_x": self.get_raw_position("x"),
                "raw_y": self.get_raw_position("y"),
            },
        )
