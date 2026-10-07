# Test forward stage movement along Y only.
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import leg2

leg = leg2.controller('COM8')
print('初始化滑轨...')
leg.init()
leg.set()
print('滑轨初始化完成')

# Move along Y only; increase Y by 100 for the assumed 1 cm movement.
print('滑轨往前移动1cm (y轴)...')
leg.moveTo_y(100)
leg.wait_y()
print('移动完成')
