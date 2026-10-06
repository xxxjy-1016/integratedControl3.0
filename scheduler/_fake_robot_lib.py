# -*- coding: utf-8 -*-
"""测试用假机械臂库：暴露 step1(n, m) / step2(n, m) 黑盒接口，供 run_plan.py 的
realtime 模式联调。用环境变量控制行为：
    FAKE_T1 / FAKE_T2   step1 / step2 的阻塞时长（秒，默认 0.05）
    FAKE_SLOW=1         step2 故意拖长 8 倍，用来触发执行器的漂移安全中止
"""
import os
import time

_T1 = float(os.environ.get("FAKE_T1", "0.05"))
_T2 = float(os.environ.get("FAKE_T2", "0.05"))
_SLOW = os.environ.get("FAKE_SLOW") == "1"


def step1(n: int, m: int) -> None:
    time.sleep(_T1)


def step2(n: int, m: int) -> None:
    time.sleep(_T2 * (8 if _SLOW else 1))
