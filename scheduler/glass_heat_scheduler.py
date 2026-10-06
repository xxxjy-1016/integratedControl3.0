# -*- coding: utf-8 -*-
"""
================================================================================
机械臂玻璃片加热调度器  ( robotic-arm glass-sheet heating scheduler)
================================================================================

问题模型
--------
* 场景里有 num_glass 个玻璃片（编号 0 .. num_glass-1），num_heater 个加热器
  （编号 1 .. num_heater）。
* 一台机械臂（单一资源，同一时刻只能做一件事）。对每个玻璃片 n 必须依次执行：

      step1(n, m) : 取第 n 个玻璃片，放到第 m 个加热器上加热   耗时 time_step1
      step2(n, m) : 从第 m 个加热器上取第 n 个玻璃片，放回第 n 号位置 耗时 time_step2

* 约束
    C1 单机   ：所有 step1 / step2 操作在时间轴上互不重叠。
    C2 加热器 ：任一时刻压在加热器上的玻璃片数量 <= num_heater。
    C3 加热窗 ：玻璃片 n 的"在台时间"必须落在
                [heat_time_min, heat_time_max] 之内。
    C4 先后序 ：step1(n,m) 必须早于 step2(n,m)。

* 目标：最小化 makespan = 全部玻璃片"加热完并放回原位"的时刻。

关于"在台时间"的度量口径
------------------------
本程序把玻璃片视为在 step1 **结束**（机械臂松开）时落到加热器上，在 step2
**开始**（机械臂夹起）时离开加热器：

        在台时间 = start(step2) - end(step1)

如果工艺定义是"夹起来也算在台内"（在台时间 = end(step2) - end(step1)），
把 heat_measure 设为 "including_pickup" 即可，两种口径本程序都支持。

算法
====
1) 状态压缩
   玻璃片彼此完全同构（同样时长、同样加热窗、放回各自原位不影响目标），
   且 step2 的执行顺序可以证明"总取在台时间最长的那片"最优（EDF 交换论证）。
   因此整个调度只取决于 step1 / step2 的**类型序列**，搜索空间从
   (2N)! / (N!N!) 降到 Catalan 数级别；又因为
        release_i = end(step1_i) + heat_time_min
        deadline_i = end(step1_i) + heat_time_max
        deadline_i - release_i = heat_time_max - heat_time_min  (常量)
   所以状态可以进一步压缩成 (t, 在台时间队列 releases)，玻璃片编号与加热器
   编号留到回溯时再分配。

2) 搜索
   * exact : 带支配剪枝 + 可采纳下界的 DFS，小规模(N<=12)证明最优。
   * beam  : 同一套转移规则做束搜索，大规模秒级出解。
   * greedy: 贪心基线，用来对照。

3) 下界（用于报告最优性差距，全部可采纳）
   LB = max( N*(a+b),  a+hmin+b,  a + ceil((N-1)/H)*(a+b+hmin) + hmin + b )

单一入口：solve(params) -> Plan
================================================================================
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple

EPS = 1e-9


class RobotError(RuntimeError):
    """指令非法（违反硬约束）时抛出。"""


# ==============================================================================
# 1. 参数
# ==============================================================================

@dataclass(frozen=True)
class Params:
    """用户预设参数。"""
    time_step1: float = 2.0          # step1 耗时
    time_step2: float = 1.0          # step2 耗时
    heat_time_min: float = 5.0       # 在台时间下界
    heat_time_max: float = 12.0      # 在台时间上界
    num_heater: int = 3              # 加热器数量
    num_glass: int = 8               # 玻璃片总数
    heat_measure: str = "until_pickup"   # "until_pickup" | "including_pickup"

    def __post_init__(self) -> None:
        if self.num_glass < 0:
            raise ValueError("num_glass 不能为负")
        if self.num_heater < 1:
            raise ValueError("num_heater 至少为 1")
        if self.time_step1 <= 0 or self.time_step2 <= 0:
            raise ValueError("time_step1 / time_step2 必须为正")
        if self.heat_time_min < 0:
            raise ValueError("heat_time_min 不能为负")
        if self.heat_time_max < self.heat_time_min:
            raise ValueError("heat_time_max 必须 >= heat_time_min")
        if self.heat_measure not in ("until_pickup", "including_pickup"):
            raise ValueError("heat_measure 只能是 until_pickup 或 including_pickup")

    @property
    def tail(self) -> float:
        """在台时间度量口径带来的偏移量。"""
        return self.time_step2 if self.heat_measure == "including_pickup" else 0.0

    @property
    def slack(self) -> float:
        """deadline - release 的常量差。"""
        return self.heat_time_max - self.heat_time_min

    def to_dict(self) -> dict:
        return {
            "time_step1": self.time_step1,
            "time_step2": self.time_step2,
            "heat_time_min": self.heat_time_min,
            "heat_time_max": self.heat_time_max,
            "num_heater": self.num_heater,
            "num_glass": self.num_glass,
            "heat_measure": self.heat_measure,
        }


# ==============================================================================
# 2. 指令原语：step1(n, m) 与 step2(n, m)
#    —— 题目要求的两条指令，签名严格为 (n, m)。
#    调度器负责"什么时候调用"，本层负责"调用时物理上是否合法"。
# ==============================================================================

@dataclass
class Command:
    """一条待执行的指令。"""
    t: float                 # 起始时刻
    kind: str                # "step1" | "step2"
    n: int                   # 玻璃片编号
    m: int                   # 加热器编号
    end: float = 0.0         # 结束时刻

    def __str__(self) -> str:
        return (f"t={self.t:7.3f}  {self.kind}(n={self.n}, m={self.m})"
                f"  [{self.t:7.3f}, {self.end:7.3f}]")


class RobotContext:
    """机械臂 + 加热器的物理状态机，供 step1 / step2 做合法性检查与记账。"""

    def __init__(self, params: Params) -> None:
        self.p = params
        self.clock: float = 0.0        # 当前时刻
        self.busy_until: float = 0.0    # 机械臂空闲时刻
        self.heater: Dict[int, Optional[int]] = {m: None for m in range(1, params.num_heater + 1)}
        self.glass_at: Dict[int, int] = {}       # 玻璃片 -> 所在加热器
        self.put_end: Dict[int, float] = {}      # 玻璃片 -> step1 结束时刻
        self.pick_at: Dict[int, float] = {}      # 玻璃片 -> step2 起始时刻
        self.trace: List[Command] = []

    # -- 内部工具 ------------------------------------------------------------
    def _arm_ready(self) -> None:
        if self.clock < self.busy_until - EPS:
            raise RobotError(
                f"机械臂仍被占用（占用至 {self.busy_until:.4f}），无法在 t={self.clock:.4f} 发指令")

    def on_heater_set(self) -> set:
        return {g for g in self.glass_at.values() if g is not None}

    def heat_time(self, n: int) -> float:
        """玻璃片 n 的在台时间。"""
        return (self.pick_at[n] + self.p.tail) - self.put_end[n]


_CTX: Optional[RobotContext] = None


def configure(params: Params) -> RobotContext:
    """初始化物理上下文，之后就可以直接调用 step1(n, m) / step2(n, m)。"""
    global _CTX
    _CTX = RobotContext(params)
    return _CTX


def step1(n: int, m: int) -> Command:
    """指令 1：机械臂取第 n 个玻璃片，放到第 m 个加热器上加热。

    耗时 time_step1；玻璃片在指令**结束**时落到加热器上。
    """
    ctx = _require_ctx()
    p = ctx.p
    ctx._arm_ready()
    if not (0 <= n < p.num_glass):
        raise RobotError(f"玻璃片编号 {n} 越界（共 {p.num_glass} 片）")
    if m not in ctx.heater:
        raise RobotError(f"加热器编号 {m} 越界（共 {p.num_heater} 个）")
    if n in ctx.glass_at:
        raise RobotError(f"玻璃片 {n} 已经在加热器 {ctx.glass_at[n]} 上，step1 非法")
    if ctx.heater[m] is not None:
        raise RobotError(f"加热器 {m} 已被玻璃片 {ctx.heater[m]} 占用，step1 非法")

    cmd = Command(t=ctx.clock, kind="step1", n=n, m=m)
    cmd.end = ctx.clock + p.time_step1
    ctx.heater[m] = n
    ctx.glass_at[n] = m
    ctx.put_end[n] = cmd.end
    ctx.busy_until = cmd.end
    ctx.trace.append(cmd)
    return cmd


def step2(n: int, m: int) -> Command:
    """指令 2：机械臂从第 m 个加热器上取第 n 个玻璃片，放回第 n 号位置。

    耗时 time_step2；玻璃片在指令**开始**时离开加热器。
    """
    ctx = _require_ctx()
    p = ctx.p
    ctx._arm_ready()
    if n not in ctx.glass_at:
        raise RobotError(f"玻璃片 {n} 不在加热器上，无法执行 step2")
    if ctx.glass_at[n] != m:
        raise RobotError(f"玻璃片 {n} 在加热器 {ctx.glass_at[n]} 上，不在 {m} 上，step2 非法")
    if ctx.clock < ctx.put_end[n] + p.heat_time_min - p.tail - EPS:
        raise RobotError(
            f"玻璃片 {n} 在台时间不足：仅 {ctx.heat_time(n):.4f} < heat_time_min={p.heat_time_min}")

    cmd = Command(t=ctx.clock, kind="step2", n=n, m=m)
    cmd.end = ctx.clock + p.time_step2
    heat = (ctx.clock + p.tail) - ctx.put_end[n]     # 此刻玻璃片正离开加热器
    if heat > p.heat_time_max + EPS:
        raise RobotError(
            f"玻璃片 {n} 在台时间超限：{heat:.4f} > heat_time_max={p.heat_time_max}")
    ctx.heater[m] = None
    del ctx.glass_at[n]
    ctx.pick_at[n] = ctx.clock
    ctx.busy_until = cmd.end
    ctx.trace.append(cmd)
    return cmd


def _require_ctx() -> RobotContext:
    if _CTX is None:
        raise RobotError("尚未初始化：请先调用 configure(params)")
    return _CTX


# ==============================================================================
# 3. 调度内核：状态、转移、下界、搜索
# ==============================================================================

# 状态 = (t, releases, placed)
#   t        : 机械臂空闲时刻
#   releases : 元组，按升序，元素为在台玻璃片的最早可取时刻
#              （= end(step1_i) + heat_time_min - tail）
#   placed   : 累计放上加热器的玻璃片数
# 未取走的玻璃片按 end(step1) 升序排列，因此 releases[0] 就是"在台最久"的那片；
# EDF 论证保证取它最优，故无需再保存玻璃片编号。

State = Tuple[float, Tuple[float, ...], int]


def _lower_bound(st: State, p: Params) -> float:
    """可采纳下界：当前状态出发的 makespan 至少是多少。

    注意口径：including_pickup 时 tail=b，"在台占用"的有效下界是
    eff = max(0, hmin - tail)（玻璃片一放好就可能被立即取走，拾取段计入加热窗）。
    """
    t, rel, placed = st
    a, b = p.time_step1, p.time_step2
    eff = max(0.0, p.heat_time_min - p.tail)
    # (1) 机械臂剩余纯作业时间
    lb = t + len(rel) * b + (p.num_glass - placed) * (a + b)
    # (2) 在台玻璃片中最后一片：最早 max(t, release) 开始取，再花 b
    if rel:
        lb = max(lb, max(t, rel[-1]) + b)
    # (3) 还有没上片的玻璃片：放 a -> 有效在台 eff -> 取 b
    if placed < p.num_glass:
        lb = max(lb, t + a + eff + b)
    return lb


def global_lower_bound(p: Params) -> float:
    """全局下界：三条可采纳界取最大。返回值必然 <= 真正的最优 makespan。

    推导（tail 为口径偏移，eff = max(0, heat_time_min - tail) 为有效在台占用）：
    (1) 机械臂串行：N*(a+b)；
    (2) 单片 latency：a + eff + b；
    (3) 加热器吞吐：同一加热器上相邻两片的 end(step1) 至少间隔 eff + b + a
        （等够在台 eff -> 取走 b -> 下一片放完 a），
        N 片分到 H 个加热器必有一个承担 >= ceil(N/H) 片，
        末片还要 eff + b 才算放回。
    """
    a, b = p.time_step1, p.time_step2
    eff = max(0.0, p.heat_time_min - p.tail)
    n, h = p.num_glass, p.num_heater
    if n == 0:
        return 0.0
    lb_busy = n * (a + b)
    lb_latency = a + eff + b
    rounds = math.ceil(n / h)
    lb_heater = a + (rounds - 1) * (eff + a + b) + eff + b
    return max(lb_busy, lb_latency, lb_heater)


def _children(st: State, p: Params) -> List[Tuple[State, int, float]]:
    """列出所有合法的下一步动作。

    返回 [(新状态, 动作码, 该动作的起始时刻), ...]，动作码 1=step1, 0=step2。
    三类动作：
      (A) 立刻 step1        —— 只要还有空位加热器且还有未上片的玻璃片
      (B) 立刻 step2        —— 最早可取时刻已到，且不超 heat_time_max
      (C) 空等再 step2      —— 机械臂无事可做，等到 releases[0] 再取
    """
    t, rel, placed = st
    a, b, slack = p.time_step1, p.time_step2, p.slack
    out: List[Tuple[State, int, float]] = []

    # (A) 上片
    if placed < p.num_glass and len(rel) < p.num_heater:
        nt = t + a
        out.append(((nt, rel + (nt + p.heat_time_min - p.tail,), placed + 1), 1, t))

    if rel:
        r0 = rel[0]
        # (B) 现在就取
        if t >= r0 - EPS and t <= r0 + slack + EPS:
            out.append(((t + b, rel[1:], placed), 0, t))
        # (C) 空等到可以取（这一步未必被 (A) 支配：短等 + 先取可以更早腾出加热器）
        if t < r0 - EPS:
            out.append(((r0 + b, rel[1:], placed), 0, r0))
    return out


# ---------------------------------------------------------------- 精确搜索 ---

def _solve_exact(p: Params, ub: float = math.inf,
                 max_nodes: int = 3_000_000, time_limit: float = 30.0):
    """DFS + 支配剪枝 + 下界剪枝。

    返回 (status, makespan, path, proven_optimal)：
      status = "ok"        找到可行解（proven_optimal=True 表示搜索完整、已证明最优）
      status = "infeasible" 搜索空间已穷尽且无任何可行解（可证明参数下无解）
      status = "timeout"    节点/时间预算耗尽且尚未找到可行解
    """
    t_end = time.perf_counter()
    best_t = [ub]
    best_path: List[Tuple] = []
    seen: Dict[State, float] = {}
    nodes = 0
    exhausted = True          # 若中途超时/超节点则置 False

    def dfs(t: float, rel: Tuple[float, ...], placed: int, path: List) -> None:
        nonlocal nodes, exhausted
        nodes += 1
        if nodes > max_nodes:
            exhausted = False
            raise TimeoutError
        if (nodes & 2047) == 0 and time.perf_counter() - t_end > time_limit:
            exhausted = False
            raise TimeoutError
        if not rel and placed == p.num_glass:
            if t < best_t[0] - EPS:
                best_t[0] = t
                best_path[:] = list(path)
            return
        # 可采纳下界剪枝（与全局下界同一套推导，对两种口径都成立）
        if _lower_bound((t, rel, placed), p) >= best_t[0] - EPS:
            return
        # 状态支配剪枝：同一 (rel, placed) 若已用不晚于当前的时刻到达过，则不必再展开
        key = (rel, placed)
        prev = seen.get(key)
        if prev is not None and prev <= t + EPS:
            return
        seen[key] = t

        kids = _children((t, rel, placed), p)
        # 先探索下界更小的分支，尽早拿到好的上界
        kids.sort(key=lambda k: _lower_bound(k[0], p))
        for ns, act, start in kids:
            path.append((act, start))
            dfs(ns[0], ns[1], ns[2], path)
            path.pop()

    try:
        dfs(0.0, (), 0, [])
    except TimeoutError:
        if best_path:
            return "ok", best_t[0], best_path, False
        return "timeout", None, None, False
    if best_path:
        return "ok", best_t[0], best_path, True
    if exhausted:
        return "infeasible", None, None, False
    return "timeout", None, None, False


# ---------------------------------------------------------------- 束搜索 ---

class _Node:
    __slots__ = ("t", "rel", "placed", "parent", "act", "start")

    def __init__(self, t, rel, placed, parent, act, start):
        self.t, self.rel, self.placed = t, rel, placed
        self.parent, self.act, self.start = parent, act, start


def _solve_beam(p: Params, width: int = 800, time_limit: float = 20.0):
    """束搜索。返回 (status, makespan, path, False)。"""
    t_end = time.perf_counter()
    nodes: List[_Node] = [_Node(0.0, (), 0, None, -1, 0.0)]
    beam = [0]
    best: List[Tuple[float, int]] = []
    timed_out = False

    for _ in range(2 * p.num_glass + 2):
        cand: List[int] = []
        seen: set = set()
        for idx in beam:
            nd = nodes[idx]
            if not nd.rel and nd.placed == p.num_glass:
                best.append((nd.t, idx))
                continue
            for ns, act, start in _children((nd.t, nd.rel, nd.placed), p):
                key = (round(ns[0], 6), ns[1], ns[2])
                if key in seen:
                    continue
                seen.add(key)
                nodes.append(_Node(ns[0], ns[1], ns[2], idx, act, start))
                cand.append(len(nodes) - 1)
            if time.perf_counter() - t_end > time_limit:
                timed_out = True
                break
        if not cand:
            break
        cand.sort(key=lambda i: (_lower_bound((nodes[i].t, nodes[i].rel, nodes[i].placed), p),
                                 nodes[i].t))
        beam = cand[:width]

    if best:
        t_best, idx = min(best)
        path: List[Tuple] = []
        cur = idx
        while nodes[cur].act >= 0:
            path.append((nodes[cur].act, nodes[cur].start))
            cur = nodes[cur].parent
        path.reverse()
        return "ok", t_best, path, False
    return ("timeout" if timed_out else "infeasible"), None, None, False


# ---------------------------------------------------------------- 贪心基线 ---

def _solve_greedy(p: Params):
    """贪心基线（带整链截止期护栏）：有空位就上片，但上片前先模拟
    "上完这片之后整个 FIFO 取片链"是否每片都能赶上各自的 deadline；
    只要有一片赶不上，就改为立刻取片。

    这是 O(N*H) 的构造式启发式：不回溯，极端实例上仍可能违反
    heat_time_max（那时 verify 会如实报告），但绝大多数可行实例能给出合法解。
    """
    t, rel, placed = 0.0, (), 0
    path: List[Tuple] = []

    def _chain_ok(t_now: float, queue: Tuple[float, ...]) -> bool:
        """假设机械臂从 t_now 起空闲，按 FIFO 依次取 queue，检查全链 deadline。"""
        end = t_now
        for r in queue:
            start = max(end, r)
            if start > r + p.slack + EPS:
                return False
            end = start + p.time_step2
        return True

    while not (placed == p.num_glass and not rel):
        can_place = placed < p.num_glass and len(rel) < p.num_heater
        # 护栏：若现在花 a 时间上片，新片排在队尾，检查整条取片链
        safe = False
        if can_place:
            new_rel = t + p.time_step1 + p.heat_time_min - p.tail
            safe = _chain_ok(t + p.time_step1, rel + (new_rel,))
        if can_place and safe:
            nt = t + p.time_step1
            path.append((1, t))
            t, rel, placed = nt, rel + (nt + p.heat_time_min - p.tail,), placed + 1
        elif rel:
            start = max(t, rel[0])
            path.append((0, start))
            t, rel = start + p.time_step2, rel[1:]
        else:
            break
    return t, path


# ==============================================================================
# 4. 回溯：把"类型序列"还原成带玻璃片编号 / 加热器编号的指令表
# ==============================================================================

def _reconstruct(p: Params, path: Sequence[Tuple[int, float]]) -> List[Command]:
    cmds: List[Command] = []
    rel: List[Tuple[float, int, int]] = []     # (release, glass, heater)
    free_heaters = sorted(range(1, p.num_heater + 1))
    next_glass = 0

    for act, start in path:
        if act == 1:
            m = free_heaters.pop(0)             # 加热器同构，任取最小空闲编号
            cmd = Command(t=start, kind="step1", n=next_glass, m=m)
            cmd.end = start + p.time_step1
            rel.append((cmd.end + p.heat_time_min - p.tail, next_glass, m))
            next_glass += 1
        else:
            _, g, m = rel.pop(0)                # EDF：取在台最久的那片
            cmd = Command(t=start, kind="step2", n=g, m=m)
            cmd.end = start + p.time_step2
            free_heaters.append(m)
            free_heaters.sort()
        cmds.append(cmd)
    return cmds


# ==============================================================================
# 5. 校验：把指令表真正喂给 step1 / step2，跑一遍物理检查
# ==============================================================================

def verify(p: Params, cmds: Sequence[Command]) -> Tuple[bool, List[str], Dict]:
    """独立复核：重放指令，检查全部硬约束。返回 (是否通过, 错误列表, 统计)。"""
    errs: List[str] = []
    ctx = configure(p)
    prev_end = -math.inf
    heats: Dict[int, float] = {}
    try:
        for cmd in cmds:
            if cmd.t < prev_end - EPS:
                errs.append(f"C1 单机冲突：{cmd} 与上一条指令重叠")
            if cmd.t < ctx.clock - EPS:
                errs.append(f"C1 指令时间倒流：{cmd}")
            ctx.clock = max(cmd.t, ctx.clock)
            if cmd.kind == "step1":
                step1(cmd.n, cmd.m)
            else:
                step2(cmd.n, cmd.m)
            prev_end = cmd.end
            if cmd.kind == "step2":
                heats[cmd.n] = ctx.heat_time(cmd.n)
    except RobotError as e:
        errs.append(f"非法指令：{e}")

    done = {c.n for c in cmds if c.kind == "step2"}
    if len(done) != p.num_glass:
        errs.append(f"只完成了 {len(done)}/{p.num_glass} 片玻璃片")

    peak = 0
    events = []
    for c in cmds:
        if c.kind == "step1":
            events.append((c.end, 1))      # step1 结束 -> 玻璃片落到加热器
        else:
            events.append((c.t, -1))       # step2 开始 -> 玻璃片离开加热器
    cur = 0
    for _, d in sorted(events, key=lambda e: (e[0], -e[1])):
        cur += d
        peak = max(peak, cur)
    if peak > p.num_heater:
        errs.append(f"C2 加热器超载：峰值 {peak} > {p.num_heater}")

    for g, h in heats.items():
        if h < p.heat_time_min - EPS or h > p.heat_time_max + EPS:
            errs.append(f"C3 玻璃片 {g} 在台时间 {h:.4f} 越界 "
                        f"[{p.heat_time_min}, {p.heat_time_max}]")

    stats = {
        "peak_heater_load": peak,
        "heat_times": heats,
        "arm_busy": sum(c.end - c.t for c in cmds),
        "makespan": max((c.end for c in cmds), default=0.0),
    }
    return (not errs), errs, stats


# ==============================================================================
# 6. 甘特图（纯文本，无第三方依赖）
# ==============================================================================

def gantt(p: Params, cmds: Sequence[Command], makespan: float, cols: int = 92) -> str:
    if not cmds:
        return "(空计划)"
    span = max(makespan, EPS)

    def col(t: float) -> int:
        return min(cols - 1, max(0, int(t / span * cols)))

    # 机械臂泳道
    lane_arm = [" "] * cols
    for c in cmds:
        ch = "P" if c.kind == "step1" else "G"
        for i in range(col(c.t), min(cols, col(c.end) + 1)):
            lane_arm[i] = ch

    # 加热器泳道（在台区间）
    lanes: Dict[int, List[str]] = {m: [" "] * cols for m in range(1, p.num_heater + 1)}
    for c in cmds:
        if c.kind == "step1":
            for c2 in cmds:
                if c2.kind == "step2" and c2.n == c.n:
                    for i in range(col(c.end), min(cols, col(c2.t) + 1)):
                        lanes[c.m][i] = str(c.n % 10)
                    break

    # 时间刻度
    axis = [" "] * cols
    ticks = 6
    for k in range(ticks + 1):
        pos = int(k / ticks * (cols - 1))
        label = f"{span * k / ticks:.0f}"
        for j, ch in enumerate(label):
            if pos + j < cols:
                axis[pos + j] = ch

    out = [f"makespan = {makespan:.3f}    (P = step1 上片, G = step2 取片, 数字 = 玻璃片编号, . = 空闲)",
           "  " + "".join(axis)]
    out.append("机械臂 " + "".join(lane_arm))
    for m in range(1, p.num_heater + 1):
        out.append(f"加热器{m} " + "".join(lanes[m]))
    return "\n".join(out)


# ==============================================================================
# 7. 结果对象 + 单一入口
# ==============================================================================

@dataclass
class Plan:
    params: Params
    commands: List[Command]
    makespan: float
    lower_bound: float
    method: str
    proven_optimal: bool
    feasible: bool
    errors: List[str] = field(default_factory=list)
    stats: Dict = field(default_factory=dict)
    searched_ms: float = 0.0

    @property
    def gap(self) -> float:
        if self.makespan <= 0:
            return 0.0
        return max(0.0, (self.makespan - self.lower_bound) / self.makespan)

    def to_dict(self) -> dict:
        return {
            "params": self.params.to_dict(),
            "makespan": self.makespan,
            "lower_bound": self.lower_bound,
            "gap": round(self.gap, 6),
            "method": self.method,
            "proven_optimal": self.proven_optimal,
            "feasible": self.feasible,
            "errors": self.errors,
            "commands": [{"t": c.t, "kind": c.kind, "n": c.n, "m": c.m, "end": c.end}
                         for c in self.commands],
            "stats": {"peak_heater_load": self.stats.get("peak_heater_load"),
                      "arm_busy": self.stats.get("arm_busy")},
        }


def solve(params: Params, method: str = "auto", beam_width: int = 800,
          time_limit: float = 30.0, verbose: bool = True) -> Plan:
    """**整个程序的唯一入口**：自动规划 step1 / step2 的下发时刻，使 makespan 尽量小。

    参数
    ----
    params     : Params，用户预设参数
    method     : "auto" | "exact" | "beam" | "greedy"
    beam_width : 束搜索宽度（大规模时影响质量/速度）
    time_limit : 精确搜索的时间上限（秒）
    """
    t0 = time.perf_counter()
    p = params
    lb = global_lower_bound(p)
    n = p.num_glass

    if n == 0:
        ok, errs, stats = verify(p, [])
        return Plan(p, [], 0.0, 0.0, "trivial", True, ok, errs, stats, 0.0)

    diag: List[str] = []
    opt = False
    ms = None
    path = None

    def _fallback(reason: str):
        """找不到可行解时，退回贪心解作为诊断参考（它会违反 heat_time_max）。"""
        g_ms, g_path = _solve_greedy(p)
        diag.append(reason + "；下面给出的是忽略 heat_time_max 的贪心参考解，仅供诊断")
        return g_ms, g_path

    if method == "greedy":
        ms, path = _solve_greedy(p)
    elif method == "exact":
        status, ms, path, opt = _solve_exact(p, time_limit=time_limit)
        if status == "infeasible":
            ms, path = _fallback("搜索已穷尽：当前参数下不存在满足 heat_time_max 的可行调度"
                                 "（通常是 heat_time_max 相对 time_step1/time_step2 过紧）")
        elif status == "timeout":
            ms, path = _fallback("精确搜索超时且未找到可行解，可增大 time_limit")
    elif method == "beam":
        status, ms, path, opt = _solve_beam(p, width=beam_width, time_limit=time_limit)
        if status == "infeasible":
            ms, path = _fallback("束搜索未找到任何可行解：当前参数下大概率不存在满足 "
                                 "heat_time_max 的可行调度")
        elif status == "timeout":
            ms, path = _fallback("束搜索超时且未找到可行解")
    else:  # auto
        cat = math.comb(2 * n, n) // (n + 1)      # Catalan(n)，类型序列数上界
        if n <= 12 and cat <= 250_000:
            status, ms, path, opt = _solve_exact(p, time_limit=time_limit)
            if status != "ok":
                status2, ms2, path2, opt2 = _solve_beam(p, width=beam_width)
                if status2 == "ok":
                    status, ms, path, opt = status2, ms2, path2, opt2
        else:
            status, ms, path, opt = _solve_beam(p, width=beam_width, time_limit=time_limit)
        if status == "infeasible":
            ms, path = _fallback("当前参数下不存在满足 heat_time_max 的可行调度")
        elif status == "timeout":
            ms, path = _fallback("搜索超时且未找到可行解，可增大 time_limit 或 beam_width")

    cmds = _reconstruct(p, path)
    ok, errs, stats = verify(p, cmds)
    errs = diag + errs
    if diag:
        ok = False
    real_ms = stats.get("makespan", ms)
    return Plan(p, cmds, real_ms, lb, method, opt and ok and not diag, ok, errs, stats,
                (time.perf_counter() - t0) * 1000)


# ==============================================================================
# 8. 命令行
# ==============================================================================

SCENARIOS = [
    ("A 宽松加热窗（H=3, N=8）", Params(2.0, 1.0, 5.0, 12.0, 3, 8)),
    ("B 加热窗很紧（hmax 卡死）", Params(1.0, 3.0, 2.0, 3.0, 2, 6)),
    ("C 中等规模走束搜索", Params(1.5, 1.0, 4.0, 6.0, 4, 12)),
    ("D 加热器是瓶颈（H=1）", Params(1.0, 1.0, 3.0, 8.0, 1, 5)),
]

DEFAULT_CONFIG_NAME = "params.json"
_SOLVER_KEYS = ("method", "beam_width", "time_limit")


def default_config_dict() -> dict:
    """默认配置（params 字段与 Params.to_dict() 一一对应）。"""
    return {
        "params": Params().to_dict(),
        "solver": {"method": "auto", "beam_width": 800, "time_limit": 30.0},
    }


def write_default_config(path: str) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(default_config_dict(), f, ensure_ascii=False, indent=2)
        f.write("\n")


def load_config(path: str) -> Tuple[dict, dict]:
    """读取 JSON 配置，返回 (params 覆盖项, solver 覆盖项)。

    支持两种写法：
      {"params": {...}, "solver": {...}}   推荐写法
      {...直接平铺 params 字段...}          也接受
    未知键一律报错（拼错参数名静默用默认值是调度事故的常见来源）。
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path}: 配置根节点必须是 JSON 对象")

    if "params" in data or "solver" in data:
        raw_params = data.get("params", {})
        raw_solver = data.get("solver", {})
        unknown_top = set(data) - {"params", "solver"}
        if unknown_top:
            raise ValueError(f"{path}: 未知顶层键 {sorted(unknown_top)}，只允许 params / solver")
    else:
        raw_params, raw_solver = data, {}

    if not isinstance(raw_params, dict) or not isinstance(raw_solver, dict):
        raise ValueError(f"{path}: params / solver 必须是 JSON 对象")

    valid_params = set(Params().to_dict())
    unknown = set(raw_params) - valid_params
    if unknown:
        raise ValueError(f"{path}: 未知参数键 {sorted(unknown)}，"
                         f"合法键: {sorted(valid_params)}")
    unknown = set(raw_solver) - set(_SOLVER_KEYS)
    if unknown:
        raise ValueError(f"{path}: 未知 solver 键 {sorted(unknown)}，"
                         f"合法键: {list(_SOLVER_KEYS)}")

    # 整数字段做整型收敛（3.0 -> 3；3.5 -> 报错）
    params_out = dict(raw_params)
    for k in ("num_heater", "num_glass"):
        if k in params_out:
            v = params_out[k]
            if isinstance(v, float) and v.is_integer():
                params_out[k] = int(v)
            elif not isinstance(v, int):
                raise ValueError(f"{path}: {k} 必须是整数，得到 {v!r}")
    return params_out, dict(raw_solver)


