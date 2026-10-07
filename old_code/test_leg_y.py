# Test a 1 cm stage movement forward.
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import leg2

leg = leg2.controller('COM8')
print('初始化滑轨...')
leg.init()
leg.set()
print('滑轨初始化完成')

# Move forward by increasing Y by 100, assuming units of 0.1 mm.
print('滑轨往前移动1cm...')
leg.moveToDirectly(0, 100)
print('移动完成')
