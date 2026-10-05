# 滑轨往前移动1cm - 只移动y轴
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import leg2

leg = leg2.controller('COM8')
print('初始化滑轨...')
leg.init()
leg.set()
print('滑轨初始化完成')

# 只移动y轴，往前移动1cm = y方向增加100
print('滑轨往前移动1cm (y轴)...')
leg.moveTo_y(100)
leg.wait_y()
print('移动完成')
