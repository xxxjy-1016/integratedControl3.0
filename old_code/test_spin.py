import spinCoater2
from dataStructures import SpinInfo
import time

print('开始旋涂测试...', flush=True)

spin = spinCoater2.controller('COM14')
print('controller创建成功', flush=True)

# Use blockSpin_speedMode.
# SpinInfo contains speed, spin duration, acceleration time, and deceleration time.
spin_info = SpinInfo(speed=300, spinTime=10, acceleratingTime=2, deceleratingTime=2)
print(f'旋涂参数: 速度={spin_info.speed} rpm, 时间={spin_info.spinTime}秒', flush=True)

print('开始旋涂：300 rpm，10秒', flush=True)
spin.blockSpin_speedMode([spin_info])
print('旋涂完成！', flush=True)
