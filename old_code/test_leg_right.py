# Test a 1 cm stage movement to the right.
import brain

ctrl = brain.masterController()

print("正在初始化leg模块...")
ctrl.leg.init()
ctrl.leg.set()
print("leg初始化完成")

# Move right by increasing X by 10; units may be 0.1 mm.
print("正在让滑轨往右移动1cm...")
ctrl.leg.moveToDirectly(10, 0)
print("移动完成")
