# Test arm sample pickup.
import brain

# Create a controller instance.
ctrl = brain.masterController()

# Initialize.
print("正在初始化设备...")
ctrl.init()
print("初始化完成")

# Pick the sample at position 1.
print("正在抓取第1个位置的样品...")
ctrl.pickGlassFromPlatform(1)
print("抓取完成")

# Return to the origin.
print("正在返回原点...")
ctrl.moveTo(ctrl.coordinate_origin)
print("操作完成")
