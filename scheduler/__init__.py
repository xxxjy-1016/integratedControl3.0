# -*- coding: utf-8 -*-
"""机械臂玻璃片加热调度器（scheduler 子项目）。

以 Python 包的形式暴露给主程序（integrated_control）使用：

    from scheduler.glass_heat_scheduler import Params, solve
    from scheduler.run_plan import execute_plan

调度算法与执行器完全分离：
- `glass_heat_scheduler.solve` 只负责排程，返回 Plan；
- `run_plan.execute_plan` 负责按计划时刻调用外部提供的 step1/step2。

step1(n, m) / step2(n, m) 的语义由调用方（主程序 zksz 工艺）决定：
    step1(n, m)  制备第 n 片玻璃（取料 -> 旋涂 -> 真空闪蒸）并放到第 m 个加热器；
    step2(n, m)  从第 m 个加热器取第 n 片玻璃，放回原料台。
"""

__all__ = ["glass_heat_scheduler", "run_plan"]
