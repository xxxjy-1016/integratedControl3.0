# Test stage movement.
import brain

# Create a controller instance.
ctrl = brain.masterController()

# Skip gripper initialization because its failure previously stopped the test.
print("正在初始化leg模块...")
ctrl.leg.init()
ctrl.leg.set()
print("leg初始化完成")

# Move 5 cm left from the origin: X decreases by 50; units may be 0.1 mm.
current_x = 0
current_y = 0
print("正在让滑轨往左移动5cm...")
ctrl.leg.moveToDirectly(current_x - 50, current_y)
print("移动完成")
