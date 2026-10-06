# -*- coding: utf-8 -*-
"""独立暴力求解器：用于交叉验证 glass_heat_scheduler 的 exact 分支是否真最优。

与被测程序完全独立：
  * 枚举所有 step1/step2 的交错类型序列（Catalan 数个）
  * 每个 step2 枚举"取哪一片"的所有可能，不假设 EDF
  * 每个 step1 枚举"放哪个加热器"的所有可能
  * 固定序列后按最早可行时刻调度（延迟无益）
只支持小规模（N <= 6）。
"""
from itertools import permutations
from typing import List, Optional, Tuple

EPS = 1e-9


def brute_force(num_glass: int, num_heater: int, time_step1: float, time_step2: float,
                heat_time_min: float, heat_time_max: float,
                heat_measure: str = "until_pickup"):
    tail = time_step2 if heat_measure == "including_pickup" else 0.0
    best = float("inf")
    best_seq = None

    def rec(t, seq, placed, on_heater, free_heaters, done):
        """on_heater: tuple of (glass, heater, put_end)，按 put_end 升序"""
        nonlocal best, best_seq
        if len(done) == num_glass:
            if t < best - EPS:
                best, best_seq = t, list(seq)
            return
        if t >= best - EPS:
            return

        # --- 选项 1: step1(下一片未放的, 某个空闲加热器) ---
        if placed < num_glass and free_heaters:
            for m in free_heaters:
                end = t + time_step1
                nh = tuple(sorted(list(on_heater) + [(placed, m, end)], key=lambda x: x[2]))
                nf = [x for x in free_heaters if x != m]
                rec(end, seq + [(1, placed, m, t)],
                    placed + 1, nh, nf, done)

        # --- 选项 2: step2(取某片, m=它所在的加热器) ---
        for (g, m, pe) in on_heater:
            start = max(t, pe + heat_time_min - tail)
            heat = (start + tail) - pe
            if heat > heat_time_max + EPS:
                continue
            nh = tuple(x for x in on_heater if x[0] != g)
            nf = sorted(free_heaters + [m])
            rec(start + time_step2, seq + [(2, g, m, start)],
                placed, nh, nf, done | {g})

    rec(0.0, [], 0, (), list(range(1, num_heater + 1)), frozenset())
    return best, best_seq


if __name__ == "__main__":
    # 自测：几个手工可推的用例
    # 用例1: N=1，任何参数 —— 必然是 a + hmin + b
    print(brute_force(1, 1, 2.0, 1.0, 5.0, 12.0))
    # 用例2: H=1, N=3, a=b=1, hmin=2 —— 单加热器完全串行，每片占 1+2+1=4，共 12
    print("expect 12.0 ->", brute_force(3, 1, 1.0, 1.0, 2.0, 9.0)[0])
    # 用例3: H 很大，N=3, a=1, b=1, hmin=1, hmax=100 —— 机械臂满负荷 3*2=6
    print("expect 6.0 ->", brute_force(3, 4, 1.0, 1.0, 1.0, 100.0)[0])
