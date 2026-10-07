# -*- coding: utf-8 -*-
import sys
import traceback

print('检查机械手状态...', flush=True)
try:
    import hand
    h = hand.controller("COM7")
    print('创建机械手控制器成功', flush=True)
    
    # Attempt initialization.
    print('尝试初始化...', flush=True)
    h.init()
    print('✅ init() 成功', flush=True)
    
except Exception as e:
    print('检查失败:', flush=True)
    traceback.print_exc()
    
    # Attempt to read the current position.
    print('', flush=True)
    print('尝试查询当前位置...', flush=True)
    try:
        import hand
        h = hand.controller("COM7")
        h.ser.open()
        print('串口已打开', flush=True)
        
        # Query the RJ opening position.
        h.send_command([0x05, 0x01, 0x10, 0x30, 0x00, 0x00])
        import time
        time.sleep(0.5)
        response = h.read_response()
        print('RJ位置查询响应:', response, flush=True)
        
        # Query the DCM position.
        h.send_command([0x05, 0x01, 0x10, 0x31, 0x00, 0x00])
        time.sleep(0.5)
        response = h.read_response()
        print('DCM位置查询响应:', response, flush=True)
        
        h.ser.close()
    except Exception as e2:
        print('查询也失败了:', flush=True)
        traceback.print_exc()
