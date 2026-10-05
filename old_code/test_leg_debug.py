# 测试滑轨移动1cm
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import leg2
import time

leg = leg2.controller('COM8')
print('串口打开成功')

# 初始化
print('初始化...')
leg.init()
print('初始化完成')

# 设置
print('设置...')
leg.set()
print('设置完成')

# 移动1cm (y方向，因为x方向已经超时过)
print('移动y轴到10...')
leg.moveTo_y(10)
print('移动命令发送完成')

# 等待
print('等待y轴到位...')
try:
    leg.wait_y()
    print('y轴到位成功！')
except Exception as e:
    print('等待超时:', e)
