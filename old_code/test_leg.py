import leg2
import time

print('开始滑轨移动...', flush=True)

leg = leg2.controller('COM8')
leg.init_x()
leg.set()
print('初始化完成', flush=True)

# 获取当前位置
current_pos = leg.getCurrentPos_x()
print(f'当前 X 位置: {current_pos:.2f} cm', flush=True)

# 右移3cm
target_pos = current_pos + 3
print(f'目标位置: {target_pos:.2f} cm', flush=True)
print(f'移动距离: 3 cm (右移)', flush=True)

# 执行移动
leg.moveTo_x(target_pos)
print('移动命令已发送...', flush=True)

# 等待移动完成
time.sleep(2)

# 检查移动后位置
new_pos = leg.getCurrentPos_x()
print(f'移动后 X 位置: {new_pos:.2f} cm', flush=True)
print('滑轨移动完成！', flush=True)
