from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
from typing import Any, Callable, cast

from integrated_control.bootstrap import ApplicationContext
from integrated_control.devices.gripper import Gripper
from integrated_control.devices.heater import Heater
from integrated_control.devices.pipette import Pipette
from integrated_control.devices.spin_coater import SpinCoater
from integrated_control.devices.stage import Stage
from integrated_control.devices.vacuum_station import VacuumStation
from integrated_control.devices.valve import Valve
from integrated_control.domain.models import SpinStep
from integrated_control.domain.results import ActionResult


@dataclass(frozen=True)
class ProcessPose:
    """Four-axis pose using the percentage units from old_code/brain.py."""

    x: float
    y: float
    gripper_z: float
    pipette_z: float


# Exact local parameters used by old_code/brain.py::masterController.zksz().
SAFE_GRIPPER_Z = 1.0
SAFE_PIPETTE_Z = 0.0
TIP_DROP_Z = 90.0
GRIP_OPENING = 30.0  # old raw clamp target 70 -> new opening 100 - 70
GLASS_RELEASE_OPENING = 64.0  # old raw clamp target 36

TIP_1 = ProcessPose(97.7, 1.8, SAFE_GRIPPER_Z, 99.0)
TIP_2 = ProcessPose(95.3, 1.8, SAFE_GRIPPER_Z, 99.0)
SPIN_COATER_GRIPPER = ProcessPose(46.5, 65.5, 87.0, SAFE_PIPETTE_Z)
SPIN_COATER_PIPETTE = ProcessPose(56.0, 87.8, SAFE_GRIPPER_Z, 18.0)
BOTTLE_1_GRIPPER = ProcessPose(47.3, 11.0, 80.0, SAFE_PIPETTE_Z)
BOTTLE_1_PIPETTE = ProcessPose(56.7, 33.5, SAFE_GRIPPER_Z, 45.0)
BOTTLE_3_GRIPPER = ProcessPose(39.8, 24.9, 80.0, SAFE_PIPETTE_Z)
BOTTLE_3_PIPETTE = ProcessPose(49.2, 47.0, SAFE_GRIPPER_Z, 45.0)
GLASS_SLOT_2 = ProcessPose(88.7, 19.0, 87.5, SAFE_PIPETTE_Z)
HEATER = ProcessPose(15.0, 10.0, 75.0, SAFE_PIPETTE_Z)
VACUUM_STATION = ProcessPose(0.0, 97.0, 96.5, SAFE_PIPETTE_Z)
BOTTLE_1_ROTATION = 360.0
BOTTLE_3_ROTATION = 360.0
# Current bench testing has no physical bottle cap.  Keep the check available
# so it can be re-enabled before running the complete process with real caps.
REQUIRE_BOTTLE_CAP_DETECTION = False
# Current bench testing has no real liquid. The pipette still performs and
# records the plunger movement so the later dispense action can also be tested.
REQUIRE_LIQUID_DETECTION = False


class WorkflowFailure(RuntimeError):
    """Signal failure of a required device action in the process workflow."""
    def __init__(self, operation: str, result: ActionResult) -> None:
        """Initialize workflow failure dependencies and internal state."""
        self.operation = operation
        self.result = result
        detail = result.message or result.error_code or "unknown device failure"
        super().__init__(f"{operation}: {detail}")