def _format_report(plan: Plan) -> str:
    """把调度结果排成人类可读的文本时间表（打印 / 存文件共用这一份）。"""
    p = plan.params
    out: List[str] = []
    out.append("=" * 92)
    out.append(f"参数: time_step1={p.time_step1}  time_step2={p.time_step2}  "
               f"heat_time=[{p.heat_time_min}, {p.heat_time_max}]  "
               f"num_heater={p.num_heater}  num_glass={p.num_glass}  口径={p.heat_measure}")
    out.append(f"结果: makespan={plan.makespan:.4f}   下界={plan.lower_bound:.4f}   "
               f"相对差距={plan.gap * 100:.2f}%   方法={plan.method}   "
               f"{'已证明最优' if plan.proven_optimal else '未证明最优'}   "
               f"耗时={plan.searched_ms:.1f}ms")
    out.append(f"校验: {'全部硬约束通过' if plan.feasible else '失败 -> ' + '; '.join(plan.errors)}"
               f"   (加热器峰值占用 {plan.stats.get('peak_heater_load')}/{p.num_heater}, "
               f"机械臂忙碌 {plan.stats.get('arm_busy', 0):.2f})")
    ht = plan.stats.get("heat_times", {})
    if ht:
        vals = list(ht.values())
        out.append(f"在台时间: min={min(vals):.3f}  max={max(vals):.3f}  "
                   f"(允许区间 [{p.heat_time_min}, {p.heat_time_max}])")
    out.append("-" * 92)
    out.append(f"{'#':>3}  {'step1(n,m) 起始':>14}  {'结束':>9}  |  "
               f"{'step2(n,m) 起始':>14}  {'结束':>9}  {'在台时间':>9}")
    s1 = {c.n: c for c in plan.commands if c.kind == "step1"}
    s2 = {c.n: c for c in plan.commands if c.kind == "step2"}
    for g in sorted(s1):
        a, b = s1[g], s2[g]
        out.append(f"{g:>3}  step1({g},{a.m}) {a.t:>9.3f}  {a.end:>9.3f}  |  "
                   f"step2({g},{b.m}) {b.t:>9.3f}  {b.end:>9.3f}  {b.t - a.end:>9.3f}")
    out.append("-" * 92)
    out.append(gantt(p, plan.commands, plan.makespan))
    out.append("=" * 92)
    return "\n".join(out)


