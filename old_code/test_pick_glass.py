# 测试机械臂抓取样品
import brain

# 创建控制器实例
ctrl = brain.masterController()

# 初始化
print("正在初始化设备...")
ctrl.init()
print("初始化完成")

# 抓取第1个位置的样品
print("正在抓取第1个位置的样品...")
ctrl.pickGlassFromPlatform(1)
print("抓取完成")

# 返回原点
print("正在返回原点...")
ctrl.moveTo(ctrl.coordinate_origin)
print("操作完成")
