# Test a 1 cm stage movement.
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import leg2
import time

leg = leg2.controller('COM8')
print('串口打开成功')

# Initialize.
print('初始化...')
leg.init()
print('初始化完成')

# Configure.
print('设置...')
leg.set()
print('设置完成')

# Move 1 cm along Y because X previously timed out.
print('移动y轴到10...')
leg.moveTo_y(10)
print('移动命令发送完成')

# Wait.
print('等待y轴到位...')
try:
    leg.wait_y()
    print('y轴到位成功！')
except Exception as e:
    print('等待超时:', e)
