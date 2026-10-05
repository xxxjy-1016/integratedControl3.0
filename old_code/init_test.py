# -*- coding: utf-8 -*-
import sys
import traceback

print('开始初始化设备...', flush=True)
try:
    import brain
    b = brain.masterController()
    print('创建主控器成功', flush=True)
    b.init()
    print('init() 完成', flush=True)
    b.leg.set()
    print('leg.set() 完成', flush=True)
    b.relax()
    print('relax() 完成', flush=True)
    print('', flush=True)
    print('=== 所有设备初始化完成 ===', flush=True)
except Exception as e:
    print('初始化失败:', flush=True)
    traceback.print_exc()
