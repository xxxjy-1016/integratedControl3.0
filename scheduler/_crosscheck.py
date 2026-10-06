# -*- coding: utf-8 -*-
"""交叉验证 harness：
  * 随机小实例 + 手工边界实例，与独立暴力解逐一对拍
  * 校验 exact 的最优性声明、beam/greedy 不低于暴力解、下界恒不超最优
  * 可行实例：三个方法都必须给出通过 verify 的调度
  * 不可行实例（暴力 = inf）：exact/beam 必须报告无解，greedy 必须被 verify 判为不可行
"""
import random
import sys

import glass_heat_scheduler as G
from _bruteforce_ref import brute_force

random.seed(20261005)
fails = 0
rows = []

CASES = []
# ---- 随机扫描（两种口径都覆盖）----
for _ in range(80):
    _hmin = round(random.uniform(0.0, 6.0), 2)
    _hmax = round(_hmin + random.uniform(0.0, 9.0), 2)   # 松弛范围放宽，会自然产生不可行实例
    CASES.append(G.Params(
        time_step1=round(random.uniform(0.5, 3.0), 2),
        time_step2=round(random.uniform(0.5, 3.0), 2),
        heat_time_min=_hmin,
        heat_time_max=_hmax,
        num_heater=random.randint(1, 3),
        num_glass=random.randint(1, 5),
        heat_measure=random.choice(["until_pickup", "including_pickup"]),
    ))
# ---- 手工边界 ----
extra = [
    G.Params(2.0, 1.0, 0.0, 0.0, 1, 4),        # 零加热窗
    G.Params(1.0, 1.0, 5.0, 5.0, 2, 4),        # 零松弛
    G.Params(1.0, 4.0, 2.0, 2.0, 1, 3),        # step2 极长 + 零松弛
    G.Params(4.0, 1.0, 3.0, 3.0, 3, 5),        # step1 极长 + 零松弛
    G.Params(1.0, 1.0, 0.0, 50.0, 5, 5),       # 加热器远多于玻璃片
    G.Params(1.5, 2.5, 1.0, 30.0, 2, 6),
    G.Params(1.0, 1.0, 10.0, 10.0, 2, 2),
    G.Params(1.0, 1.0, 0.5, 0.6, 1, 2),        # hmin < b（including_pickup 下可立即取）
    G.Params(0.5, 0.5, 3.0, 3.2, 2, 6),
    G.Params(1.0, 1.0, 1.0, 1.5, 2, 4),        # 强约束
    G.Params(1.0, 3.0, 2.0, 3.0, 2, 6),        # 对抗实例：裸贪心曾在此违规（整链护栏的回归用例）
    G.Params(1.0, 3.0, 2.0, 3.0, 2, 8),        # 同型放大
    G.Params(2.0, 1.0, 5.0, 6.0, 2, 7),        # 松弛=1 的紧约束
]
CASES.extend(extra)

n_infeasible = 0
for i, p in enumerate(CASES):
    bf, _ = brute_force(p.num_glass, p.num_heater, p.time_step1, p.time_step2,
                        p.heat_time_min, p.heat_time_max, p.heat_measure)
    lb = G.global_lower_bound(p)

    plans = {}
    problems = []
    for m in ("exact", "beam", "greedy"):
        try:
            plans[m] = G.solve(p, method=m, beam_width=400)
        except Exception as e:                          # noqa: BLE001
            problems.append(f"{m} 抛异常: {type(e).__name__}: {e}")

    if bf < float("inf"):
        # ---- 可行实例 ----
        pe, pb, pg = plans.get("exact"), plans.get("beam"), plans.get("greedy")
        if pe is None or pb is None or pg is None:
            problems.append("有求解器缺结果")
        else:
            if not pe.feasible:
                problems.append(f"exact 报不可行: {pe.errors}")
            elif abs(pe.makespan - bf) > 1e-6:
                problems.append(f"exact={pe.makespan:.4f} != 暴力={bf:.4f}")
            if not pe.proven_optimal:
                problems.append("exact 未标记已证明最优")
            if pb.makespan < bf - 1e-6:
                problems.append(f"beam={pb.makespan:.4f} < 暴力={bf:.4f}（不可能）")
            if not pb.feasible:
                problems.append(f"beam 不可行: {pb.errors}")
            # greedy 是 O(N) 基线，紧约束下允许违规，但若自称可行则不得快过最优
            if pg.feasible and pg.makespan < bf - 1e-6:
                problems.append(f"greedy={pg.makespan:.4f} < 暴力={bf:.4f}（不可能）")
            if lb > bf + 1e-6:
                problems.append(f"下界 {lb:.4f} > 暴力最优 {bf:.4f}（下界无效）")
        rows.append((i, p, bf, lb,
                     pe.makespan if pe else None,
                     pb.makespan if pb else None,
                     pg.makespan if (pg and pg.feasible) else None))
    else:
        # ---- 不可行实例 ----
        n_infeasible += 1
        pe, pb, pg = plans.get("exact"), plans.get("beam"), plans.get("greedy")
        if pe is not None and pe.feasible:
            problems.append("暴力判不可行，但 exact 给出了'可行'解")
        if pe is not None and not pe.feasible and not pe.errors:
            problems.append("exact 报不可行却没有诊断信息")
        if pb is not None and pb.feasible:
            problems.append("暴力判不可行，但 beam 给出了'可行'解")
        if pg is not None and pg.feasible:
            problems.append("暴力判不可行，但 greedy 的解竟通过了 verify")
        rows.append((i, p, None, lb, None, None, None))

    if problems:
        fails += 1
        print(f"[FAIL] #{i} {p}")
        for x in problems:
            print("       ", x)

print()
print(f"{'#':>3} {'暴力最优':>10} {'下界':>10} {'exact':>10} {'beam':>10} {'greedy':>10}")
for r in rows[:15]:
    def f(v):
        return f"{v:>10.3f}" if v is not None else f"{'不可行':>10}"
    print(f"{r[0]:>3} {f(r[2])} {f(r[3])} {f(r[4])} {f(r[5])} {f(r[6])}")
print("...")

n_beam_gap = sum(1 for r in rows if r[2] is not None and r[5] is not None and r[5] > r[2] + 1e-6)
n_greedy_gap = sum(1 for r in rows if r[2] is not None and r[6] is not None and r[6] > r[2] + 1e-6)
n_lb_tight = sum(1 for r in rows if r[2] is not None and abs(r[2] - r[3]) < 1e-6)
n_greedy_ok = sum(1 for r in rows if r[6] is not None)
n_feasible = sum(1 for r in rows if r[2] is not None)
print()
print(f"总用例 {len(rows)}   失败 {fails}   其中不可行实例 {n_infeasible}   可行实例 {n_feasible}")
print(f"beam 未达最优: {n_beam_gap}    greedy 未达最优: {n_greedy_gap}    下界恰好收紧: {n_lb_tight}")
print(f"greedy 在可行实例上给出合法解的比例: {n_greedy_ok}/{n_feasible}")
sys.exit(1 if fails else 0)
