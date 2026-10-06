# -*- coding: utf-8 -*-
"""
执行器：调用 glass_heat_scheduler 求解，然后把 plan 里的指令逐条发给机械臂。

step1 / step2 两个函数来自外部库（黑盒，本文件不关心其内部实现，只负责调用）：
    step1(n, m)  取第 n 个玻璃片，放到第 m 个加热器上
    step2(n, m)  从第 m 个加热器上取第 n 个玻璃片，放回第 n 号位置

外部库的定位方式（按优先级）：
    1. 命令行 --robot-lib 模块名
    2. 环境变量 ROBOT_LIB
    3. 默认模块名 "robot_lib"
要求该模块暴露可调用的 step1(n, m) 与 step2(n, m)。
注意：外部 step1/step2 应当各自阻塞 time_step1 / time_step2 秒（真实硬件控制库
的常见行为）。若它们立即返回，实时模式仍会按计划时刻派发，但无法监控漂移。

三种运行模式（默认 simulate，绝不误触真实硬件）：
  --mode dry       只打印将要执行的指令序列，不调用任何函数
  --mode simulate  用 glass_heat_scheduler 内置的物理校验模拟器逐步执行
                   （step1/step2 用库内自带版本，全程校验硬约束，无需外部库）
  --mode realtime  按真实时钟把指令派发给外部库的 step1/step2。
                   带漂移监控：执行滞后会向后传播，一旦继续执行将使某片玻璃
                   超过 heat_time_max，立即中止（宁可停机，不烧玻璃）。

用法：
    python run_plan.py                          # 求解 + 模拟执行
    python run_plan.py --mode dry               # 只看指令序列
    python run_plan.py --mode realtime          # 真实执行（先确认外部库就绪）
    python run_plan.py -c my.json --mode realtime --robot-lib my_robot

退出码：0 成功；2 配置/参数错误；3 执行中安全中止。
"""

from __future__ import annotations

import argparse
import importlib
import math
import os
import sys
import time

try:  # 作为 scheduler 包的一部分被主程序导入时
    from . import glass_heat_scheduler as G
except ImportError:  # 在 scheduler 目录内直接运行（python run_plan.py）
    import glass_heat_scheduler as G

DEFAULT_ROBOT_LIB = os.environ.get("ROBOT_LIB", "robot_lib")
COUNTDOWN_SEC = 3.0


# --------------------------------------------------------------------------- #
# 外部库加载
# --------------------------------------------------------------------------- #

def load_external_steppers(lib_name: str):
    """从外部库拿 step1 / step2。只检查"存在且可调用"，不关心内部实现。"""
    try:
        mod = importlib.import_module(lib_name)
    except ImportError as e:
        raise SystemExit(
            f"[致命] 找不到机械臂控制库 '{lib_name}'（{e}）。\n"
            f"       请把它装好并放到 import 路径上，或用 --robot-lib / 环境变量 "
            f"ROBOT_LIB 指定模块名。先用 --mode simulate 验证流程也可以。")
    fn1, fn2 = getattr(mod, "step1", None), getattr(mod, "step2", None)
    if not callable(fn1) or not callable(fn2):
        raise SystemExit(f"[致命] 模块 '{lib_name}' 没有暴露可调用的 step1(n, m) / step2(n, m)。")
    return fn1, fn2


# --------------------------------------------------------------------------- #
# 漂移预算：每条指令最多允许滞后多少秒而不违反 heat_time_max
# --------------------------------------------------------------------------- #

def drift_budgets(plan: G.Plan):
    """反向递推计算每条指令的"可滞后预算" A[k]。

    第 k 条指令若滞后 d 秒开始（其余按计划推进），空档 idle_{k+1} 会吸收一部分，
    传到第 k+1 条时剩余滞后为 max(0, d - idle_{k+1})。于是：
        A[k] = min( 自身截止余量 , A[k+1] + max(0, idle_{k+1}) )
    自身截止余量只对 step2 存在：
        最新可取时刻 = end(step1) + heat_time_max - tail，减去计划开始时刻。
    """
    p = plan.params
    cmds = plan.commands
    put_end = {c.n: c.end for c in cmds if c.kind == "step1"}
    own = [math.inf] * len(cmds)
    for i, c in enumerate(cmds):
        if c.kind == "step2":
            latest = put_end[c.n] + p.heat_time_max - p.tail
            own[i] = max(0.0, latest - c.t)
    budgets = [0.0] * len(cmds)
    budgets[-1] = own[-1]
    for k in range(len(cmds) - 2, -1, -1):
        idle = max(0.0, cmds[k + 1].t - cmds[k].end)
        budgets[k] = min(own[k], budgets[k + 1] + idle)
    return budgets


