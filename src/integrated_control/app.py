"""Main entry point for the integrated control application."""
import argparse
import json
import sys
from pathlib import Path

from integrated_control.application.workflows import run_zksz, run_batch_zksz, BatchParams
from integrated_control.application.scheduler.algorithm import AlgorithmConfig
from integrated_control.application.scheduler.decision_preview import OnlineTiming
from integrated_control.bootstrap import build_application
from integrated_control.domain.errors import ConfigurationError


def _parser():
    """Build the command-line parser for this entry point."""
    parser = argparse.ArgumentParser(description="完整单片工艺或批量在线实验")
    parser.add_argument("--workflow", choices=("single", "batch"), default="single")
    parser.add_argument("--device-mode", choices=("simulation", "native_hardware", "hardware"))
    parser.add_argument("--algorithm", choices=("fifo", "greedy", "exact", "beam", "auto"))
    parser.add_argument("--batch-config", help="JSON BatchParams")
    parser.add_argument("--timing-config", help="JSON OnlineTiming，批量实验必填")
    parser.add_argument("--beam-width", type=int, default=200)
    parser.add_argument("--search-time-limit", type=float, default=0.05)
    parser.add_argument("--lookahead-depth", type=int,
                        help="限制在线搜索深度；省略时搜索全部剩余任务")
    parser.add_argument("--exact-task-limit", type=int, default=8)
    parser.add_argument("--log-path")
    return parser


def main(argv=None) -> int:
    """Parse command-line arguments and run the app entry point."""
    parser = _parser()
    args = parser.parse_args(argv)
    if args.workflow == "batch" and (not args.algorithm or not args.timing_config):
        parser.error("batch requires --algorithm and --timing-config")
    try:
        batch, timing, chosen = None, None, None
        if args.workflow == "batch":
            batch = (BatchParams(**json.loads(Path(args.batch_config).read_text(encoding="utf-8")))
                     if args.batch_config else BatchParams())
            timing = OnlineTiming(**json.loads(Path(args.timing_config).read_text(encoding="utf-8")))
            chosen = AlgorithmConfig(args.algorithm, args.beam_width, args.search_time_limit,
                                     args.exact_task_limit, args.lookahead_depth)
            if (batch.heat_time_min, batch.heat_time_max) != (timing.heat_min_s, timing.heat_max_s):
                raise ValueError("Batch heating window and timing window must match")
        application = build_application(mode=args.device_mode) if args.device_mode else build_application()
        if batch is not None:
            batch = batch.resolve(application.coordinates)
    except (ConfigurationError, ValueError, TypeError, OSError) as exc:
        print(f"配置错误：{exc}")
        return 2

    try:
        started = application.controller.start()
        if not started.success:
            print(f"设备初始化失败：{started.message}")
            return 1

        result = (run_zksz(application) if args.workflow == "single" else
                  run_batch_zksz(application, batch=batch, online_timing=timing,
                                 algorithm_config=chosen, log_path=args.log_path))
        if not result.success:
            message = result.message if args.workflow == "single" else "; ".join(result.errors)
            print(f"{args.workflow} 流程失败：{message}")
            return 1
        return 0
    except (ValueError, RuntimeError) as exc:
        print(f"实验执行失败：{exc}")
        return 1
    finally:
        application.controller.shutdown()


def batch_main(argv=None) -> int:
    """Console-script alias; lifecycle and CLI implementation stay in this module."""
    return main(["--workflow", "batch", *(sys.argv[1:] if argv is None else argv)])


if __name__ == "__main__":
    raise SystemExit(main())
