# 滑轨往前移动1cm
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import leg2

leg = leg2.controller('COM8')
print('初始化滑轨...')
leg.init()
leg.set()
print('滑轨初始化完成')

# 往前移动1cm = y方向增加100 (假设单位是0.1mm)
print('滑轨往前移动1cm...')
leg.moveToDirectly(0, 100)
print('移动完成')