class ZkszWorkflow:
    """Native-device translation of old_code/brain.py's zksz workflow."""

    def __init__(
        self,
        application: ApplicationContext,
        *,
        sleep: Callable[[float], None] = time.sleep,
        require_bottle_cap_detection: bool = REQUIRE_BOTTLE_CAP_DETECTION,
        require_liquid_detection: bool = REQUIRE_LIQUID_DETECTION,
        checkpoint: Callable[[str, int, int, float], None] | None = None,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize zksz workflow dependencies and internal state."""
        devices = application.controller.devices
        self._stage = cast(Stage, devices.get("stage"))
        self._gripper = cast(Gripper, devices.get("gripper"))
        self._pipette = cast(Pipette, devices.get("pipette"))
        self._spin_coater = cast(SpinCoater, devices.get("spin_coater"))
        self._vacuum_station = cast(
            VacuumStation, devices.get("vacuum_station")
        )
        self._valve = cast(Valve, devices.get("valve"))
        self._heater = cast(Heater, devices.get("heater"))
        self._coordinates = application.coordinates
        self._sleep = sleep
        self._require_bottle_cap_detection = require_bottle_cap_detection
        self._require_liquid_detection = require_liquid_detection
        self._checkpoint = checkpoint
        self._clock = clock
        self._active_step = None

    def _checkpoint_at(self, event: str, pose: ProcessPose) -> None:
        """Record heater placement or departure for the active matching step and invoke its callback."""
        if self._active_step is None:
            return
        kind, n, m, heater = self._active_step
        if pose != heater or (event == "placed" and kind != "step1") or (event == "picked" and kind != "step2"):
            return
        at = self._clock()
        if event == "placed":
            self._require("登记加热台占用", self._heater.place(m, f"glass-{n}"))
        else:
            self._require("登记加热台释放", self._heater.remove(m))
        if self._checkpoint is not None:
            self._checkpoint(event, n, m, at)

    def run(self) -> ActionResult:
        """Run the complete single-glass process, including its internal annealing wait."""
        try:
            self._prepare_one(GLASS_SLOT_2, HEATER)
            print("退火 20 分钟...（本次为模拟实验，模拟退火10秒）")
            self._sleep(10.0)
            self._return_one(GLASS_SLOT_2, HEATER)
        except WorkflowFailure as exc:
            return ActionResult.failed("ZKSZ_WORKFLOW_FAILED", str(exc))
        except Exception as exc:
            return ActionResult.failed(
                "ZKSZ_UNEXPECTED_ERROR",
                f"{type(exc).__name__}: {exc}",
            )

        print("zksz 流程完成。")
        return ActionResult.done("zksz workflow completed")

    def _prepare_one(self, glass_pose: ProcessPose, heater_pose: ProcessPose) -> None:
        """Transfer a glass through spin coating and vacuum flashing, then place it on the heater.

        This is step1; the scheduler handles the subsequent heating wait."""
        print("取玻璃...")
        self._pick_glass(glass_pose)
        print("放到旋涂仪...")
        self._put_glass(SPIN_COATER_GRIPPER)

        print("取吸头 1...")
        self._pick_tip(TIP_1, "zksz-tip-1")

        print("开1号瓶...")
        self._open_bottle(BOTTLE_1_GRIPPER, BOTTLE_1_ROTATION)

        print("吸 SAM...")
        self._aspirate(BOTTLE_1_PIPETTE, 100.0)

        print("关1号瓶...")
        self._close_bottle(BOTTLE_1_GRIPPER)

        print("滴 SAM...")
        self._dispense_all(SPIN_COATER_PIPETTE)

        print("旋涂 SAM...")
        recipe = [
            SpinStep(
                rpm=5000,
                duration_s=10.0,
                acceleration_rpm_s=5000.0,
            )
        ]
        with ThreadPoolExecutor(max_workers=1) as executor:
            spin_future = executor.submit(self._spin_coater.run, recipe)
            self._sleep(1.0)

            print("放回吸头 1...")
            self._drop_tip(TIP_1)

            print("等待 SAM 旋涂结束...")
            self._require("旋涂 SAM", spin_future.result())
        self._sleep(1.0)

        print("打开真空泵盖子...")
        self._require("打开真空泵盖子", self._vacuum_station.open_cover())
        self._sleep(1.0)

        print("从旋涂仪取玻璃...")
        self._pick_glass(SPIN_COATER_GRIPPER)
        print("放到真空泵...")
        self._put_glass(VACUUM_STATION)

        print("关闭真空泵盖子...")
        self._require("关闭真空泵盖子", self._vacuum_station.close_cover())
        self._sleep(1.0)

        print("打开电磁阀...")
        self._require("打开电磁阀", self._valve.open())
        self._sleep(10.0)
        print("关闭电磁阀...")
        self._require("关闭电磁阀", self._valve.close())
        self._sleep(1.0)

        print("打开真空泵盖子...")
        self._require("打开真空泵盖子", self._vacuum_station.open_cover())
        self._sleep(1.0)

        print("从真空泵取玻璃...")
        self._pick_glass(VACUUM_STATION)
        print("放到退火台...")
        self._put_glass(heater_pose)

        print("关闭真空泵盖子...")
        self._require("关闭真空泵盖子", self._vacuum_station.close_cover())
        self._sleep(1.0)

    def _return_one(self, glass_pose: ProcessPose, heater_pose: ProcessPose) -> None:
        """Retrieve a glass from the heater and return it to its original tray slot.

        This is step2; physical departure is recorded at the pickup checkpoint during the action."""
        print("从退火台取玻璃...")
        self._pick_glass(heater_pose)
        print("放回原平台...")
        self._put_glass(glass_pose)

    # Batch preparation: align step1 and step2 with the scheduler.

    def glass_pose(self, n: int) -> ProcessPose:
        """Map zero-based glass number n to its configured tray-slot pose."""
        slots = self._coordinates.get("glass_platform", {}).get("slots", [])
        if not 0 <= n < len(slots):
            raise WorkflowFailure(
                "解析玻璃槽位坐标",
                ActionResult.failed(
                    "GLASS_SLOT_OUT_OF_RANGE",
                    f"玻璃片编号 {n} 越界（共 {len(slots)} 个槽位）",
                ),
            )
        slot = slots[n]
        return ProcessPose(
            float(slot["x"]),
            float(slot["y"]),
            float(slot.get("gripper_z", 0.0)),
            float(slot.get("pipette_z", 0.0)),
        )

    def heater_pose(self, m: int) -> ProcessPose:
        """Map one-based heater number m to its configured station pose."""
        heaters = self._coordinates.get("stations", {}).get("heater", [])
        index = m - 1
        if not 0 <= index < len(heaters):
            raise WorkflowFailure(
                "解析加热工位坐标",
                ActionResult.failed(
                    "HEATER_SLOT_OUT_OF_RANGE",
                    f"加热器编号 {m} 越界（共 {len(heaters)} 个工位）",
                ),
            )
        heater = heaters[index]
        return ProcessPose(
            float(heater["x"]),
            float(heater["y"]),
            float(heater.get("gripper_z", 0.0)),
            float(heater.get("pipette_z", 0.0)),
        )

    def step1(self, n: int, m: int) -> None:
        """Prepare glass n and load heater m synchronously.

        Emit placement checkpoints during the operation; scheduling handles the heating wait between step1 and step2."""
        glass = self.glass_pose(n)
        heater = self.heater_pose(m)
        self._active_step = ("step1", n, m, heater)
        try:
            self._prepare_one(glass, heater)
        finally:
            self._active_step = None

    def step2(self, n: int, m: int) -> None:
        """Retrieve glass n from heater m and return it to its original tray slot synchronously.

        The pickup checkpoint occurs after the gripper is raised, rather than at the start of this method."""
        glass = self.glass_pose(n)
        heater = self.heater_pose(m)
        self._active_step = ("step2", n, m, heater)
        try:
            self._return_one(glass, heater)
        finally:
            self._active_step = None

    def _move_to(self, pose: ProcessPose) -> None:
        """Move the stage to the requested process pose and require successful completion."""
        self._move_safe()
        self._require("移动 XY 平台", self._stage.move_xy(pose.x, pose.y))
        self._require("移动夹爪 Z 轴", self._gripper.move_z(pose.gripper_z))
        self._require("移动移液器 Z 轴", self._pipette.move_z(pose.pipette_z))

    def _move_safe(self, picked_pose: ProcessPose | None = None) -> None:
        """Raise the gripper and pipette to their configured safe travel heights."""
        self._require(
            "夹爪抬升到安全高度",
            self._gripper.move_z(SAFE_GRIPPER_Z),
        )
        if picked_pose is not None:
            self._checkpoint_at("picked", picked_pose)
        self._require(
            "移液器抬升到安全高度",
            self._pipette.move_z(SAFE_PIPETTE_Z),
        )

    def _pick_glass(self, pose: ProcessPose) -> None:
        """Grip the glass, raise the gripper, and emit a matching heater pickup checkpoint."""
        self._move_to(pose)
        held = self._grip()
        if not held:
            # Preserve clamp_with_detection(): lower, reopen, rotate, retry,
            # retract and restore the neutral rotation.
            self._require(
                "夹爪下探重试",
                self._gripper.move_z(max(0.0, pose.gripper_z - 1.0)),
            )
            self._require("完全张开夹爪", self._gripper.open())
            self._require("夹爪旋转 45 度", self._gripper.rotate(45.0))
            self._require("夹爪返回抓取高度", self._gripper.move_z(pose.gripper_z))
            held = self._grip()
            self._move_safe(pose if held else None)
            self._require("夹爪恢复零角度", self._gripper.rotate(0.0))
        else:
            self._move_safe(pose)
        if not held:
            raise WorkflowFailure(
                "检测玻璃夹持状态",
                ActionResult.failed(
                    "GRIPPER_OBJECT_NOT_HELD",
                    "夹爪到达目标位置，但没有检测到被夹持物体",
                ),
            )
        self._sleep(1.0)

    def _put_glass(self, pose: ProcessPose) -> None:
        """Release the glass, emit a matching heater placement checkpoint, and raise the axes."""
        self._move_to(pose)
        self._require(
            "释放玻璃",
            self._gripper.set_opening(GLASS_RELEASE_OPENING),
        )
        self._checkpoint_at("placed", pose)
        self._move_safe()
        self._sleep(1.0)

    def _pick_tip(self, pose: ProcessPose, tip_id: str) -> None:
        """Align the pipette with the selected tip, attach it, and return to a safe height."""
        self._move_to(pose)
        self._require("记录已安装吸头", self._pipette.attach_tip(tip_id))
        self._sleep(1.0)

    def _drop_tip(self, pose: ProcessPose) -> None:
        """Return the pipette tip to its discard pose and eject it."""
        drop_pose = ProcessPose(
            pose.x,
            pose.y,
            SAFE_GRIPPER_Z,
            TIP_DROP_Z,
        )
        self._move_to(drop_pose)
        self._require("弹出吸头", self._pipette.eject_tip())
        self._move_safe()
        self._sleep(1.0)

    def _open_bottle(self, pose: ProcessPose, rotation: float) -> None:
        """Move to the bottle cap, grip it, and perform the configured opening rotation."""
        self._move_to(pose)
        self._require("完全张开夹爪", self._gripper.open())
        self._require("瓶盖旋转轴归零", self._gripper.rotate(0.0))
        if not self._grip():
            if self._require_bottle_cap_detection:
                raise WorkflowFailure(
                    "夹紧瓶盖",
                    ActionResult.failed(
                        "GRIPPER_OBJECT_NOT_HELD",
                        "夹爪没有检测到瓶盖",
                    ),
                )
            print("未检测到瓶盖；当前为无瓶盖测试模式，继续执行旋转动作。")
        self._require("旋开瓶盖", self._gripper.rotate(-rotation))
        self._move_safe()
        self._sleep(1.0)

    def _close_bottle(self, pose: ProcessPose) -> None:
        """Return the bottle cap and perform the configured closing rotation."""
        self._move_to(pose)
        self._require("旋紧瓶盖", self._gripper.rotate(0.0))
        self._require("释放瓶盖", self._gripper.open())
        self._move_safe()
        self._sleep(1.0)

    def _aspirate(self, pose: ProcessPose, volume_ul: float) -> None:
        """Move the pipette into the source bottle and aspirate the requested volume."""
        self._move_to(pose)
        result = self._pipette.aspirate(
            volume_ul,
            require_liquid_detection=self._require_liquid_detection,
        )
        self._require("吸液", result)
        if result.measurements.get("liquid_detected") is False:
            print("未检测到真实液体；当前为空吸测试模式，继续后续流程。")
        self._move_safe()
        self._sleep(1.0)

    def _dispense_all(self, pose: ProcessPose) -> None:
        """Move to the dispensing pose and dispense all tracked liquid."""
        self._move_to(pose)
        self._require("排液", self._pipette.dispense())
        self._move_safe()
        self._sleep(1.0)

    def _grip(self) -> bool:
        """Apply the workflow gripper position and torque settings and require success."""
        result = self._gripper.set_opening(GRIP_OPENING)
        self._require("夹紧物体", result)
        return result.measurements.get("holding_object") is not False

    @staticmethod
    def _require(operation: str, result: ActionResult) -> None:
        """Raise WorkflowFailure when a required device operation returns an unsuccessful result."""
        if not result.success:
            raise WorkflowFailure(operation, result)


def run_zksz(
    application: ApplicationContext,
    *,
    sleep: Callable[[float], None] = time.sleep,
    require_bottle_cap_detection: bool = REQUIRE_BOTTLE_CAP_DETECTION,
    require_liquid_detection: bool = REQUIRE_LIQUID_DETECTION,
) -> ActionResult:
    """Construct and run the complete single-glass workflow using the application devices."""
    return ZkszWorkflow(
        application,
        sleep=sleep,
        require_bottle_cap_detection=require_bottle_cap_detection,
        require_liquid_detection=require_liquid_detection,
    ).run()
