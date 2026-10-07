"""Offline planning and text visualization; never construct or operate devices."""
import argparse
import math
import json
from dataclasses import replace
from pathlib import Path

from .algorithm import AlgorithmConfig, schedule
from .contracts import TaskPlan
from .decision_preview import FifoPreview, OnlineTiming
from .experiment_manager import ExperimentManager
from .task_manager import TaskManager


def dry(*, num_glass: int, num_heater: int, timing: OnlineTiming,
        config: AlgorithmConfig) -> TaskPlan:
    """Compile the experiment once and plan every task without hardware I/O."""
    if type(num_glass) is not int or num_glass < 0:
        raise ValueError("num_glass must be a nonnegative integer")
    if type(num_heater) is not int or num_heater < 1:
        raise ValueError("num_heater must be a positive integer")
    manager = ExperimentManager(TaskManager())
    specs = manager.submit("zksz", {"experiment_id": "dry", "glass_ids": range(num_glass)})
    resources = {"arm": {"capacity": 1, "available": 1},
                 **{f"heater:{m}": {"capacity": 1, "available": 1}
                    for m in range(1, num_heater + 1)}}
    snapshot = {"resources": resources, "samples": {}}
    adapter = FifoPreview(timing, clock=lambda: 0.0)
    models = [adapter.planning_model(spec, snapshot) for spec in specs]
    capacities, available = adapter.planning_capacities(snapshot)
    # No current-step restriction: dry is a full predictive plan and may idle.
    return schedule(models, capacities, config, horizon=None, initial_available=available)


def format_dry(plan: TaskPlan) -> str:
    """Format feasibility, search metadata, and planned task timings for dry output."""
    lines = [f"[dry] algorithm={plan.method} feasible={plan.feasible} "
             f"optimal={plan.proven_optimal} timed_out={plan.timed_out}",
             f"tasks={len(plan.commands)} makespan={plan.makespan:.3f}s"]
    for i, command in enumerate(plan.commands):
        lines.append(f"  #{i:>3} {command.task_id:<24} "
                     f"[{command.start:10.3f}, {command.end:10.3f}] "
                     f"duration={command.end - command.start:.3f}s")
    lines.extend(f"  error: {error}" for error in plan.errors)
    return "\n".join(lines)


def gantt(plan: TaskPlan, cols: int = 92) -> str:
    """Render generic TaskPlan task lanes; half-open intervals avoid overlap."""
    if type(cols) is not int or cols < 20 or cols > 240:
        raise ValueError("Gantt width must be an integer between 20 and 240")
    if not plan.commands:
        return "(空计划)" if plan.feasible else "(无可行方案，无法绘制甘特图)"
    origin = min(0.0, plan.commands[0].start)
    end = max(command.end for command in plan.commands)
    span = max(end - origin, 1e-9)
    axis = [" "] * cols
    tick_count = max(1, min(6, cols // (len(f"{end:.1f}") + 3)))
    for k in range(tick_count + 1):
        label = f"{origin + span * k / tick_count:.1f}"
        position = min(int(k / tick_count * (cols - 1)), cols - len(label))
        if position >= 0:
            axis[position:position + len(label)] = label
    labels = [command.task_id for command in plan.commands]
    padding = max(len(label) for label in labels)
    lines = [f"[gantt] 时间单位：秒；# = 执行，. = 空闲；makespan={plan.makespan:.3f}s",
             " " * (padding + 1) + "".join(axis)]
    for command in plan.commands:
        start_col = max(0, min(cols - 1, int((command.start - origin) / span * cols)))
        end_col = min(cols, max(start_col + 1, math.ceil((command.end - origin) / span * cols)))
        lane = ["."] * cols
        lane[start_col:end_col] = ["#"] * (end_col - start_col)
        lines.append(f"{command.task_id:<{padding}} " + "".join(lane))
    return "\n".join(lines)


def _parser():
    """Build the command-line parser for this entry point."""
    parser = argparse.ArgumentParser(description="离线方案计算与文本甘特图（不连接设备）")
    parser.add_argument("command", choices=("dry", "gantt"))
    parser.add_argument("--algorithm", choices=("fifo", "greedy", "exact", "beam", "auto"), required=True)
    parser.add_argument("--batch-config", help="JSON BatchParams；命令行工艺参数覆盖配置")
    parser.add_argument("--num-glass", type=int)
    parser.add_argument("--num-heater", type=int)
    parser.add_argument("--step1-s", type=float)
    parser.add_argument("--step2-s", type=float)
    parser.add_argument("--heat-min-s", type=float)
    parser.add_argument("--heat-max-s", type=float)
    parser.add_argument("--put-offset-min-s", type=float)
    parser.add_argument("--put-offset-max-s", type=float)
    parser.add_argument("--pickup-offset-min-s", type=float,
                        help="Required: minimum seconds from step2 start to the actual pickup event")
    parser.add_argument("--pickup-offset-max-s", type=float,
                        help="Required: maximum seconds from step2 start to the actual pickup event")
    parser.add_argument("--pickup-margin-s", type=float, default=0.0)
    parser.add_argument("--beam-width", type=int)
    parser.add_argument("--time-limit-s", type=float)
    parser.add_argument("--exact-task-limit", type=int, default=8)
    parser.add_argument("--cols", type=int, default=92)
    parser.add_argument("--gantt", action="store_true", help="dry 输出后附带甘特图")
    return parser


def main(argv=None) -> int:
    """Parse command-line arguments and run the cli entry point."""
    args = _parser().parse_args(argv)
    try:
        from ..workflows.batch_zksz import BatchParams
        batch = (BatchParams(**json.loads(Path(args.batch_config).read_text(encoding="utf-8")))
                 if args.batch_config else BatchParams(2, 1, 5, 12, 3, 8, beam_width=200, time_limit=1))
        overrides = {name: value for name, value in {
            "num_glass": args.num_glass, "num_heater": args.num_heater,
            "time_step1": args.step1_s, "time_step2": args.step2_s,
            "heat_time_min": args.heat_min_s, "heat_time_max": args.heat_max_s,
            "beam_width": args.beam_width, "time_limit": args.time_limit_s}.items() if value is not None}
        batch = replace(batch, **overrides, method=args.algorithm)
        if batch.num_glass is None or batch.num_heater is None:
            raise ValueError("dry requires explicit num_glass/num_heater in config or flags")
        if args.pickup_offset_min_s is None or args.pickup_offset_max_s is None:
            raise ValueError(
                "dry requires explicit --pickup-offset-min-s and --pickup-offset-max-s")
        if not 20 <= args.cols <= 240:
            raise ValueError("--cols must be between 20 and 240")
        timing = OnlineTiming(batch.time_step1, batch.time_step2, batch.heat_time_min, batch.heat_time_max,
            batch.time_step1 if args.put_offset_min_s is None else args.put_offset_min_s,
            batch.time_step1 if args.put_offset_max_s is None else args.put_offset_max_s,
            args.pickup_offset_min_s, args.pickup_offset_max_s, args.pickup_margin_s)
        config = AlgorithmConfig(args.algorithm, batch.beam_width, batch.time_limit,
                                 args.exact_task_limit)
        plan = dry(num_glass=batch.num_glass, num_heater=batch.num_heater, timing=timing, config=config)
    except (ValueError, TypeError, OSError) as exc:
        print(f"调度参数错误：{exc}")
        return 2
    print(format_dry(plan))
    if args.command == "gantt" or args.gantt:
        print(gantt(plan, args.cols))
    return 0 if plan.feasible else 1


if __name__ == "__main__":
    raise SystemExit(main())
