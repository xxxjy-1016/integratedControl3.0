from abc import abstractmethod
from typing import Literal

from integrated_control.devices.base import Device
from integrated_control.domain.results import ActionResult

Axis = Literal["x", "y"]


class Stage(Device):
    @abstractmethod
    def move_axis(
        self, axis: Axis, target: float, *, ignore_limit: bool = False
    ) -> ActionResult: ...

    @abstractmethod
    def get_raw_position(self, axis: Axis) -> float: ...

    @abstractmethod
    def get_offset(self, axis: Axis) -> float: ...

    @abstractmethod
    def set_offset(self, axis: Axis, value: float) -> None: ...

    def move_axis_raw(
        self, axis: Axis, target: float, *, ignore_limit: bool = False
    ) -> ActionResult:
        """Move using the drive coordinate without applying the user offset."""
        return self.move_axis(
            axis,
            target - self.get_offset(axis),
            ignore_limit=ignore_limit,
        )

    def set_current_position_as_zero(self, axis: Axis) -> ActionResult:
        return ActionResult.failed(
            "STAGE_HARDWARE_ZERO_UNSUPPORTED",
            f"{axis.upper()} axis does not support hardware position clearing",
        )

    def needs_startup_homing(self) -> bool:
        return False

    def reload_saved_offsets(self) -> ActionResult:
        return ActionResult.done("Stage offsets do not require reloading")

    def save_offsets(self) -> ActionResult:
        return ActionResult.done(
            "Stage offsets are not backed by persistent storage",
            {"offset_x": self.get_offset("x"), "offset_y": self.get_offset("y")},
        )

    def mark_at_origin(self, value: bool) -> ActionResult:
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
