import argparse
import shlex

from integrated_control.application.device_diagnostics import (
    DeviceDiagnosticsController,
    MotionSnapshot,
)
from integrated_control.bootstrap import build_device_diagnostics
from integrated_control.devices.stage import Axis
from integrated_control.domain.errors import ConfigurationError
from integrated_control.domain.models import SpinStep
from integrated_control.domain.results import ActionResult


HARDWARE_MODES = {"native_hardware", "hardware"}


def _parser() -> argparse.ArgumentParser:
    """Build the command-line parser for this entry point."""
    parser = argparse.ArgumentParser(description="集成设备人工调试器")
    parser.add_argument(
        "--mode",
        choices=("simulation", "native_hardware", "hardware"),
        help="覆盖 config/system.yaml 中的运行模式",
    )
    parser.add_argument("command", nargs="?", choices=("dry", "gantt"),
                        help="直接计算离线方案，不启动设备连接")
    parser.add_argument("scheduler_args", nargs=argparse.REMAINDER,
                        help="传给调度 CLI 的参数")
    return parser


def _print_help() -> None:
    """Print the supported diagnostic commands and their argument syntax."""
    print(
        """命令：
  p | status             显示所有调试设备状态
  mx <位置> / my <位置>  移动单轴到逻辑坐标
  mxy <X> <Y>            依次移动X、Y轴
  jx <距离> / jy <距离>  相对点动（正负数均可）
  rx <位置> / ry <位置>  移动到原始机器坐标（仍检查软限位）
  sx / sy                读取单个传感器
  homex / homey / home   单轴或双轴回零
  setx <值> / sety <值>  设置坐标偏移
  resetx / resety        将坐标偏移清零
  saveoffset             将当前X/Y偏移保存到状态文件

夹爪：
  gz <高度>              移动夹爪Z轴
  gopen                  完全张开夹爪
  gclose [夹持力]        闭合夹爪，默认夹持力50
  gopening <开度>        设置夹爪开度（0~100）
  grotate <角度>         旋转夹爪

移液器：
  pz <高度>              移动移液器Z轴
  tip <吸头编号>         仅登记吸头已安装，不检测实物
  tipeject               执行退吸头
  aspirate <uL>          吸液
  dispense [uL]          排液；省略体积时排出软件记录的全部液体

旋涂仪：
  shome                  旋涂仪回玻璃原点
  spin <转速> <秒> <加速度>  执行单段旋涂配方

真空腔盖：
  coveropen / coverclose 打开或关闭真空腔盖

阀门：
  vopen / vclose         打开或关闭阀门

调度方案（不执行设备动作）：
  dry --algorithm <算法> [参数]    计算并打印完整方案
  gantt --algorithm <算法> [参数]  计算方案并显示文本甘特图
  dry --help                      显示调度参数

  help                   显示帮助
  q | quit               关闭连接并退出"""
    )


def _print_result(result: ActionResult) -> None:
    """Print an operation result, including its error and measurement details."""
    if result.success:
        suffix = f"：{result.measurements}" if result.measurements else ""
        print(f"完成 - {result.message}{suffix}")
    else:
        print(f"失败 [{result.error_code}] - {result.message}")


def _print_snapshot(value: MotionSnapshot) -> None:
    """Print the current motion positions, offsets, sensor readings, and system state."""
    print(
        f"X: 逻辑={value.logical_x:.3f}, 原始={value.raw_x:.3f}, "
        f"偏移={value.offset_x:.3f}, 传感器={'触发' if value.sensor_x_triggered else '未触发'} "
        f"({value.sensor_x_mv:.2f} mV)"
    )
    print(
        f"Y: 逻辑={value.logical_y:.3f}, 原始={value.raw_y:.3f}, "
        f"偏移={value.offset_y:.3f}, 传感器={'触发' if value.sensor_y_triggered else '未触发'} "
        f"({value.sensor_y_mv:.2f} mV)"
    )


def _print_device_states(controller: DeviceDiagnosticsController) -> None:
    """Print lifecycle, activity, measurements, and fault information for each device."""
    for name, state in controller.device_states().items():
        fault = f", 故障={state.fault}" if state.fault else ""
        print(
            f"{name}: 生命周期={state.lifecycle}, 活动={state.activity}, "
            f"数据={state.measurements}{fault}"
        )


def _sensor_reading(
    controller: DeviceDiagnosticsController, axis: Axis
) -> ActionResult:
    """Read and format the selected position sensor for diagnostic output."""
    voltage = controller.sensor.read_voltage(axis)
    triggered = controller.sensor.is_triggered(axis)
    return ActionResult.done(
        f"{axis.upper()} sensor read",
        {"axis": axis, "triggered": triggered, "voltage_mv": voltage},
    )


def _set_offset(
    controller: DeviceDiagnosticsController, axis: Axis, value: float
) -> ActionResult:
    """Validate a diagnostic offset command and update the selected stage axis."""
    controller.stage.set_offset(axis, value)
    marked = controller.stage.mark_at_origin(False)
    if not marked.success:
        return marked
    return ActionResult.done(
        f"{axis.upper()} offset updated", {f"offset_{axis}": value}
    )


def _move_raw(
    controller: DeviceDiagnosticsController, axis: Axis, raw_target: float
) -> ActionResult:
    """Parse a diagnostic movement command and move without applying the stage offset."""
    return controller.stage.move_axis_raw(axis, raw_target)