# --------------------------------------------------------------------------- #
# 三种执行模式
# --------------------------------------------------------------------------- #

def run_dry(plan: G.Plan) -> int:
    print("\n[dry-run] 以下指令按时间顺序执行（本次不调用任何函数）：")
    for i, c in enumerate(plan.commands):
        fn = "step1" if c.kind == "step1" else "step2"
        print(f"  #{i:>2}  t={c.t:9.3f}  {fn}(n={c.n}, m={c.m})   "
              f"[{c.t:9.3f}, {c.end:9.3f}]")
    print(f"共 {len(plan.commands)} 条指令，makespan={plan.makespan:.3f}")
    return 0


def run_simulate(plan: G.Plan) -> int:
    """用库内自带 step1/step2 逐步重放，等效于把外部调用过一遍完整物理校验。"""
    ctx = G.configure(plan.params)
    print("\n[simulate] 用内置模拟器执行（每条指令都经过物理约束校验）：")
    for i, c in enumerate(plan.commands):
        ctx.clock = c.t
        fn = G.step1 if c.kind == "step1" else G.step2
        try:
            fn(c.n, c.m)
        except G.RobotError as e:
            print(f"  #{i:>2}  t={c.t:9.3f}  {c.kind}(n={c.n}, m={c.m})  ->  "
                  f"校验失败：{e}", file=sys.stderr)
            print(f"[中止] 模拟执行在第 {i} 条指令处失败，plan 不应被下发。", file=sys.stderr)
            return 3
        print(f"  #{i:>2}  t={c.t:9.3f}  {c.kind}(n={c.n}, m={c.m})  ok")
    print(f"[simulate] 全部 {len(plan.commands)} 条指令执行成功，约束全部满足。")
    return 0


def execute_plan(
    plan: G.Plan,
    step1,
    step2,
    *,
    mode: str = "simulate",
    log_path: str | None = None,
) -> int:
    """按计划执行，step1 / step2 由调用方直接注入（可调用对象）。

    这是调度器暴露给主程序（integrated_control）的**推荐集成入口**：主程序把
    绑定好设备上下文的 zksz step1/step2 传进来即可，无需把外部库做成可 import
    的模块。

    mode:
      "dry"       只打印指令序列，不调用任何函数；
      "simulate"  用调度器内置物理校验模拟器逐步重放（不调用传入的 step1/step2）；
      "realtime"  按真实时钟调用传入的 step1/step2，带漂移安全中止。
    """
    if mode == "dry":
        return run_dry(plan)
    if mode == "simulate":
        return run_simulate(plan)
    return _run_realtime(plan, step1, step2, log_path)


def run_realtime(plan: G.Plan, lib_name: str, log_path: str | None = None) -> int:
    """按真实时钟把计划派发给外部库的 step1/step2（通过模块名加载）。

    如需直接注入可调用对象（例如主程序把绑定好设备上下文的 step1/step2
    传进来），请改用 execute_plan()。
    """
    step1, step2 = load_external_steppers(lib_name)
    return _run_realtime(plan, step1, step2, log_path)


