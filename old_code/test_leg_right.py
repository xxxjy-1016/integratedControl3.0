# 测试滑轨往右移动1cm
import brain

ctrl = brain.masterController()

print("正在初始化leg模块...")
ctrl.leg.init()
ctrl.leg.set()
print("leg初始化完成")

# 往右移动1cm (x增加10，单位可能是0.1mm)
print("正在让滑轨往右移动1cm...")
ctrl.leg.moveToDirectly(10, 0)
print("移动完成")