def execute_command(controller: DeviceDiagnosticsController, line: str) -> bool:
    """Execute one operator command. Return False when the session should exit."""
    parts = shlex.split(line)
    if not parts:
        return True
    command = parts[0].lower()
    if command in {"dry", "gantt"}:
        from integrated_control.application.scheduler.cli import main as scheduler_cli
        try:
            scheduler_cli([command, *parts[1:]])
        except SystemExit:
            # argparse help/errors must not terminate the diagnostic session.
            pass
        return True
    if command in {"q", "quit", "exit"}:
        return False
    if command in {"help", "?"}:
        _print_help()
        return True
    if command in {"p", "status"}:
        _print_snapshot(controller.snapshot())
        _print_device_states(controller)
        return True

    no_arg_actions = {
        "sx": lambda: _sensor_reading(controller, "x"),
        "sy": lambda: _sensor_reading(controller, "y"),
        "homex": lambda: controller.home_axis("x"),
        "homey": lambda: controller.home_axis("y"),
        "home": controller.home_xy,
        "saveoffset": controller.save_stage_offsets,
        "resetx": lambda: _set_offset(controller, "x", 0.0),
        "resety": lambda: _set_offset(controller, "y", 0.0),
        "gopen": controller.gripper.open,
        "tipeject": controller.pipette.eject_tip,
        "shome": controller.spin_coater.home,
        "coveropen": controller.vacuum_station.open_cover,
        "coverclose": controller.vacuum_station.close_cover,
        "vopen": controller.valve.open,
        "vclose": controller.valve.close,
    }
    if command in no_arg_actions:
        if len(parts) != 1:
            raise ValueError(f"{command} 不需要参数")
        _print_result(no_arg_actions[command]())
        return True

    one_arg_actions = {
        "mx": lambda value: controller.stage.move_axis("x", value),
        "my": lambda value: controller.stage.move_axis("y", value),
        "jx": lambda value: controller.stage.jog("x", value),
        "jy": lambda value: controller.stage.jog("y", value),
        "rx": lambda value: _move_raw(controller, "x", value),
        "ry": lambda value: _move_raw(controller, "y", value),
        "setx": lambda value: _set_offset(controller, "x", value),
        "sety": lambda value: _set_offset(controller, "y", value),
        "gz": controller.gripper.move_z,
        "gopening": controller.gripper.set_opening,
        "grotate": controller.gripper.rotate,
        "pz": controller.pipette.move_z,
        "aspirate": controller.pipette.aspirate,
    }
    if command in one_arg_actions:
        if len(parts) != 2:
            raise ValueError(f"{command} 需要一个数值参数")
        _print_result(one_arg_actions[command](float(parts[1])))
        return True
    if command == "gclose":
        if len(parts) > 2:
            raise ValueError("gclose 最多需要一个夹持力参数")
        force = 50.0 if len(parts) == 1 else float(parts[1])
        _print_result(controller.gripper.close(force))
        return True
    if command == "tip":
        if len(parts) != 2:
            raise ValueError("tip 需要一个吸头编号")
        _print_result(controller.pipette.attach_tip(parts[1]))
        return True
    if command == "dispense":
        if len(parts) > 2:
            raise ValueError("dispense 最多需要一个体积参数")
        volume = None if len(parts) == 1 else float(parts[1])
        _print_result(controller.pipette.dispense(volume))
        return True
    if command == "mxy":
        if len(parts) != 3:
            raise ValueError("mxy 需要 X 和 Y 两个数值参数")
        _print_result(controller.stage.move_xy(float(parts[1]), float(parts[2])))
        return True
    if command == "spin":
        if len(parts) != 4:
            raise ValueError("spin 需要转速、持续秒数和加速度三个数值参数")
        step = SpinStep(
            rpm=int(parts[1]),
            duration_s=float(parts[2]),
            acceleration_rpm_s=float(parts[3]),
        )
        _print_result(controller.spin_coater.run([step]))
        return True
    raise ValueError(f"未知命令: {command}")


def main() -> int:
    """Parse command-line arguments and run the diagnostics cli entry point."""
    args = _parser().parse_args()
    if args.command is not None:
        from integrated_control.application.scheduler.cli import main as scheduler_cli
        return scheduler_cli([args.command, *args.scheduler_args])
    selected_mode = args.mode
    try:
        controller = build_device_diagnostics(mode=selected_mode)
        backend = controller.stage.get_state().measurements.get("backend")
        if selected_mode in HARDWARE_MODES or backend == "native":
            print("警告：即将连接真实设备。请确认急停可用、运动范围内无人和障碍物。")
            print("确认后将连接全部调试设备；夹爪和移液器可能立即回零。")
            if input("输入 MOVE 继续：").strip() != "MOVE":
                print("已取消。")
                return 2
        initialized = controller.initialize()
    except ConfigurationError as exc:
        print(f"配置错误：{exc}")
        return 2
    except Exception as exc:
        print(f"连接失败：{exc}")
        return 1
    if not initialized.success:
        _print_result(initialized)
        return 1

    print(
        "全部调试设备已连接。平台和旋涂仪不会自动回零；"
        "夹爪和移液器初始化可能执行各自的回零动作。"
    )
    _print_help()
    try:
        while True:
            try:
                if not execute_command(controller, input("> ").strip()):
                    break
            except (ValueError, RuntimeError) as exc:
                print(f"命令错误：{exc}")
            except Exception as exc:
                print(f"设备操作失败：{exc}")
    except (KeyboardInterrupt, EOFError):
        print("\n用户中断。")
    finally:
        _print_result(controller.shutdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
