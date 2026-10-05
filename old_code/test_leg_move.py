# 测试滑轨移动
import brain

# 创建控制器实例
ctrl = brain.masterController()

# 初始化（跳过hand初始化，因为手失败了就停下来了）
print("正在初始化leg模块...")
ctrl.leg.init()
ctrl.leg.set()
print("leg初始化完成")

# 从原点开始，往左移动5cm (x减少50，单位可能是0.1mm)
current_x = 0
current_y = 0
print("正在让滑轨往左移动5cm...")
ctrl.leg.moveToDirectly(current_x - 50, current_y)
print("移动完成")
