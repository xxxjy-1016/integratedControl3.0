# -*- coding: utf-8 -*-
"""批量 zksz 制备：用调度器（scheduler）的排程结果驱动主程序设备。

这是 scheduler 子项目与主程序（integrated_control）之间的集成层，职责：
  1. 从主程序配置（coordinates.yaml 的玻璃槽位 / 加热工位）推导调度参数；
  2. 调用 scheduler.glass_heat_scheduler.solve 生成 step1/step2 计划；
  3. 把 ZkszWorkflow 的 step1/step2 作为黑盒执行函数注入 scheduler.run_plan，
     按计划时刻批量制备产品。

step1 / step2 语义（与调度器模型对齐）：
  step1(n, m) = 制备第 n 片玻璃（取料 -> 旋涂 -> 真空闪蒸）并放到第 m 个加热器；
  step2(n, m) = 从第 m 个加热器取第 n 片玻璃，放回原料台。
退火等待（在台时间）落在 step1 结束与 step2 开始之间，由调度器统一安排。
"""

from __future__ import annotations

import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from integrated_control.application.workflows.zksz import ZkszWorkflow
from integrated_control.bootstrap import ApplicationContext


@dataclass(frozen=True)
class BatchParams:
    """批量制备的调度参数（与 scheduler.Params 一一对应）。

    num_heater / num_glass 为 None 时从主程序配置自动推导：
      num_heater <- coordinates.yaml 的 stations.heater 工位数；
      num_glass  <- coordinates.yaml 的 glass_platform.slots 槽位数。
    """

    time_step1: float = 100.0  # step1（制备 + 上加热台）估算耗时（秒）
    time_step2: float = 20.0  # step2（下加热台 + 放回）估算耗时（秒）
    heat_time_min: float = 1200.0  # 退火在台时间下界（秒）
    heat_time_max: float = 1210.0  # 退火在台时间上界（秒）
    num_heater: int | None = None  # 加热器数量；None = 自动推导
    num_glass: int | None = None  # 玻璃片总数；None = 自动推导
    heat_measure: str = "until_pickup"
    method: str = "auto"
    beam_width: int = 800
    time_limit: float = 30.0


def _load_scheduler(project_root: Path):
    """加载 scheduler 子项目（独立目录，不在主程序 src 包内）。"""
    root = str(project_root)
    if root not in sys.path:
        sys.path.insert(0, root)
    from scheduler import glass_heat_scheduler, run_plan

    return glass_heat_scheduler, run_plan


def _build_params_dict(
    application: ApplicationContext,
    batch: BatchParams,
) -> dict[str, Any]:
    """从主程序配置 + BatchParams 推导 scheduler.Params 的构造参数。"""
    coordinates = application.coordinates
    if batch.num_glass is None:
        num_glass = len(coordinates.get("glass_platform", {}).get("slots", []))
    else:
        num_glass = batch.num_glass
    if batch.num_heater is None:
        num_heater = len(coordinates.get("stations", {}).get("heater", []))
    else:
        num_heater = batch.num_heater

    return {
        "time_step1": batch.time_step1,
        "time_step2": batch.time_step2,
        "heat_time_min": batch.heat_time_min,
        "heat_time_max": batch.heat_time_max,
        "num_heater": num_heater,
        "num_glass": num_glass,
        "heat_measure": batch.heat_measure,
    }


def run_batch_zksz(
    application: ApplicationContext,
    *,
    batch: BatchParams | None = None,
    mode: str = "simulate",
    log_path: str | None = None,
    sleep: Callable[[float], None] | None = None,
):
    """批量制备入口：排程并执行 zksz 批量工艺。

    mode:
      "simulate"  用调度器内置物理校验模拟器重放计划（不驱动设备，快速验证排程）；
      "realtime"  把 ZkszWorkflow 的 step1/step2 注入执行器，按真实时钟驱动设备；
      "dry"       只打印指令序列，不执行。

    sleep: 注入给 ZkszWorkflow 的休眠函数（默认 time.sleep）。测试/台架联调时
    可传入 lambda _s: None 跳过工艺内的等待，加快验证。

    返回 scheduler 的 Plan 对象（含 makespan / feasible / commands 等），
    调用方据此判断成败。
    """
    batch = batch or BatchParams()
    glass_heat_scheduler, run_plan = _load_scheduler(application.project_root)

    params = glass_heat_scheduler.Params(**_build_params_dict(application, batch))
    plan = glass_heat_scheduler.solve(
        params,
        method=batch.method,
        beam_width=batch.beam_width,
        time_limit=batch.time_limit,
    )

    print(glass_heat_scheduler._format_report(plan))

    if not plan.feasible:
        return plan

    if mode == "realtime":
        workflow = ZkszWorkflow(application, sleep=sleep or time.sleep)
        run_plan.execute_plan(
            plan,
            workflow.step1,
            workflow.step2,
            mode=mode,
            log_path=log_path,
        )
    else:
        run_plan.execute_plan(plan, None, None, mode=mode, log_path=log_path)

    return plan