def _run_realtime(plan: G.Plan, step1, step2, log_path: str | None) -> int:
    """run_realtime 的核心：按计划时刻调用已注入的 step1/step2 可调用对象。

    step1/step2 必须满足调度器的黑盒契约：
      - 同步阻塞调用，签名 (n, m) -> None；
      - 各自阻塞 time_step1 / time_step2 秒（真实硬件控制的常见行为）；
      - 若立即返回，实时模式仍按计划时刻派发，只是无法监控漂移。
    """
    budgets = drift_budgets(plan)
    cmds = plan.commands
    drift = 0.0
    log_lines: list[str] = []

    def log(msg: str) -> None:
        print(msg)
        log_lines.append(msg)

    src1 = f"{getattr(step1, '__module__', '?')}.{getattr(step1, '__name__', '?')}"
    src2 = f"{getattr(step2, '__module__', '?')}.{getattr(step2, '__name__', '?')}"
    log(f"\n[realtime] step1/step2 = {src1} / {src2}，{len(cmds)} 条指令，"
        f"makespan={plan.makespan:.3f}s，3 秒后开始（Ctrl+C 取消）")
    try:
        time.sleep(COUNTDOWN_SEC)
    except KeyboardInterrupt:
        log("[取消] 用户在倒计时阶段中止，未发出任何指令。")
        return 3

    # 执行时钟零点：倒计时结束后才起表，倒计时不计入漂移
    t0_wall = time.monotonic()

    for i, c in enumerate(cmds):
        # ---- 等到计划时刻 ----
        target = t0_wall + c.t
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        drift = max(drift, time.monotonic() - target)

        # ---- 漂移安全检查：继续执行是否会违反 heat_time_max ----
        budget = budgets[i]
        if drift > budget + 1e-9:
            log(f"  #{i:>2}  [安全中止] 当前滞后 {drift*1000:.0f}ms 超过本条预算 "
                f"{budget*1000:.0f}ms；若继续，玻璃片将在台超时。")
            log(f"[中止] 已执行 {i}/{len(cmds)} 条。请检查外部 step1/step2 是否按 "
                f"time_step1/time_step2 耗时，或放宽 heat_time_max 后重算。")
            _flush_log(log_path, log_lines)
            return 3
        if drift > 0.5 * budget and math.isfinite(budget):
            log(f"  #{i:>2}  [警告] 滞后 {drift*1000:.0f}ms，已达预算 "
                f"{budget*1000:.0f}ms 的一半")

        # ---- 调用外部黑盒函数 ----
        wall = time.strftime("%H:%M:%S")
        fn = step1 if c.kind == "step1" else step2
        log(f"  #{i:>2}  {wall}  {c.kind}(n={c.n}, m={c.m})"
            f"   计划 t={c.t:9.3f}  滞后={drift*1000:6.0f}ms")
        fn(c.n, c.m)

        # ---- 用调用返回后的真实时刻更新漂移 ----
        actual_end = time.monotonic()
        drift = max(drift, actual_end - (t0_wall + c.end))

    log(f"[realtime] 全部 {len(cmds)} 条指令执行完毕，最终滞后 {drift*1000:.0f}ms。")
    _flush_log(log_path, log_lines)
    return 0


def _flush_log(path: str | None, lines: list[str]) -> None:
    if not path:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"[提示] 执行日志已保存到 {path}")


# --------------------------------------------------------------------------- #
# 主流程：读配置 -> 求解 -> 执行
# --------------------------------------------------------------------------- #

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="执行器：调用 glass_heat_scheduler 求解，并按计划下发 step1/step2")
    ap.add_argument("--config", "-c", default=None,
                    help=f"JSON 配置（缺省用当前目录 {G.DEFAULT_CONFIG_NAME}）")
    ap.add_argument("--mode", choices=["dry", "simulate", "realtime"], default="simulate",
                    help="dry=只打印；simulate=内置模拟器；realtime=真实派发（默认 simulate）")
    ap.add_argument("--robot-lib", default=DEFAULT_ROBOT_LIB,
                    help="外部机械臂库的模块名（也可用环境变量 ROBOT_LIB）")
    ap.add_argument("--method", choices=["auto", "exact", "beam", "greedy"], default=None,
                    help="覆盖配置文件里的 solver.method")
    ap.add_argument("--log", default=None, help="执行日志保存路径")
    args = ap.parse_args(argv)

    # ---- 读配置（与主程序同一套加载与校验）----
    cfg_path = args.config or G.DEFAULT_CONFIG_NAME
    try:
        json_params, json_solver = G.load_config(cfg_path)
    except (OSError, ValueError) as e:
        print(f"[配置错误] {e}", file=sys.stderr)
        return 2
    p = G.Params(**{**G.Params().to_dict(), **json_params})

    method = args.method or json_solver.get("method", "auto")
    plan = G.solve(p, method=method,
                   beam_width=json_solver.get("beam_width", 800),
                   time_limit=json_solver.get("time_limit", 30.0))
    print(G._format_report(plan))
    if not plan.feasible:
        print("[拒绝执行] 计划未通过物理校验：", file=sys.stderr)
        for e in plan.errors:
            print(f"  - {e}", file=sys.stderr)
        return 2

    if args.mode == "dry":
        return run_dry(plan)
    if args.mode == "simulate":
        return run_simulate(plan)
    return run_realtime(plan, args.robot_lib, args.log)


if __name__ == "__main__":
    sys.exit(main())
