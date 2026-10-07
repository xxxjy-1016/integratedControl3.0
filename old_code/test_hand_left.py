# Move the arm 1 cm to the left.
import sys
sys.path.insert(0, 'D:/anaconda/python_files/python_test/integratedControl2.0')
import hand

h = hand.controller('COM7')
print('初始化机械臂...')
try:
    h.init()
    print('机械臂初始化完成')
except Exception as e:
    print('初始化部分失败:', e)

# Attempt a direct joint movement.
print('尝试移动...')
try:
    # Test arm joint movement.
    h.moveTo(20)  # Move to position 20.
    print('移动命令已发送')
except Exception as e:
    print('移动失败:', e)