def _print_report(plan: Plan) -> None:
    print(_format_report(plan))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="机械臂玻璃片加热调度器：自动规划 step1/step2 的下发时刻，最小化 makespan")
    ap.add_argument("--config", "-c", default=None,
                    help=f"JSON 配置文件路径（缺省自动寻找当前目录的 {DEFAULT_CONFIG_NAME}）")
    ap.add_argument("--out", "-o", default=None,
                    help="把文本时间表额外保存到该文件")
    ap.add_argument("--time-step1", type=float, default=None, help="step1 耗时（覆盖配置文件）")
    ap.add_argument("--time-step2", type=float, default=None, help="step2 耗时（覆盖配置文件）")
    ap.add_argument("--heat-time-min", type=float, default=None, help="在台时间下界（覆盖配置文件）")
    ap.add_argument("--heat-time-max", type=float, default=None, help="在台时间上界（覆盖配置文件）")
    ap.add_argument("--num-heater", type=int, default=None, help="加热器数量（覆盖配置文件）")
    ap.add_argument("--num-glass", type=int, default=None, help="玻璃片总数（覆盖配置文件）")
    ap.add_argument("--heat-measure", choices=["until_pickup", "including_pickup"], default=None)
    ap.add_argument("--method", choices=["auto", "exact", "beam", "greedy"], default=None)
    ap.add_argument("--beam-width", type=int, default=None)
    ap.add_argument("--time-limit", type=float, default=None)
    ap.add_argument("--demo", action="store_true", help="跑内置的一组场景")
    ap.add_argument("--compare", action="store_true", help="对比 greedy / beam / exact")
    ap.add_argument("--json", action="store_true", help="以 JSON 输出（仍可加 --out 存文本表）")
    args = ap.parse_args(argv)

    # ---- 1. 配置来源与优先级：命令行 > JSON 配置 > 内置默认 ----
    created_config = False
    cfg_path = args.config
    if not args.demo and cfg_path is None:
        if os.path.exists(DEFAULT_CONFIG_NAME):
            cfg_path = DEFAULT_CONFIG_NAME
        else:
            # 首次运行且没有配置文件：生成一份默认 params.json 方便修改
            write_default_config(DEFAULT_CONFIG_NAME)
            created_config = True
            cfg_path = DEFAULT_CONFIG_NAME

    json_params: dict = {}
    json_solver: dict = {}
    if cfg_path and not args.demo:
        try:
            json_params, json_solver = load_config(cfg_path)
        except (OSError, ValueError) as e:
            print(f"[配置错误] {e}", file=sys.stderr)
            return 2

    cli_params = {k: v for k, v in {
        "time_step1": args.time_step1, "time_step2": args.time_step2,
        "heat_time_min": args.heat_time_min, "heat_time_max": args.heat_time_max,
        "num_heater": args.num_heater, "num_glass": args.num_glass,
        "heat_measure": args.heat_measure,
    }.items() if v is not None}
    p = Params(**{**Params().to_dict(), **json_params, **cli_params})

    method = args.method or json_solver.get("method", "auto")
    beam_width = args.beam_width if args.beam_width is not None else json_solver.get("beam_width", 800)
    time_limit = args.time_limit if args.time_limit is not None else json_solver.get("time_limit", 30.0)

    if created_config:
        print(f"[提示] 未找到配置文件，已生成默认 {DEFAULT_CONFIG_NAME}，"
              f"改完数值后重新运行即可生效。\n")

    # ---- 2. demo 模式 ----
    if args.demo:
        for name, sp in SCENARIOS:
            print(f"\n### 场景 {name}")
            _print_report(solve(sp, method=method, beam_width=beam_width,
                                time_limit=time_limit))
        return 0

    # ---- 3. 常规运行：求解 -> 文本时间表 ----
    if args.compare:
        rows = []
        for m in ("greedy", "beam", "exact"):
            try:
                pl = solve(p, method=m, beam_width=beam_width, time_limit=time_limit)
                rows.append((m, pl.makespan, pl.lower_bound, pl.gap * 100,
                             "是" if pl.proven_optimal else "否",
                             "是" if pl.feasible else "否", pl.searched_ms))
            except Exception as e:                       # noqa: BLE001
                rows.append((m, None, None, None, f"失败: {e}", "-", 0.0))
        print(f"{'方法':<8}{'makespan':>12}{'下界':>12}{'差距%':>10}{'最优':>8}{'可行':>8}{'耗时ms':>12}")
        for r in rows:
            print(f"{r[0]:<8}{(f'{r[1]:.4f}' if r[1] is not None else '-'):>12}"
                  f"{(f'{r[2]:.4f}' if r[2] is not None else '-'):>12}"
                  f"{(f'{r[3]:.2f}' if r[3] is not None else '-'):>10}{r[4]:>8}{r[5]:>8}{r[6]:>12.1f}")
        return 0

    plan = solve(p, method=method, beam_width=beam_width, time_limit=time_limit)
    text = _format_report(plan)
    print(text)                                   # 先以文本形式输出给用户看
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(text + "\n")
        print(f"[提示] 文本时间表已保存到 {args.out}")
    if args.json:
        print(json.dumps(plan.to_dict(), ensure_ascii=False, indent=2))
    return 0 if plan.feasible else 1


if __name__ == "__main__":
    sys.exit(main())
