# 机械臂往左移动1cm
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

# 尝试直接移动关节看看
print('尝试移动...')
try:
    # 机械臂关节移动测试
    h.moveTo(20)  # 移动到位置20
    print('移动命令已发送')
except Exception as e:
    print('移动失败:', e)

