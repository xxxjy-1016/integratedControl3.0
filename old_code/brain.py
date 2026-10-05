#from colorcet import b_rainbow_bgyrm_35_85_c71
from errors import TLE
import eye_spinCoater
from errors import *
from dataStructures import *
import hand
import leg2
import mouth
import spinCoater2
import evacuationSpace
import valve
import ui
import time
import heaterManager
import positionSensor

# Z轴安全高度（避免撞限位）
Z_SAFE_HAND = 1.0    # 手爪安全最低位置（禁止小于1）
Z_SAFE_MOUTH = 0.0   # 移液器安全最低位置

class masterController:
    def __init__(self):
        self.hand = hand.controller("COM7")
        self.mouth = mouth.controller("COM9")
        self.spinCoater = spinCoater2.controller("COM14")
        self.leg = leg2.controller("COM8")
        self.positionSensor = positionSensor.sensor("COM10")
        self.Heater1 = heaterManager.heaterController("heater1", 4)
        self.Heater2 = heaterManager.heaterController("heater2", 4)
        self.Heater_All = heaterManager.heaterController("heater_all", 8)
        self.evacuationSpace = evacuationSpace.controller("COM15")
        self.valve = valve.controller("COM13")
        self.coordinate_spinCoater_hand = None
        self.distance_spinCoater_pick_and_drop = None
        self.coordinate_spinCoater_mouth = None
        self.coordinate_spinCoater_wait_hand = None
        self.coordinate_spinCoater_wait_mouth = None
        self.coordinate_origin = None
        self.glass_coordinates = [None] * 24  # 索引 0~23 对应编号 1~24
        self.distance_platform_pick_and_put = None
        self.coordinate_cur = None
        # self.coordinate_lips_first = None
        # self.coordinate_lips_12th = None
        # self.coordinate_lips_manyth = None
        self.coordinate_garbage = None
        self.coordinate_bottle_one_hand = None
        self.coordinate_bottle_two_hand = None
        self.coordinate_bottle_one_mouth = None
        self.coordinate_bottle_two_mouth = None
        self.coordinate_bottle_three_hand = None
        self.coordinate_bottle_three_mouth = None

        self.coordinate_heater_stepOne_first = None
        self.coordinate_heater_stepTwo_first = None
        self.coordinate_heater_stepOne_second = None
        self.coordinate_heater_stepTwo_second = None
        self.coordinate_heater_stepOne_third = None
        self.coordinate_heater_stepTwo_third = None
        self.coordinate_heater_stepOne_fourth = None
        self.coordinate_heater_stepTwo_fourth = None

        self.deg_bottle_one = None
        self.deg_bottle_two = None
        self.deg_bottle_three = None
        self.lips_distance_x = None
        self.lips_distance_y = None
        self.coordinate_evacuation_space = None

        self.volume_current = None

        self.hand_aim_position = None

        self.glass_num = 1
        self.lip_num = 1
        self.emergence = False
        self.emergence_info = None
        self.config()

    def YBF_1(self, params : dict, bottleNum = 1):
        start = time.time()
        self.prepareForMultiGlass(1)
        self.pickGlassFromPlatform(1)
        self.putToSpinCoater()
        self.pickLip(bottleNum)
        if bottleNum == 1:
            self.openBottleOne()
            self.suckFromBottleOne(params['SolutionOneVolume'])  # 30
            self.closeBottleOne()
        elif bottleNum == 2:
            self.openBottleTwo()
            self.suckFromBottleTwo(params['SolutionOneVolume'])
            self.closeBottleTwo()
        elif bottleNum == 3:
            self.openBottleThree()
            self.suckFromBottleThree(params['SolutionOneVolume'])
            self.closeBottleThree()
        self.spitToSpinCoater(-1)
        self.spin(params['SpinOneParams'], mode="position")
        end_mid = time.time()
        self.relinquishLip(bottleNum)
        end = time.time()
        # self.moveTo(self.coordinate_origin)

        time1_mid = end_mid - start
        time1 = end - start
        print("time1_mid", time1_mid)
        print("time1", time1)


    def YBF_2(self, params : dict, bottleNum = 1):
        start = time.time()
        self.pickLip(bottleNum)
        if bottleNum == 1:
            self.openBottleOne()
            self.suckFromBottleOne(params['SolutionTwoVolume'])  # 30
            self.closeBottleOne()
        elif bottleNum == 2:
            self.openBottleTwo()
            self.suckFromBottleTwo(params['SolutionTwoVolume'])
            self.closeBottleTwo()
        elif bottleNum == 3:
            self.openBottleThree()
            self.suckFromBottleThree(params['SolutionTwoVolume'])
            self.closeBottleThree()
        self.moveTo(brain.coordinate_spinCoater_wait_mouth)
        self.spitToSpinCoater(-1)
        end_mid = time.time()
        self.moveTo_upAndDown(0,0)
        #self.relinquishLip(2)
        def move_leg_to(self, x, y):
            """直接移动滑轨到指定百分比位置（0~140），并等待到位"""
            self.leg.moveTo(x, y)
            self.leg.wait_x()
            self.leg.wait_y()

        end = time.time()
        time2_mid = end_mid - start
        time2 = end - start
        print("time2_mid", time2_mid)
        print("time2", time2)

    def YBF_3(self, params : dict,bottleNum = 1):
        start = time.time()
        self.moveTo(brain.coordinate_spinCoater_wait_hand)
        mid = time.time()
        self.pickGlassFromSpinCoater()
        self.putToHeater(2, 3)
        self.relinquishLip(bottleNum)  #加热后再放回滴管
        self.moveTo(self.coordinate_origin)
        end = time.time()
        time3 = end - start
        print("time3", time3)
        print("time3_mid", mid - start)

    def YBF_4(self, params : dict):
        start = time.time()
        self.pickGlassFromHeater(2, 3)
        self.putToPlatform(1)
        self.moveTo(self.coordinate_origin)
        end = time.time()
        time4 = end - start
        print("time4", time4)

    def LBF_2(self):
        start = time.time()
        self.pickGlassFromSpinCoater()
        self.putToHeater(2, 3)
        self.moveTo(brain.coordinate_origin)
        end = time.time()
        time5 = end - start
        print("time5", time5)

    def LBF_3(self, bottleNum = 1):
        start = time.time()
        self.pickGlassFromHeater(2, 3)
        self.putToPlatform(1)
        self.prepareForGlass_onlyTheFirstPosition(1)
        self.pickGlassFromPlatform(1)
        self.putToSpinCoater()
        self.pickLip(bottleNum)
        if bottleNum == 1:
            self.openBottleOne()
            self.suckFromBottleOne(params['SolutionTwoVolume'])  # 30
            self.closeBottleOne()
        elif bottleNum == 2:
            self.openBottleTwo()
            self.suckFromBottleTwo(params['SolutionTwoVolume'])
            self.closeBottleTwo()
        elif bottleNum == 3:
            self.openBottleThree()
            self.suckFromBottleThree(params['SolutionTwoVolume'])
            self.closeBottleThree()
        self.spitToSpinCoater(-1)
        self.relinquishLip(bottleNum)
        self.moveTo(brain.coordinate_origin)
        end = time.time()
        time6 = end - start
        print("time6", time6)
        self.pickGlassFromSpinCoater()
        self.putToHeater(2, 3)
        self.moveTo(brain.coordinate_origin)

    def _homing_x(self):
        """X轴回零（临时禁用偏移量，避免干扰搜索）"""
        print("正在执行X轴回零...")

        # 1. 保存旧偏移量，然后临时置零
        old_offset = self.leg.offset_x
        self.leg.offset_x = 0
        print(f"临时禁用X偏移量，从当前位置开始搜索")

        max_steps = 500
        step = 1.0
        sensor_triggered = False

        # 2. 获取当前原始位置
        cur_pos = self.leg.getCurrentPos_x()
        raw_pos = cur_pos
        print(f"起始X位置: {cur_pos:.2f}")

        # 3. 先检查传感器是否已经触发
        if self.positionSensor.detection_x():
            sensor_triggered = True
            raw_pos = self.leg.getCurrentPos_x()
            print(f"X传感器已触发！当前位置: {raw_pos:.2f}")
            self.leg.moveTo_x(raw_pos + 6, ignore_limit=True)
            self.leg.wait_x()
            cur_pos = self.leg.getCurrentPos_x()
            raw_pos = cur_pos
            '''self.leg.offset_x = raw_pos
            self.leg.save_offset()
            print(f"X零点已锁定，偏移量 X = {raw_pos:.2f}")'''

        # 4. 从当前位置逐步向负方向移动
        for i in range(1, max_steps + 1):
            target = cur_pos - i * step
            print(f"  尝试移动到 X = {target:.2f}")
            try:
                self.leg.moveTo_x(target, ignore_limit=True)
                self.leg.wait_x()
            except TLE as e:
                print(f"移动到 {target:.2f} 超时，可能到达限位")
                # 超时后检测传感器
                if self.positionSensor.detection_x():
                    raw_pos = self.leg.getCurrentPos_x()
                    print(f"X传感器触发！当前位置: {raw_pos:.2f}")
                    self.leg.offset_x = raw_pos
                    self.leg.save_offset()
                    print(f"X零点已锁定，偏移量 X = {raw_pos:.2f}")
                    sensor_triggered = True
                break

            # 正常移动后检测传感器
            if self.positionSensor.detection_x():
                raw_pos = self.leg.getCurrentPos_x()
                print(f"X传感器触发！当前位置: {raw_pos:.2f}")
                '''self.leg.offset_x = raw_pos
                self.leg.save_offset()
                print(f"X零点已锁定，偏移量 X = {raw_pos:.2f}")'''
                sensor_triggered = True
                break

        # 5. 如果回零失败，恢复旧偏移量（避免丢失原有设置）
        if not sensor_triggered:
            print("X轴未触发传感器，恢复原偏移量")
            self.leg.offset_x = old_offset
            self.leg.save_offset()
        else:
            for i in range(100):
                target = raw_pos + i * 0.02
                print(f"  尝试移动到 X = {target:.2f}")
                self.leg.moveTo_x(target, ignore_limit=True)
                self.leg.wait_x()
                if not self.positionSensor.detection_x():
                    raw_pos = self.leg.getCurrentPos_x()
                    print(f"X传感器触发！当前位置: {raw_pos:.2f}")
                    self.leg.offset_x = raw_pos
                    self.leg.save_offset()
                    print(f"X零点已锁定，偏移量 X = {raw_pos:.2f}")
                    break
            print("X轴回零成功")

    def _homing_y(self):
        """Y轴回零（临时禁用偏移量，避免干扰搜索）"""
        print("正在执行Y轴回零...")

        # 1. 保存旧偏移量，然后临时置零
        old_offset = self.leg.offset_y
        self.leg.offset_y = 0
        print(f"临时禁用Y偏移量，从当前位置开始搜索")

        max_steps = 500
        step = 1.0
        sensor_triggered = False

        # 2. 获取当前原始位置
        cur_pos = self.leg.getCurrentPos_y()
        raw_pos = cur_pos
        print(f"起始Y位置: {cur_pos:.2f}")

        # 3. 先检查传感器是否已经触发
        if self.positionSensor.detection_y():
            sensor_triggered = True
            raw_pos = self.leg.getCurrentPos_y()
            print(f"Y传感器已触发！当前位置: {raw_pos:.2f}")
            self.leg.moveTo_y(raw_pos + 6, ignore_limit=True)
            self.leg.wait_y()
            cur_pos = self.leg.getCurrentPos_y()
            raw_pos = cur_pos
            '''self.leg.offset_y = raw_pos
            self.leg.save_offset()
            print(f"Y零点已锁定，偏移量 Y = {raw_pos:.2f}")
            return'''

        # 4. 从当前位置逐步向负方向移动
        for i in range(1, max_steps + 1):
            target = cur_pos - i * step
            print(f"  尝试移动到 Y = {target:.2f}")
            try:
                self.leg.moveTo_y(target, ignore_limit=True)
                self.leg.wait_y()
            except TLE as e:
                print(f" 移动到 {target:.2f} 超时，可能到达限位")
                # 超时后检测传感器
                if self.positionSensor.detection_y():
                    raw_pos = self.leg.getCurrentPos_y()
                    print(f"Y传感器触发！当前位置: {raw_pos:.2f}")
                    self.leg.offset_y = raw_pos
                    self.leg.save_offset()
                    print(f"Y零点已锁定，偏移量 Y = {raw_pos:.2f}")
                    sensor_triggered = True
                break

            # 正常移动后检测传感器
            if self.positionSensor.detection_y():
                raw_pos = self.leg.getCurrentPos_y()
                print(f"Y传感器触发！当前位置: {raw_pos:.2f}")
                '''self.leg.offset_y = raw_pos
                self.leg.save_offset()
                print(f"Y零点已锁定，偏移量 Y = {raw_pos:.2f}")'''
                sensor_triggered = True
                break

        # 5. 如果回零失败，恢复旧偏移量（避免丢失原有设置）
        if not sensor_triggered:
            print("Y轴未触发传感器，恢复原偏移量")
            self.leg.offset_y = old_offset
            self.leg.save_offset()
        else:
            for i in range(100):
                target = raw_pos + i * 0.02
                print(f"  尝试移动到 Y = {target:.2f}")
                self.leg.moveTo_y(target, ignore_limit=True)
                self.leg.wait_y()
                if not self.positionSensor.detection_y():
                    raw_pos = self.leg.getCurrentPos_y()
                    print(f"Y传感器触发！当前位置: {raw_pos:.2f}")
                    self.leg.offset_y = raw_pos
                    self.leg.save_offset()
                    print(f"Y零点已锁定，偏移量 Y = {raw_pos:.2f}")
                    break
            print("Y轴回零成功")

    def getLipsCoordinate(self, num=-1):
        if num == -1:
            num = self.lip_num
        if num < 1 or num > len(self.lips_coordinates):
            print(f"错误：吸头编号 {num} 超出范围（1~{len(self.lips_coordinates)}）")
            return None
        return self.lips_coordinates[num - 1]

    def init(self):
        self.lip_num = 1
        self.last_picked_num = None  # 记录上次取的吸头编号
        self.hand.init()
        self.mouth.init()
        self.leg.init()
        self.leg.set()
        self.coordinate_cur = coordinate(0, 0, 0, 0)

        # 先放松手爪，再抬升Z轴
        self.relax()
        self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)

        '''self._homing_x()
        self._homing_y()
        self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)  # 回零后再次确认'''

        print("机械臂初始化完成")

    # def moveTo(self, x, y, zh = 0, zm = 0):
    #     self.coordinate_cur = coordinate(x, y, zh, zm)
    #     self.hand.moveTo(0)
    #     self.mouth.moveTo(0)
    #     self.leg.moveToDirectly(x, y)
    #     self.hand.moveTo(zh)
    #     self.mouth.moveTo(zm)

    def moveTo(self, aim):
        # 先抬升Z轴到安全高度
        self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
        self.coordinate_cur = coordinate(aim.x, aim.y, aim.zh, aim.zm)
        self.hand.moveTo(0)
        self.mouth.moveTo(0)
        self.leg.moveToDirectly(aim.x, aim.y)
        self.hand.moveTo(aim.zh)
        self.mouth.moveTo(aim.zm)

    def moveTo_upAndDown(self, zh=0, zm=0):
        # 手爪限幅：确保不小于 Z_SAFE_HAND（即最小为1）
        if zh < Z_SAFE_HAND:
            zh = Z_SAFE_HAND
        # 移液器不做限制（或可限制为不能小于 Z_SAFE_MOUTH）
        if zm < Z_SAFE_MOUTH:
            zm = Z_SAFE_MOUTH

        if self.coordinate_cur is None:
            self.coordinate_cur = coordinate(0, 0, 0, 0)
        self.coordinate_cur = coordinate(self.coordinate_cur.x, self.coordinate_cur.y, zh, zm)
        self.hand.moveTo(zh)
        self.mouth.moveTo(zm)

    def move_leg_to(self, x, y):
        """直接移动滑轨到指定百分比位置（0~140），并等待到位"""
        self.leg.moveTo(x, y)
        self.leg.wait_x()
        self.leg.wait_y()

    def spin(self, spinInfoList, mode = "speed"):
        if self.coordinate_cur.x == self.coordinate_spinCoater_hand.x and self.coordinate_cur.y == self.coordinate_spinCoater_hand.y:
            self.coordinate_cur.zh = 0
            self.moveTo(self.coordinate_cur)
        self.spinCoater.spin(spinInfoList, mode)

    def clamp(self, aim = 30):
        self.hand.set_rj_clampTorque(50)
        self.hand.clamp(self.hand_aim_position)
        pos = self.hand.query_rj_position()
        if pos < aim:
            return True
        return False

    def clamp_with_detection(self):
        flag = self.clamp()
        if flag:
            self.moveTo_upAndDown(self.coordinate_cur.zh - 1, self.coordinate_cur.zm)
            self.relax_thorough()
            self.hand.spiral(45)
            self.moveTo_upAndDown(self.coordinate_cur.zh + 1, self.coordinate_cur.zm)
            self.clamp()
            self.moveTo_upAndDown(0, self.coordinate_cur.zm)
            self.hand.spiral(0)

    def relax(self):
        self.hand.set_rj_clampTorque(50)
        self.hand.clamp_position(36)

    def relax_thorough(self):
        self.hand.set_rj_clampTorque(50)
        self.hand.clamp(0)

    def detect_hand_loose(self):
        self.clamp()
        pos = self.hand.query_rj_position()
        if pos >= self.hand_aim_position:
            self.emergence = True
            self.emergence_info = "hand does not clamp tight"
            return True
        return False

    def detect_mouth_suck(self):
        response = self.mouth.query_adp()
        if response == 'not sucked':
            self.emergence = True
            self.emergence_info = "mouth does not suck"
            return True
        return False

    def pickLip(self, num=-1):
        """
        取吸头（若 num=-1，则取当前 lip_num，然后自动递增）
        参数：
            num: 吸头编号（1~25）。若为 -1，则使用当前编号 self.lip_num。
        """
        auto = (num == -1)
        if auto:
            # 如果当前编号超过总数，重置为1（循环使用）
            if self.lip_num > len(self.lips_coordinates):
                self.lip_num = 1
            num = self.lip_num
            # 取用后立即递增，为下次做准备
            self.lip_num += 1
        co = self.getLipsCoordinate(num)
        if co is None:
            return
        # 先移动到吸头位置（下压到正常深度）
        self.moveTo(co)
        # 额外再往下压 2 个单位（让吸头套紧）
        co.zm += 2
        self.moveTo_upAndDown(0, co.zm)
        # 压紧后抬升到安全高度（防止取完后横移时刮擦）
        self.moveTo_upAndDown(0, Z_SAFE_MOUTH)
        # 如果自动模式，记录上次取的编号（可选）
        if auto:
            self.last_picked_num = num

    def relinquishLip(self, num=-1):
        """
        放回吸头（默认放回原处，不递增编号）
        参数：
            num: 吸头编号（1~25）。若为 -1，则放回当前编号 self.lip_num（已递增后的值，即上次使用的编号+1）
        """
        if num == -1:
            # 如果 lip_num 已被 pickLip 递增，这里需要取的是上次使用的编号
            if hasattr(self, 'last_picked_num'):
                num = self.last_picked_num
            else:
                num = self.lip_num - 1  # 回退一步
        co = self.getLipsCoordinate(num)
        if co is None:
            return
        # 1. 先向下多压 10 个单位，确保吸头完全插回孔位
        co.zm -= 10
        self.moveTo(co)
        # 2. 弹出吸头（移液器弹射机构动作）
        self.mouth.secedeTip()
        # 3. 放回后立即将移液器抬升到安全高度（zm=0），避免横移时碰撞
        self.moveTo_up_andDown(0, Z_SAFE_MOUTH)

    def suckFromBottleOne(self, vol):
        if(self.volume_current > 1e-9):
            print("sucking with liquids!!!!")

        self.volume_current += vol
        self.moveTo(self.coordinate_bottle_one_mouth)
        self.mouth.suck(vol)
        # if self.detect_mouth_suck(): self.moveTo(self.coordinate_origin)
        if self.detect_mouth_suck(): print("mouth does not suck")

    def suckFromBottleTwo(self, vol):
        if (self.volume_current > 1e-9):
            print("sucking with liquids!!!!")

        self.volume_current += vol
        self.moveTo(self.coordinate_bottle_two_mouth)
        self.mouth.suck(vol)

        # if self.detect_mouth_suck(): self.moveTo(self.coordinate_origin)
        if self.detect_mouth_suck(): print("mouth does not suck")

    def suckFromBottleThree(self, vol):
        if (self.volume_current > 1e-9):
            print("sucking with liquids!!!!")

        self.volume_current += vol
        self.moveTo(self.coordinate_bottle_three_mouth)
        self.mouth.suck(vol)
        # if self.detect_mouth_suck(): self.moveTo(self.coordinate_origin)
        if self.detect_mouth_suck(): print("mouth does not suck")

    def spitToSpinCoater(self, vol = -1):
        if vol == -1:
            vol = self.volume_current

        self.moveTo(self.coordinate_spinCoater_mouth)
        print("spit : ", vol)
        self.mouth.spit(0)
        self.volume_current = 0

    def pickGlassFromPlatform(self, num=1, flag=0):
        if num < 1 or num > 24:
            print('错误：玻璃编号必须在 1~24 之间')
            return
        aimCoordinate = self.glass_coordinates[num - 1]
        if aimCoordinate is None:
            print(f'错误：第 {num} 片玻璃未标定')
            return
        if flag:
            self.hand.spiral(90)
        else:
            self.hand.spiral(0)
        self.relax()
        self.moveTo(aimCoordinate)
        self.clamp_with_detection()

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def putToSpinCoater(self):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        aim = self.coordinate_spinCoater_hand.copy()
        aim.zh -= self.distance_spinCoater_pick_and_drop
        suspend = self.coordinate_spinCoater_hand.copy()
        suspend.zh = 0
        self.moveTo(suspend)
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        self.moveTo(aim)
        time.sleep(0.1)
        self.relax()

    def pickGlassFromSpinCoater(self):
        self.relax_thorough()
        self.moveTo(self.coordinate_spinCoater_hand)
        self.clamp_with_detection()

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def putToPlatform(self, num=1):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        if num < 1 or num > 24:
            print('错误：玻璃编号必须在 1~24 之间')
            return
        aimCoordinate = self.glass_coordinates[num - 1]
        if aimCoordinate is None:
            print(f'错误：第 {num} 片玻璃未标定')
            return
        # 注意放下时需要减去高度补偿
        zh = aimCoordinate.zh - self.distance_platform_pick_and_put
        self.moveTo(coordinate(aimCoordinate.x, aimCoordinate.y, zh, 0))
        self.relax()

    def pickGlassFromHeater(self, step = 1, num = 1, flag = 0): #flag = 1 : change to vertical direction to grab glass from heater whose space is limited
        aim = None
        if step == 1:
            if num == 1:
                aim = self.coordinate_heater_stepOne_first
            elif num == 2:
                aim = self.coordinate_heater_stepOne_second
            elif num == 3:
                aim = self.coordinate_heater_stepOne_third
            elif num == 4:
                aim = self.coordinate_heater_stepOne_fourth
            else:
                print('wrong input in pickGlassFromHeater: num')
                return
        elif step == 2:
            if num == 1:
                aim = self.coordinate_heater_stepTwo_first
            elif num == 2:
                aim = self.coordinate_heater_stepTwo_second
            elif num == 3:
                aim = self.coordinate_heater_stepTwo_third
            elif num == 4:
                aim = self.coordinate_heater_stepTwo_fourth
            else:
                print('wrong input in pickGlassFromHeater: num')
                return
        else:
            print('wrong input in pickGlassFromHeater: step')
            return
        suspend = coordinate(aim.x, aim.y, 0, 0)
        if flag:
            self.moveTo(suspend)
            self.hand.spiral(90)
            self.relax() # not sure whether this should be thorough
            self.moveTo(aim)
            self.clamp_with_detection()
            self.moveTo(suspend)
            self.hand.spiral(0)
        else:
            self.hand.spiral(0)
            self.relax()
            self.moveTo(aim)
            self.clamp_with_detection()

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def putToHeater(self, step = 1, num = 1, flag = 0):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        aim = None
        if step == 1:
            if num == 1:
                aim = self.coordinate_heater_stepOne_first
            elif num == 2:
                aim = self.coordinate_heater_stepOne_second
            elif num == 3:
                aim = self.coordinate_heater_stepOne_third
            elif num == 4:
                aim = self.coordinate_heater_stepOne_fourth
            else:
                print('wrong input in putToHeater: num')
                return
        elif step == 2:
            if num == 1:
                aim = self.coordinate_heater_stepTwo_first
            elif num == 2:
                aim = self.coordinate_heater_stepTwo_second
            elif num == 3:
                aim = self.coordinate_heater_stepTwo_third
            elif num == 4:
                aim = self.coordinate_heater_stepTwo_fourth
            else:
                print('wrong input in putToHeater: num')
                return
        else:
            print('wrong input in putToHeater: step')
            return
        suspend = coordinate(aim.x, aim.y, 0, 0)
        if flag:
            self.moveTo(suspend)
            self.hand.spiral(90)
            self.moveTo(aim)
            self.relax()
            self.moveTo(suspend)
            self.hand.spiral(0)
        else:
            self.hand.spiral(0)
            self.moveTo(aim)
            self.relax()

    def openBottleOne(self):
        self.relax_thorough()
        self.hand.spiral(0)
        self.moveTo(self.coordinate_bottle_one_hand)
        self.clamp()
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        self.hand.spiral(-self.deg_bottle_one)

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def closeBottleOne(self):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return

        self.moveTo(self.coordinate_bottle_one_hand)
        self.hand.spiral(0)  # be careful !!!!!!!!!!!!!!!!!!!!!!
        self.relax_thorough()

    def openBottleTwo(self):
        self.relax_thorough()
        self.hand.spiral(0)
        self.moveTo(self.coordinate_bottle_two_hand)
        self.clamp()
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        self.hand.spiral(-self.deg_bottle_two)

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def closeBottleTwo(self):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return

        self.moveTo(self.coordinate_bottle_two_hand)
        self.hand.spiral(0)  # be careful !!!!!!!!!!!!!!!!!!!!!!
        self.relax_thorough()

    def openBottleThree(self):
        self.relax_thorough()
        self.hand.spiral(0)
        self.moveTo(self.coordinate_bottle_three_hand)
        self.clamp()
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        self.hand.spiral(-self.deg_bottle_three)

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def closeBottleThree(self):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return

        self.moveTo(self.coordinate_bottle_three_hand)
        self.hand.spiral(0)  # be careful !!!!!!!!!!!!!!!!!!!
        self.relax_thorough()

    def prepareForGlass_onlyTheFirstPosition(self, num):
        aimCoordinate = self.coordinate_glass_first

        self.moveTo(aimCoordinate)
        self.clamp()
        self.relax()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(90)
        self.moveTo_upAndDown(aimCoordinate.zh, 0)
        self.clamp()
        self.relax()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(0)

    def prepareForHeater(self, step = 1, num = 1):
        aimCoordinate = None
        if step == 1:
            if num == 1:
                aimCoordinate = self.coordinate_heater_stepOne_first
            elif num == 2:
                aimCoordinate = self.coordinate_heater_stepOne_second
            elif num == 3:
                aimCoordinate = self.coordinate_heater_stepOne_third
            elif num == 4:
                aimCoordinate = self.coordinate_heater_stepOne_fourth
            else:
                print('wrong input in prepareForHeater: num')
                return
        elif step == 2:
            if num == 1:
                aimCoordinate = self.coordinate_heater_stepTwo_first
            elif num == 2:
                aimCoordinate = self.coordinate_heater_stepTwo_second
            elif num == 3:
                aimCoordinate = self.coordinate_heater_stepTwo_third
            elif num == 4:
                aimCoordinate = self.coordinate_heater_stepTwo_fourth
            else:
                print('wrong input in prepareForHeater: num')
                return
        else:
            print('wrong input in prepareForHeater: step')
            return

        self.moveTo(aimCoordinate)
        self.clamp()
        self.relax()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(90)
        self.moveTo_upAndDown(aimCoordinate.zh, 0)
        self.clamp()
        self.relax()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(0)

    def putToEvacuationSpace(self):
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        self.moveTo(self.coordinate_evacuation_space)
        self.relax()

    def pickGlassFromEvacuationSpace(self):
        self.moveTo(self.coordinate_evacuation_space)
        self.clamp_with_detection()

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def OneStepMethod_A(self, id, vol = 30, spinInfoList = None):
        if spinInfoList is None:
            spinInfoList = [SpinInfo(1500, 10, 1, 1)]
        self.prepareForMultiGlass(id)
        self.pickGlassFromPlatform(id)
        self.putToSpinCoater()
        self.pickLip(1)
        self.openBottleThree()
        self.suckFromBottleThree(vol)  # 30
        self.closeBottleThree()
        self.spitToSpinCoater(-1)
        self.spin(spinInfoList, mode="position")
        self.relinquishLip(1)

    def OneStepMethod_B(self, vol = 30):
        self.pickLip(2)
        self.openBottleTwo()
        self.suckFromBottleTwo(vol)  # 30
        self.closeBottleTwo()
        self.moveTo(self.coordinate_spinCoater_wait_mouth)
        self.spitToSpinCoater(-1)
        self.moveTo_upAndDown(0,0)

    def OneStepMethod_H(self, id):
        self.moveTo(self.coordinate_spinCoater_wait_hand)
        self.pickGlassFromSpinCoater()
        heater_id = self.Heater_All.AssignGlass(id) #这里改了，用heater_all替代了heater1
        self.putToHeater((heater_id - 1) // 4 + 1, (heater_id - 1) % 4 + 1)
        self.spinCoater.returnToOriginOfSingleRevolution_notBlocked()
        self.relinquishLip(2)  #加热后再放回滴管
        self.moveTo(self.coordinate_origin)

    def OneStepMethod_T(self, id):
        print("in T")
        heater_id = self.Heater_All.RemoveGlass(id)
        self.pickGlassFromHeater((heater_id - 1) // 4 + 1, (heater_id - 1) % 4 + 1)
        self.putToPlatform(id)
        self.moveTo(self.coordinate_origin)

    def LBF(self):
        self.spinCoater.returnToOriginOfSingleRevolution(type='glass')
        self.moveTo(brain.coordinate_origin)
        self.prepareForGlass_onlyTheFirstPosition(1)
        self.pickGlassFromPlatform(1)
        self.putToSpinCoater()
        self.pickLip(1)
        self.openBottleTwo()
        self.suckFromBottleTwo(30)
        self.closeBottleTwo()
        self.spitToSpinCoater(-1)
        self.spin([SpinInfo(1500, 10, 1, 1)], mode = "position")
        self.relinquishLip(1)
        self.moveTo(brain.coordinate_spinCoater_wait_hand)
        time.sleep(4)  # 旋涂后等待测试
        self.pickGlassFromSpinCoater()
        self.putToHeater(2,1)
        self.moveTo(brain.coordinate_origin)
        #time.sleep(10)  # step 1 heating
        self.pickGlassFromHeater(2,1)
        self.putToPlatform(1)
        self.prepareForGlass_onlyTheFirstPosition(1)
        self.pickGlassFromPlatform(1)
        self.putToSpinCoater()
        self.pickLip(2)
        self.openBottleOne()
        self.suckFromBottleOne(30)
        self.closeBottleOne()
        self.spitToSpinCoater(-1)
        self.spin([SpinInfo(2000, 10, 1, 1)], mode = "position")
        self.relinquishLip(2)
        self.moveTo(brain.coordinate_spinCoater_wait_hand)
        time.sleep(5)  # 旋涂后等待测试
        self.pickGlassFromSpinCoater()
        self.putToHeater(1,1)
        self.moveTo(brain.coordinate_origin)
        #time.sleep(10)  # step 2 heating test
        self.pickGlassFromHeater(1,1)
        self.putToPlatform(1)
        self.moveTo(brain.coordinate_origin)

    def YBF(self, params : dict):
        self.spinCoater.returnToOriginOfSingleRevolution(type='glass')
        self.moveTo(brain.coordinate_origin)
        self.prepareForGlass_onlyTheFirstPosition(1)
        self.pickGlassFromPlatform(1)
        self.putToSpinCoater()
        self.pickLip(1)
        self.openBottleTwo()
        self.suckFromBottleTwo(params['SolutionOneVolume'])#30
        self.closeBottleTwo()
        self.spitToSpinCoater(-1)
        self.relinquishLip(1)
        self.pickLip(2)
        self.spin(params['SpinOneParams'], mode = "position")
        self.openBottleOne()
        self.suckFromBottleOne(params['SolutionTwoVolume'])#30
        self.closeBottleOne()
        self.moveTo(brain.coordinate_spinCoater_wait_mouth)
        self.spitToSpinCoater(-1)
        self.relinquishLip(2)
        self.moveTo(brain.coordinate_spinCoater_wait_hand)
        time.sleep(10 + params['SpinOneParams'][0].spinTime - 38 + 2)
        self.pickGlassFromSpinCoater()
        self.putToHeater(1,1)
        self.moveTo(brain.coordinate_origin)
        #time.sleep(10)  # step 2 heating test
        time.sleep(params['HeatingOneTime'])
        self.pickGlassFromHeater(1,1)
        self.putToPlatform(1)
        self.moveTo(brain.coordinate_origin)

    def testSpin(self):
        #self.moveTo(brain.coordinate_origin)

        self.pickGlassFromPlatform(1)
        self.putToSpinCoater()

        #for i in range(10):
        self.spin([SpinInfo(3000, 10, 1, 1)], mode="position")
        self.moveTo(self.coordinate_origin)
        time.sleep(15)

        self.pickGlassFromSpinCoater()
        self.putToPlatform(1)
        self.moveTo(self.coordinate_origin)

    def zksz(self):
        """
        完整工艺流程（直接使用硬编码坐标，每步之间延时 1s）
        吸头：先用 (3,4) 坐标 98.4 3.5 99，再用 (3,5) 坐标 96.1 3.5 99
        丢吸头时移液器 Z 轴高度设为 90
        """
        # ========== 所有坐标直接定义 ==========
        # 吸头坐标
        lip1_x, lip1_y, lip1_z = 97.7, 1.8, 99  # (3,5)
        lip2_x, lip2_y, lip2_z = 95.3, 1.8, 99  # (3,6)
        lip_drop_z = 90  # 丢吸头时移液器 Z 轴高度

        # 旋涂仪
        sc_hand_x, sc_hand_y, sc_hand_z = 46.5, 65.5, 87
        sc_mouth_x, sc_mouth_y, sc_mouth_z = 56.0, 87.8, 18

        # 1号瓶
        b1_hand_x, b1_hand_y, b1_hand_z = 47.3, 11.0, 80
        b1_mouth_x, b1_mouth_y, b1_mouth_z = 56.7, 33.5, 45
        b1_deg = 360

        # 3号瓶
        b3_hand_x, b3_hand_y, b3_hand_z = 39.8, 24.9, 80
        b3_mouth_x, b3_mouth_y, b3_mouth_z = 49.2, 47.0, 45
        b3_deg = 360

        # 玻璃位置（第2块）
        glass_x, glass_y, glass_z = 88.7, 19.0, 87.5

        # 退火台
        heater_x, heater_y, heater_z = 15, 10, 75

        # 真空泵
        vacuum_x, vacuum_y, vacuum_z = 0, 97, 96.5

        # 安全高度
        Z_SAFE_HAND = 1.0
        Z_SAFE_MOUTH = 0.0

        # ========== 辅助函数 ==========
        def move_hand(x, y, z):
            self.moveTo(coordinate(x, y, z, Z_SAFE_MOUTH))

        def move_mouth(x, y, z):
            self.moveTo(coordinate(x, y, Z_SAFE_HAND, z))

        def pick_glass(x, y, z):
            move_hand(x, y, z)
            self.clamp_with_detection()
            if self.detect_hand_loose():
                print('hand loose when picking glass')
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def put_glass(x, y, z):
            move_hand(x, y, z)
            self.relax()
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def pick_lip(x, y, z):
            move_mouth(x, y, z)
            # self.moveTo_upAndDown(Z_SAFE_HAND, z + 2)  # 额外下压 2 个单位
            # self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def drop_lip(x, y):
            move_mouth(x, y, lip_drop_z)
            self.mouth.secedeTip()
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def open_bottle(x, y, z, deg):
            move_hand(x, y, z)
            self.relax_thorough()
            self.hand.spiral(0)
            self.clamp()
            if self.detect_hand_loose():
                print('hand loose when opening bottle')
            self.hand.spiral(-deg)
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def close_bottle(x, y, z):
            move_hand(x, y, z)
            self.hand.spiral(0)
            self.relax_thorough()
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            #self.hand.spiral(deg)
            time.sleep(1)

        def suck(x, y, z, vol):
            move_mouth(x, y, z)
            self.mouth.suck(vol)
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def spit(x, y, z, vol=0):
            move_mouth(x, y, z)
            self.mouth.spit(vol)
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        # ========== 开始流程 ==========

        # 1. 从平台取第2块玻璃 -> 放到旋涂仪
        print("取玻璃...")
        pick_glass(glass_x, glass_y, glass_z)
        print("放到旋涂仪...")
        put_glass(sc_hand_x, sc_hand_y, sc_hand_z)

        # 2. 取第一根吸头 (3,4)
        print("取吸头 1...")
        pick_lip(lip1_x, lip1_y, lip1_z)

        # 3. 开1号瓶
        print("开1号瓶...")
        open_bottle(b1_hand_x, b1_hand_y, b1_hand_z, b1_deg)

        # 4. 吸 SAM 100 微升
        print("吸 SAM...")
        suck(b1_mouth_x, b1_mouth_y, b1_mouth_z, 100)

        # 5. 关1号瓶
        print("关1号瓶...")
        close_bottle(b1_hand_x, b1_hand_y, b1_hand_z)

        # 6. 滴到旋涂仪
        print("滴 SAM...")
        spit(sc_mouth_x, sc_mouth_y, sc_mouth_z)

        # 7. 旋涂 SAM（5000rpm, 30s, 加速度5000 → 加速时间1.0s）
        print("旋涂 SAM...")
        spin1 = [SpinInfo(speed=5000, spinTime=10, acceleratingTime=1.0, deceleratingTime=1.0)]
        self.spinCoater.spin(spin1, mode="speed")
        time.sleep(1)

        # 8. 旋涂期间放回吸头 (3,4)
        print("放回吸头 1...")
        drop_lip(lip1_x, lip1_y)

        # 9. 等待旋涂结束
        print("等待 SAM 旋涂结束...")
        if self.spinCoater.spinThread.is_alive():
            self.spinCoater.spinThread.join()
        time.sleep(1)

        # 21. 打开真空泵盖子
        print("打开真空泵盖子...")
        self.evacuationSpace.openLid()
        time.sleep(1)

        # 22. 从旋涂仪取玻璃 -> 放到真空泵
        print("从旋涂仪取玻璃...")
        pick_glass(sc_hand_x, sc_hand_y, sc_hand_z)
        print("放到真空泵...")
        put_glass(vacuum_x, vacuum_y, vacuum_z)

        # 23. 关闭真空泵盖子
        print("关闭真空泵盖子...")
        self.evacuationSpace.closeLid()
        time.sleep(1)

        # 24. 打开电磁阀，20s 后关闭
        print("打开电磁阀...")
        self.valve.setPowerOn()
        time.sleep(10)
        print("关闭电磁阀...")
        self.valve.setPowerOff()
        time.sleep(1)

        # 25. 打开真空泵盖子
        print("打开真空泵盖子...")
        self.evacuationSpace.openLid()
        time.sleep(1)

        # 26. 从真空泵取玻璃 -> 放到退火台
        print("从真空泵取玻璃...")
        pick_glass(vacuum_x, vacuum_y, vacuum_z)
        print("放到退火台...")
        put_glass(heater_x, heater_y, heater_z)

        # 27. 关闭真空泵盖子
        print("关闭真空泵盖子...")
        self.evacuationSpace.closeLid()
        time.sleep(1)

        # 28. 退火 20 分钟
        print("退火 20 分钟...（本次为模拟实验，模拟退火10秒）")
        time.sleep(10)

        # 29. 从退火台取玻璃 -> 放回原平台位置
        print("从退火台取玻璃...")
        pick_glass(heater_x, heater_y, heater_z)
        print("放回原平台...")
        put_glass(glass_x, glass_y, glass_z)

        print("zksz 流程完成。")



    def close(self):
        self.hand.close()
        self.mouth.close()
        self.leg.close()
        self.spinCoater.close()
        self.evacuationSpace.close()
        self.valve.close()


    #dx,dy = 8.7 24.5
    def config(self):
        # 手爪抓放玻璃的精确坐标
        self.coordinate_spinCoater_hand = coordinate(48.5, 64.5, 87.1, 0)
        # 放置玻璃时手爪从上方再下降的距离（保持原值，可后续微调）
        self.distance_spinCoater_pick_and_drop = 0.5
        # 手爪等待位置（X、Y 与 hand 相同，Z 抬到安全高度）
        self.coordinate_spinCoater_wait_hand = coordinate(48.5, 64.5, 0, 0)
        # 移液器滴液坐标
        self.coordinate_spinCoater_mouth = coordinate(57.2, 90.0, 0, 18)
        # 移液器等待位置（X、Y 与 mouth 相同，Z 抬到安全高度）
        self.coordinate_spinCoater_wait_mouth = coordinate(57.2, 90.0, 0, 0)
        self.coordinate_origin = coordinate(0, 0, 0, 0)

        self.glass_coordinates = [coordinate(0, 0, 0, 0) for _ in range(24)]  #玻璃坐标
        self.distance_platform_pick_and_put = 0.5

        # self.coordinate_lips_first = coordinate(110, 1.5, 0, 99)#94
        # self.coordinate_lips_12th = coordinate(85.15, 1.5, 0, 99)
        # self.coordinate_lips_manyth = coordinate(85.15, 47.5, 0, 0)#待改

        self.coordinate_garbage = coordinate(30, 0, 0, 0)

        # 1-3号瓶子手爪坐标
        self.coordinate_bottle_one_hand = coordinate(48.2, 12.2, 80, 0)
        self.coordinate_bottle_two_hand = coordinate(40.8, 11.7, 80, 0)
        self.coordinate_bottle_three_hand = coordinate(41.6, 26.7, 80, 0)
        #1-3号瓶子移液器坐标
        self.coordinate_bottle_one_mouth = coordinate(58.0, 36.0, 0, 45)
        self.coordinate_bottle_two_mouth = coordinate(49.5, 34.0, 0, 45)
        self.coordinate_bottle_three_mouth = coordinate(49.2, 50.0, 0, 45)


        self.coordinate_heater_stepOne_first = coordinate(0, 6, 53.9, 0)#45
        self.coordinate_heater_stepTwo_first = coordinate(0, 41, 53.9, 0)#45
        self.coordinate_heater_stepOne_second = coordinate(8.3, 6, 53.9, 0)#45
        self.coordinate_heater_stepTwo_second = coordinate(8.3, 41, 53.9, 0)#45
        self.coordinate_heater_stepOne_third = coordinate(0, 19, 53.9, 0)#45
        self.coordinate_heater_stepTwo_third = coordinate(0, 54, 53.9, 0)#45
        self.coordinate_heater_stepOne_fourth = coordinate(8.3, 19, 53.9, 0)#45
        self.coordinate_heater_stepTwo_fourth = coordinate(8.3, 54, 53.9, 0)#45

        self.coordinate_evacuation_space = coordinate(25, 100, 90.6, 0)

        self.deg_bottle_one = 720
        self.deg_bottle_two = self.deg_bottle_one
        self.deg_bottle_three = self.deg_bottle_one
        # self.lips_distance_x = (self.coordinate_lips_first.x - self.coordinate_lips_12th.x) / 11.0
        # self.lips_distance_y = (self.coordinate_lips_manyth.y - self.coordinate_lips_12th.y) / 6.0

        self.volume_current = 0.0
        self.hand_aim_position = 70

        # ----- 直接存储24片玻璃的精确坐标（按索引赋值）-----
        self.glass_coordinates = [None] * 24  # 索引 0~23 对应编号 1~24

        # 第1行
        self.glass_coordinates[0] = coordinate(95.3, 19.0, 87.5, 0)  # 1号
        self.glass_coordinates[1] = coordinate(88.7, 19.0, 87.5, 0)  # 2号
        self.glass_coordinates[2] = coordinate(79.1, 19.0, 87.5, 0)  # 3号
        self.glass_coordinates[3] = coordinate(72.6, 19.0, 87.5, 0)  # 4号

        # 第2行
        self.glass_coordinates[4] = coordinate(95.5, 32.0, 87.5, 0)  # 5号
        self.glass_coordinates[5] = coordinate(88.7, 32.0, 87.5, 0)  # 6号
        self.glass_coordinates[6] = coordinate(79.2, 32.0, 87.5, 0)  # 7号
        self.glass_coordinates[7] = coordinate(72.5, 32.0, 87.5, 0)  # 8号

        # 第3行
        self.glass_coordinates[8] = coordinate(95.5, 45.5, 87.5, 0)  # 9号
        self.glass_coordinates[9] = coordinate(88.7, 45.5, 87.5, 0)  # 10号
        self.glass_coordinates[10] = coordinate(79.1, 45.5, 87.5, 0)  # 11号
        self.glass_coordinates[11] = coordinate(72.6, 45.5, 87.5, 0)  # 12号

        # 第4行
        self.glass_coordinates[12] = coordinate(95.5, 59.3, 87.5, 0)  # 13号
        self.glass_coordinates[13] = coordinate(88.7, 59.3, 87.5, 0)  # 14号
        self.glass_coordinates[14] = coordinate(79.3, 59.3, 87.5, 0)  # 15号
        self.glass_coordinates[15] = coordinate(72.6, 59.3, 87.5, 0)  # 16号

        # 第5行
        self.glass_coordinates[16] = coordinate(95.7, 73.2, 87.5, 0)  # 17号
        self.glass_coordinates[17] = coordinate(88.9, 73.2, 87.5, 0)  # 18号
        self.glass_coordinates[18] = coordinate(79.4, 73.2, 87.5, 0)  # 19号
        self.glass_coordinates[19] = coordinate(72.7, 73.2, 87.5, 0)  # 20号

        # 第6行
        self.glass_coordinates[20] = coordinate(95.5, 86.7, 87.5, 0)  # 21号
        self.glass_coordinates[21] = coordinate(88.9, 86.2, 87.5, 0)  # 22号
        self.glass_coordinates[22] = coordinate(79.4, 86.2, 87.5, 0)  # 23号
        self.glass_coordinates[23] = coordinate(72.9, 86.7, 87.5, 0)  # 24号

        # # ----- 玻璃平台配置（4列×6行，共24片）-----
        # self.glass_z = 88
        #
        # # 第一列X坐标（所有行第一列相同）—— 按1号玻璃 x=95.3
        # x_first_col = 95.3
        #
        # # 列间距（从左到右）：第1→2, 2→3, 3→4
        # col_spacings = [6.6, 9.6, 6.5]
        #
        # # 计算各列X坐标（相对于第一列向左偏移）
        # x_offsets = [0.0]
        # for d in col_spacings:
        #     x_offsets.append(x_offsets[-1] + d)
        #
        # # 各列实际X坐标
        # col_x = [x_first_col - offset for offset in x_offsets]
        # # col_x = [95.3, 88.7, 79.1, 72.6]
        #
        # # 行参数—— 按1号玻璃 y=19.0
        # first_row_y = 19.0  # 第一行坐标
        # row_spacing = 13.54  # 行间距
        #
        # # 各行Y坐标
        # row_y = [first_row_y + i * row_spacing for i in range(6)]
        # # row_y = [19.0, 32.54, 46.08, 59.62, 73.16, 86.7]
        #
        # # ----- 生成24块玻璃坐标 -----
        # self.glass_coordinates = []
        # for row in range(6):  # 6行
        #     y = first_row_y + row * row_spacing
        #     for col in range(4):  # 4列
        #         x = col_x[col]
        #         self.glass_coordinates.append(coordinate(x, y, self.glass_z, 0))
        #
        # # ----- 用实测值覆盖第21和第24块玻璃坐标（下方两个对角）-----
        # # 编号21 → 索引20；编号24 → 索引23
        # self.glass_coordinates[20] = coordinate(95.4, 86.7, 88, 0)  # 21号玻璃
        # self.glass_coordinates[23] = coordinate(72.9, 86.7, 88, 0)  # 24号玻璃

        # ========== 吸头坐标（5行×5列，共25个） ==========
        # 已知：第三排第四列 (行3,列4) 坐标 (101.3, 4.8)，zm=93
        # 列间距 dx = 2.2（列号增加，X减小），行间距 dy = 4.5（行号增加，Y增大）
        center_x = 101.3
        center_y = 4.8
        dx = 2.2
        dy = 4.5
        zm_lip = 93

        # 生成行号1~5，列号2~6
        self.lips_coordinates = []
        for row in range(1, 6):  # 1~5行
            y = center_y + (row - 3) * dy
            for col in range(2, 7):  # 2~6列
                x = center_x + (4 - col) * dx  # 列号越大X越小
                self.lips_coordinates.append(coordinate(x, y, 0, zm_lip))


    def prepareForSpinCoater(self):
        aimCoordinate = self.coordinate_spinCoater_hand
        self.relax_thorough()
        self.moveTo(aimCoordinate)
        self.clamp()
        self.relax_thorough()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(90)
        self.moveTo_upAndDown(aimCoordinate.zh, 0)
        self.clamp()
        self.relax_thorough()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(0)

    def prepareForMultiGlass(self, num):
        if num < 1 or num > 24:
            print('错误：玻璃编号必须在 1~24 之间')
            return
        aimCoordinate = self.glass_coordinates[num - 1]
        if aimCoordinate is None:
            print(f'错误：第 {num} 片玻璃未标定')
            return
        self.relax()
        self.hand.spiral(0)
        self.moveTo(aimCoordinate)
        self.clamp()
        self.relax()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(90)
        self.moveTo_upAndDown(aimCoordinate.zh, 0)
        self.clamp()
        self.relax()
        self.moveTo_upAndDown(aimCoordinate.zh - 10, 0)
        self.hand.spiral(0)

    def returnToOrigin_x(self):  # stop at 21.43
        x_0 = self.leg.getCurrentPos_x()
        y_0 = self.leg.getCurrentPos_y()
        if x_0 <= 25:
            self.leg.moveTo_x(30, ignore_limit=True)
            self.leg.wait_x()
        x_0 = self.leg.getCurrentPos_x()
        y_0 = self.leg.getCurrentPos_y()
        print("start in : ", x_0, y_0)
        # for i in range(100):
        #     self.leg.moveTo_x(x_0 - i, ignore_limit=True)
        #     self.leg.wait_x()
        #     if self.positionSensor.detection_x():
        #         x_0 = x_0 - i
        #         break
        print("进入回零循环，x_0 =", x_0)
        for i in range(100):
            target_x = x_0 - i
            print(f"i={i}, 准备移动到 {target_x}")
            self.leg.moveTo_x(target_x, ignore_limit=True)
            print("moveTo_x 执行完毕")
            self.leg.wait_x()
            print("wait_x 执行完毕")
            sensor = self.positionSensor.detection_x()
            print(f"传感器状态: {sensor}")
            if sensor:
                x_0 = target_x
                print("传感器触发，跳出循环")
                break
        else:
            print("循环正常结束，未触发传感器")
        print("循环结束，x_0 =", x_0)

        print("end in : ", x_0, y_0)
        self.leg.moveTo_x(x_0 - 2.54, ignore_limit=True)
        self.leg.wait_x()
        x_0 = self.leg.getCurrentPos_x()
        print("restart in : ", x_0, y_0)
        for i in range(100):
            self.leg.moveTo_x(x_0 - (i + 1) * 0.02, ignore_limit=True)
            self.leg.wait_x()
            if not self.positionSensor.detection_x():
                break
            if (i == 99) & (self.positionSensor.detection_x()):
                print("Number of cycles is insufficient")
        x_0 = self.leg.getCurrentPos_x()
        print("end in : ", x_0, y_0)
        self.leg.moveTo_x(x_0 - 21.43, ignore_limit=True)
        self.leg.wait_x()
        x_0 = self.leg.getCurrentPos_x()
        print("result in :", x_0, y_0)

    def returnToOrigin_y(self):  # stop at 11.835
        x_0 = self.leg.getCurrentPos_x()
        y_0 = self.leg.getCurrentPos_y()
        if y_0 <= 15:
            self.leg.moveTo_y(20, ignore_limit=True)
            self.leg.wait_y()
        x_0 = self.leg.getCurrentPos_x()
        y_0 = self.leg.getCurrentPos_y()
        print("start in : ", x_0, y_0)
        for i in range(150):
            self.leg.moveTo_y(y_0 - i, ignore_limit=True)
            self.leg.wait_y()
            if self.positionSensor.detection_y():
                y_0 = y_0 - i
                break
        print("end in : ", x_0, y_0)
        self.leg.moveTo_y(y_0 - 2.5, ignore_limit=True)
        self.leg.wait_y()
        y_0 = self.leg.getCurrentPos_y()
        print("restart in : ", x_0, y_0)
        for i in range(100):
            self.leg.moveTo_y(y_0 - (i + 1) * 0.03, ignore_limit=True)
            self.leg.wait_y()
            if not self.positionSensor.detection_y():
                break
            if (i == 99) & (self.positionSensor.detection_y()):
                print("Number of cycles is insufficient")
        y_0 = self.leg.getCurrentPos_y()
        print("end in : ", x_0, y_0)
        self.leg.moveTo_y(y_0 - 12.055, ignore_limit=True)
        self.leg.wait_y()
        y_0 = self.leg.getCurrentPos_y()
        print("result in :", x_0, y_0)

    def returnToOrigin(self):
        self.returnToOrigin_x()
        self.returnToOrigin_y()
        print("result in finally: ", self.leg.getCurrentPos_x(), self.leg.getCurrentPos_y())


# if __name__ == '__main__':
#     try:
#         brain = masterController()
#         brain.moveTo(brain.coordinate_spinCoater_hand)
#         # 旋涂: 300转/秒, 加速10秒, 旋转20秒
#         brain.spin([SpinInfo(300, 10, 20, 1)], mode="position")
#         time.sleep(22)
#         #brain.moveTo(brain.coordinate_glass_first)
#         '''brain.evacuationSpace.openLid()
#         brain.evacuationSpace.closeLid()
#         time.sleep(0.2)
#         brain.valve.setPowerOn()
#         time.sleep(10)
#         brain.valve.setPowerOff()
#         time.sleep(0.2)
#         brain.evacuationSpace.openLid()
#         brain.evacuationSpace.closeLid()'''
#         #brain.relinquishLip(1)
#         '''testSpin = [SpinInfo(speed=1000, acceleratingTime=1, spinTime=1)]
#         for i in range(10):
#             brain.spinCoater.returnToOriginOfSingleRevolution_notBlocked(type='glass')
#             brain.spin(testSpin, mode="position")
#             print(i + 1)'''
#
#         '''for i in range(13, 19):
#             brain.spinCoater.returnToOriginOfSingleRevolution_notBlocked(type = 'glass')
#             brain.pickGlassFromPlatform(i+1)
#             brain.putToSpinCoater()
#             brain.prepareForSpinCoater()
#             brain.spin(params['SpinOneParams'], mode="position")
#             time.sleep(18)
#             brain.pickGlassFromSpinCoater()
#             brain.putToPlatform(i+1)
#         brain.moveTo(brain.coordinate_origin)'''
#
#         #brain.hand.spiral(0)
#         #brain.moveTo(brain.coordinate_glass_twentieth)
#         #brain.moveTo(brain.coordinate_evacuation_space)
#         #brain.moveTo(brain.coordinate_heater_stepTwo_second)
#
#         #brain.testSpin()
#
#         '''for i in range(19,24):
#             brain.spinCoater.returnToOriginOfSingleRevolution_notBlocked(type='glass')
#             brain.relax()
#             # brain.prepareForMultiGlass(1)
#             brain.pickGlassFromPlatform(i+1)
#             brain.putToSpinCoater()
#             brain.prepareForSpinCoater()
#             brain.pickLip(1)
#             brain.openBottleThree()
#             brain.suckFromBottleThree(params['SolutionOneVolume'])  # 30
#             brain.closeBottleThree()
#             brain.spitToSpinCoater(-1)
#             brain.relinquishLip(1)
#             brain.moveTo(brain.coordinate_origin)
#             brain.spin(params['SpinOneParams'], mode="position")
#             time.sleep(18)
#             brain.evacuationSpace.openLid()  # 动盖子之前保证机械臂在原点！！！
#             brain.pickGlassFromSpinCoater()
#             brain.putToEvacuationSpace()
#             brain.moveTo(brain.coordinate_origin)
#             brain.evacuationSpace.closeLid()
#             time.sleep(0.2)
#             brain.valve.setPowerOn()
#             time.sleep(10)
#             brain.valve.setPowerOff()
#             time.sleep(0.2)
#             brain.evacuationSpace.openLid()
#             brain.pickGlassFromEvacuationSpace()
#             brain.putToHeater(1, 1,)
#             brain.moveTo(brain.coordinate_origin)
#             # brain.heat(params['HeatingOneTime'])
#             brain.evacuationSpace.closeLid()
#             # time.sleep(params['HeatingOneTime'])
#             brain.pickGlassFromHeater(1, 1, 0)
#             brain.putToPlatform(i+1)
#         brain.moveTo(brain.coordinate_origin)'''
#
#         #brain.moveTo(brain.coordinate_evacuation)
#         #brain.returnToOrigin_x()
#         #brain.evacuationSpace.openLid()
#         #brain.moveTo(brain.coordinate_glass_first)
#
#         '''brain.spinCoater.returnToOriginOfSingleRevolution_notBlocked(type = 'glass')
#         brain.relax()
#         #brain.prepareForMultiGlass(1)
#         brain.pickGlassFromPlatform(1)
#         brain.putToSpinCoater()
#         brain.prepareForSpinCoater()
#         brain.pickLip(1)
#         brain.openBottleThree()
#         brain.suckFromBottleThree(params['SolutionOneVolume'])  # 30
#         brain.closeBottleThree()
#         brain.spitToSpinCoater(-1)
#         brain.relinquishLip(1)
#         brain.moveTo(brain.coordinate_origin)
#         brain.spin(params['SpinOneParams'], mode="position")
#         time.sleep(18)
#         brain.evacuationSpace.openLid()   #动盖子之前保证机械臂在原点！！！
#         brain.pickGlassFromSpinCoater()
#         brain.putToEvacuationSpace()
#         brain.moveTo(brain.coordinate_origin)
#         brain.evacuationSpace.closeLid()
#         time.sleep(0.2)
#         brain.valve.setPowerOn()
#         time.sleep(10)
#         brain.valve.setPowerOff()
#         time.sleep(0.2)
#         brain.evacuationSpace.openLid()
#         brain.pickGlassFromEvacuationSpace()
#         brain.putToHeater(1, 1)
#         brain.moveTo(brain.coordinate_origin)
#         #brain.heat(params['HeatingOneTime'])
#         brain.evacuationSpace.closeLid()
#         #time.sleep(params['HeatingOneTime'])
#         brain.pickGlassFromHeater(1, 1, 0)
#         brain.putToPlatform(1)
#         brain.moveTo(brain.coordinate_origin)'''
#
#
#         # brain.YBF_2(params,3)'''
#
#
#         '''brain.OneStepMethod_A(1, spinInfoList=[SpinInfo(2000, 10, 1, 1)])
#         time.sleep(10)
#         brain.OneStepMethod_B()
#         brain.OneStepMethod_H(1)
#         brain.OneStepMethod_T(1)
#         '''
#         brain.close()
#     except Exception as e:
#         brain.moveTo(brain.coordinate_origin)
#         brain.close()
#         raise e
#
#         #current y : platform_hand 1

#读取玻璃片准确值
# if __name__ == '__main__':
#     brain = masterController()
#     brain.init()
#     brain.moveTo(brain.coordinate_origin)  # 初始化 coordinate_cur
#
#     print("===== 标定玻璃平台四个角点 =====")
#     print("命令说明：")
#     print("  p            -> 打印当前位置 (X, Y, ZH, ZM)")
#     print("  m x y        -> 移动滑轨到 (x, y) 百分比位置")
#     print("  zh 值        -> 设置手爪Z高度 (例如 zh 60)")
#     print("  zm 值        -> 设置注射泵Z高度 (例如 zm 20)")
#     print("  s 名称       -> 保存当前坐标为指定的变量名 (例如 s coordinate_glass_first)")
#     print("  q            -> 退出")
#
#     current_zh = 0.0
#     current_zm = 0.0
#
#     while True:
#         cmd = input("> ").strip()
#         if cmd == 'q':
#             break
#         elif cmd == 'p':
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             print(f"当前位置: X={x:.2f}, Y={y:.2f}, ZH={current_zh:.2f}, ZM={current_zm:.2f}")
#         elif cmd.startswith('m '):
#             parts = cmd.split()
#             if len(parts) == 3:
#                 try:
#                     x = float(parts[1])
#                     y = float(parts[2])
#                     brain.leg.moveTo(x, y)
#                     brain.leg.wait_x()
#                     brain.leg.wait_y()
#                     print(f"移动到 ({x}, {y})")
#                 except Exception as e:
#                     print(f"移动失败: {e}")
#             else:
#                 print("格式错误，请输入 'm x y'")
#         elif cmd.startswith('zh '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zh = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
#                     print(f"手爪Z设置为 {current_zh}")
#                 except Exception as e:
#                     print(f"设置Z高度失败: {e}")
#             else:
#                 print("格式错误，请输入 'zh 数值'")
#         elif cmd.startswith('zm '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zm = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
#                     print(f"注射泵Z设置为 {current_zm}")
#                 except Exception as e:
#                     print(f"设置Z失败: {e}")
#             else:
#                 print("格式错误，请输入 'zm 数值'")
#         elif cmd.startswith('s '):
#             parts = cmd.split()
#             if len(parts) != 2:
#                 print("格式错误，请输入 's 变量名'")
#                 continue
#             name = parts[1]
#             valid_names = ['coordinate_glass_first', 'coordinate_glass_fifth',
#                            'coordinate_glass_21st', 'coordinate_glass_25th']
#             if name not in valid_names:
#                 print(f"无效名称，请使用: {valid_names}")
#                 continue
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             setattr(brain, name, coordinate(x, y, current_zh, current_zm))
#             print(f"已保存 {name} = ({x:.2f}, {y:.2f}, {current_zh:.2f}, {current_zm:.2f})")
#         else:
#             print("未知命令，请参考提示输入")
#
#     brain.close()
#     print("标定结束，请将以下坐标复制到 config() 中：")
#     # 确保这些属性存在，否则打印会报错，添加默认值保护
#     for attr in ['coordinate_glass_first', 'coordinate_glass_fifth',
#                  'coordinate_glass_21st', 'coordinate_glass_25th']:
#         val = getattr(brain, attr, None)
#         if val is None:
#             print(f"{attr} 未被标定，值为 None")
#         else:
#             print(f"{attr} = ({val.x:.2f}, {val.y:.2f}, {val.zh:.2f}, {val.zm:.2f})")

# if __name__ == '__main__':
#     try:
#         print("===== 启动主程序 =====")
#         brain = masterController()
#         brain.init()  # 执行 X、Y 轴回零
#
#         print(f"当前偏移量 offset_x = {brain.leg.offset_x:.2f}")
#         print(f"当前位置 X = {brain.leg.getCurrentPos_x():.2f}")
#         print(f"当前位置 Y = {brain.leg.getCurrentPos_y():.2f}")
#
#         if abs(brain.leg.offset_x) > 0.1:
#             print("回零成功，现在测试 moveTo(0,0)...")
#             brain.moveTo(brain.coordinate_origin)  # 使用 coordinate 对象
#             print("moveTo(0,0) 完成")
#         else:
#             print("警告：偏移量为0，回零可能失败")
#
#         brain.close()
#         print("程序正常结束")
#     except Exception as e:
#         print(f"发生错误: {e}")
#         import traceback
#
#         traceback.print_exc()
#         brain.close()

#检测传感器状态
# if __name__ == '__main__':
#     try:
#         print("===== 光电传感器测试 =====")
#         brain = masterController()
#         # 只初始化硬件，不执行回零
#         brain.hand.init()
#         brain.mouth.init()
#         brain.leg.init()
#         brain.leg.set()
#         brain.coordinate_cur = coordinate(0, 0, 0, 0)
#         brain.moveTo_upAndDown(0, 0)
#         brain.relax()
#
#         print("开始读取传感器状态，每0.5秒更新一次。")
#         print("请用手或物体遮挡X轴和Y轴的光电传感器，观察状态变化。")
#         print("按 Ctrl+C 退出。\n")
#
#         import time
#
#         try:
#             while True:
#                 x_val = brain.positionSensor.detection_x()
#                 y_val = brain.positionSensor.detection_y()
#                 print(f"X传感器: {x_val}, Y传感器: {y_val}")
#                 time.sleep(0.5)
#         except KeyboardInterrupt:
#             print("\n测试结束")
#
#         brain.close()
#     except Exception as e:
#         print(f"发生错误: {e}")
#         import traceback
#
#         traceback.print_exc()
#         brain.close()

# if __name__ == '__main__':
#     try:
#         print("===== 滑轨调试模式 (X/Y轴) =====")
#         brain = masterController()
#         brain.hand.init()
#         brain.mouth.init()
#         brain.leg.init()
#         brain.leg.set()
#         brain.coordinate_cur = coordinate(0, 0, 0, 0)
#         brain.moveTo_upAndDown(0, 0)
#         brain.relax()
#
#         print("命令说明：")
#         print("  mx <位置>       -> 移动X轴到指定位置（应用偏移）")
#         print("  my <位置>       -> 移动Y轴到指定位置（应用偏移）")
#         print("  rx <位置>       -> 直接移动X轴（不应用偏移）")
#         print("  ry <位置>       -> 直接移动Y轴（不应用偏移）")
#         print("  sx              -> 显示X传感器状态")
#         print("  sy              -> 显示Y传感器状态")
#         print("  p               -> 显示当前位置和偏移量")
#         print("  homex           -> 执行X轴回零")
#         print("  homey           -> 执行Y轴回零")
#         print("  resetx          -> 将X偏移量置零")
#         print("  resety          -> 将Y偏移量置零")
#         print("  setx <值>       -> 手动设置X偏移量")
#         print("  sety <值>       -> 手动设置Y偏移量")
#         print("  q               -> 退出")
#         print()
#
#         import time
#
#         while True:
#             try:
#                 cmd = input("> ").strip()
#                 if not cmd:
#                     continue
#
#                 if cmd == 'q':
#                     break
#
#                 elif cmd == 'sx':
#                     val = brain.positionSensor.detection_x()
#                     print(f"X传感器: {'触发' if val else '未触发'}")
#                 elif cmd == 'sy':
#                     val = brain.positionSensor.detection_y()
#                     print(f"Y传感器: {'触发' if val else '未触发'}")
#
#                 elif cmd == 'p':
#                     print(f"X: 位置={brain.leg.getCurrentPos_x():.2f}, offset_x={brain.leg.offset_x:.2f}")
#                     print(f"Y: 位置={brain.leg.getCurrentPos_y():.2f}, offset_y={brain.leg.offset_y:.2f}")
#
#                 elif cmd == 'homex':
#                     brain._homing_x()
#                     print("X轴回零完成")
#                 elif cmd == 'homey':
#                     brain._homing_y()
#                     print("Y轴回零完成")
#
#                 elif cmd == 'resetx':
#                     brain.leg.offset_x = 0
#                     brain.leg.save_offset()
#                     print("X偏移量已重置为0")
#                 elif cmd == 'resety':
#                     brain.leg.offset_y = 0
#                     brain.leg.save_offset()
#                     print("Y偏移量已重置为0")
#
#                 elif cmd.startswith('setx '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             v = float(parts[1])
#                             brain.leg.offset_x = v
#                             brain.leg.save_offset()
#                             print(f"X偏移量已设置为 {v:.2f}")
#                         except:
#                             print("请输入有效数值")
#                     else:
#                         print("格式错误，请输入 'setx 数值'")
#                 elif cmd.startswith('sety '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             v = float(parts[1])
#                             brain.leg.offset_y = v
#                             brain.leg.save_offset()
#                             print(f"Y偏移量已设置为 {v:.2f}")
#                         except:
#                             print("请输入有效数值")
#                     else:
#                         print("格式错误，请输入 'sety 数值'")
#
#                 elif cmd.startswith('mx '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             target = float(parts[1])
#                             print(f"正在移动X到 {target:.2f} ...")
#                             brain.leg.moveTo_x(target, ignore_limit=True)
#                             brain.leg.wait_x()
#                             print("移动完成")
#                         except Exception as e:
#                             print(f"移动失败: {e}")
#                     else:
#                         print("格式错误，请输入 'mx 数值'")
#                 elif cmd.startswith('my '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             target = float(parts[1])
#                             print(f"正在移动Y到 {target:.2f} ...")
#                             brain.leg.moveTo_y(target, ignore_limit=True)
#                             brain.leg.wait_y()
#                             print("移动完成")
#                         except Exception as e:
#                             print(f"移动失败: {e}")
#                     else:
#                         print("格式错误，请输入 'my 数值'")
#
#                 elif cmd.startswith('rx '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             target = float(parts[1])
#                             old = brain.leg.offset_x
#                             brain.leg.offset_x = 0
#                             brain.leg.moveTo_x(target, ignore_limit=True)
#                             brain.leg.wait_x()
#                             brain.leg.offset_x = old
#                             print("移动完成")
#                         except Exception as e:
#                             print(f"移动失败: {e}")
#                     else:
#                         print("格式错误，请输入 'rx 数值'")
#                 elif cmd.startswith('ry '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             target = float(parts[1])
#                             old = brain.leg.offset_y
#                             brain.leg.offset_y = 0
#                             brain.leg.moveTo_y(target, ignore_limit=True)
#                             brain.leg.wait_y()
#                             brain.leg.offset_y = old
#                             print("移动完成")
#                         except Exception as e:
#                             print(f"移动失败: {e}")
#                     else:
#                         print("格式错误，请输入 'ry 数值'")
#
#                 else:
#                     print("未知命令")
#             except KeyboardInterrupt:
#                 print("\n用户中断")
#                 break
#
#         brain.close()
#         print("调试结束")
#     except Exception as e:
#         print(f"发生错误: {e}")
#         import traceback
#
#         traceback.print_exc()
#         brain.close()

# if __name__ == '__main__':
#     # ---------- 1. 初始化 ----------
#     brain = masterController()
#     brain.init()
#     brain.moveTo(brain.coordinate_origin)  # 初始化 coordinate_cur
#
#     # ---------- 2. 定义可保存的其他坐标变量名 ----------
#     # 玻璃位置使用 sg 命令单独保存，不在此列表
#     valid_names = [
#         'coordinate_bottle_one_hand', 'coordinate_bottle_two_hand', 'coordinate_bottle_three_hand',
#         'coordinate_bottle_one_mouth', 'coordinate_bottle_two_mouth', 'coordinate_bottle_three_mouth'
#     ]
#
#     # 当前Z高度（用户通过 zh/zm 命令设置）
#     current_zh = 0.0
#     current_zm = 0.0
#
#     # ---------- 3. 显示帮助信息 ----------
#     print("===== 标定玻璃平台（4×6，共24片）=====")
#     print("命令说明：")
#     print("  p            -> 打印当前位置 (X, Y, ZH, ZM)")
#     print("  m x y        -> 移动滑轨到 (x, y) 百分比位置")
#     print("  zh 值        -> 设置手爪Z高度 (例如 zh 60)")
#     print("  zm 值        -> 设置注射泵Z高度 (例如 zm 20)")
#     print("  pick         -> 机械手夹紧（测试）")
#     print("  place        -> 机械手松开（测试）")
#     print("  sg 编号      -> 保存当前坐标到对应编号的玻璃 (编号 1~24)")
#     print("  s 名称       -> 保存当前坐标到其他变量 (如 coordinate_bottle_one_hand)")
#     # ============ 新增拧瓶盖命令说明 ============
#     print("  open1/close1 -> 打开/关闭1号瓶（使用已保存的坐标）")
#     print("  open2/close2 -> 打开/关闭2号瓶")
#     print("  open3/close3 -> 打开/关闭3号瓶")
#     # ========================================
#     print("  q            -> 退出并显示所有已标定的坐标")
#     print()
#
#     # ---------- 4. 主循环 ----------
#     while True:
#         try:
#             cmd = input("> ").strip()
#         except EOFError:
#             break
#         if not cmd:
#             continue
#
#         # ---- 退出 ----
#         if cmd == 'q':
#             break
#
#         # ---- 打印当前位置 ----
#         elif cmd == 'p':
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             print(f"当前位置: X={x:.2f}, Y={y:.2f}, ZH={current_zh:.2f}, ZM={current_zm:.2f}")
#
#         # ---- 夹紧/释放测试 ----
#         elif cmd == 'pick':
#             print("夹持测试...")
#             brain.clamp_with_detection()
#             print("夹持完成")
#         elif cmd == 'place':
#             print("释放测试...")
#             brain.relax()
#             print("释放完成")
#
#         # ============ 新增拧瓶盖命令 ============
#         elif cmd == 'open1':
#             print("打开1号瓶...")
#             brain.openBottleOne()
#             print("1号瓶已打开")
#         elif cmd == 'close1':
#             print("关闭1号瓶...")
#             brain.closeBottleOne()
#             print("1号瓶已关闭")
#         elif cmd == 'open2':
#             print("打开2号瓶...")
#             brain.openBottleTwo()
#             print("2号瓶已打开")
#         elif cmd == 'close2':
#             print("关闭2号瓶...")
#             brain.closeBottleTwo()
#             print("2号瓶已关闭")
#         elif cmd == 'open3':
#             print("打开3号瓶...")
#             brain.openBottleThree()
#             print("3号瓶已打开")
#         elif cmd == 'close3':
#             print("关闭3号瓶...")
#             brain.closeBottleThree()
#             print("3号瓶已关闭")
#         # ======================================
#
#         # ---- 移动滑轨 ----
#         elif cmd.startswith('m '):
#             parts = cmd.split()
#             if len(parts) == 3:
#                 try:
#                     x = float(parts[1])
#                     y = float(parts[2])
#                     brain.leg.moveTo(x, y)
#                     brain.leg.wait_x()
#                     brain.leg.wait_y()
#                     print(f"移动到 ({x}, {y})")
#                 except Exception as e:
#                     print(f"移动失败: {e}")
#             else:
#                 print("格式错误，请输入 'm x y'")
#
#         # ---- 设置手爪Z高度 ----
#         elif cmd.startswith('zh '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zh = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
#                     print(f"手爪Z设置为 {current_zh}")
#                 except Exception as e:
#                     print(f"设置Z高度失败: {e}")
#             else:
#                 print("格式错误，请输入 'zh 数值'")
#
#         # ---- 设置注射泵Z高度 ----
#         elif cmd.startswith('zm '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zm = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
#                     print(f"注射泵Z设置为 {current_zm}")
#                 except Exception as e:
#                     print(f"设置Z失败: {e}")
#             else:
#                 print("格式错误，请输入 'zm 数值'")
#
#         # ---- 保存玻璃位置 ----
#         elif cmd.startswith('sg '):
#             parts = cmd.split()
#             if len(parts) != 2:
#                 print("格式错误，请输入 'sg 编号'")
#                 continue
#             try:
#                 idx = int(parts[1]) - 1   # 用户输入 1~24，转为列表索引 0~23
#                 if idx < 0 or idx >= 24:
#                     print("编号必须在 1~24 之间")
#                     continue
#             except ValueError:
#                 print("请输入有效数字")
#                 continue
#
#             # 读取当前位置
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             # 保存到 glass_coordinates 列表
#             brain.glass_coordinates[idx] = coordinate(x, y, current_zh, current_zm)
#             print(f"已保存第 {idx+1} 片玻璃坐标: X={x:.2f}, Y={y:.2f}, ZH={current_zh:.2f}, ZM={current_zm:.2f}")
#
#         # ---- 保存其他坐标（瓶盖等） ----
#         elif cmd.startswith('s '):
#             parts = cmd.split()
#             if len(parts) != 2:
#                 print("格式错误，请输入 's 变量名'")
#                 continue
#             name = parts[1]
#             if name not in valid_names:
#                 print(f"无效名称，可用名称：{valid_names}")
#                 continue
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             setattr(brain, name, coordinate(x, y, current_zh, current_zm))
#             print(f"已保存 {name} = ({x:.2f}, {y:.2f}, {current_zh:.2f}, {current_zm:.2f})")
#
#         # ---- 未知命令 ----
#         else:
#             print("未知命令，请参考提示输入")
#
#     # ---------- 5. 退出前打印所有标定结果 ----------
#     print("\n===== 标定结果 =====")
#
#     # 打印玻璃坐标
#     print("\n--- 玻璃位置（24片） ---")
#     for i, coord in enumerate(brain.glass_coordinates):
#         if coord is not None:
#             print(f"第 {i+1:2d} 片: X={coord.x:8.2f}, Y={coord.y:8.2f}, ZH={coord.zh:6.2f}, ZM={coord.zm:6.2f}")
#         else:
#             print(f"第 {i+1:2d} 片: 未标定")
#
#     # 打印其他坐标
#     print("\n--- 其他坐标 ---")
#     for name in valid_names:
#         val = getattr(brain, name, None)
#         if val is not None:
#             print(f"{name}: X={val.x:.2f}, Y={val.y:.2f}, ZH={val.zh:.2f}, ZM={val.zm:.2f}")
#         else:
#             print(f"{name}: 未标定")
#
#     print("\n标定结束，请将玻璃坐标复制到 config() 的 glass_coordinates 列表中。")
#     brain.close()

def verify_coordinates():
    """
    专门用于验证玻璃坐标的交互式工具
    """
    print("===== 玻璃坐标验证工具 =====")
    brain = masterController()
    brain.init()
    brain.moveTo(brain.coordinate_origin)

    # 当前手爪/注射泵高度（用于微调）
    current_zh = 0.0
    current_zm = 0.0

    # 记录已验证的玻璃编号
    verified_list = []

    print("\n命令说明：")
    print("  g 编号      -> 移动到指定编号的玻璃（1~24），并显示坐标")
    print("  p           -> 打印当前位置")
    print("  m x y       -> 移动滑轨到 (x, y) 百分比位置")
    print("  zh 值       -> 设置手爪Z高度 (例如 zh 60)")
    print("  zm 值       -> 设置注射泵Z高度 (例如 zm 20)")
    print("  pick        -> 夹紧玻璃（测试）")
    print("  place       -> 释放玻璃（测试）")
    print("  q           -> 退出并显示已验证的编号")
    print()

    while True:
        try:
            cmd = input("> ").strip()
        except EOFError:
            break
        if not cmd:
            continue

        # ---- 退出 ----
        if cmd == 'q':
            break

        # ---- 移动到指定玻璃 ----
        elif cmd.startswith('g '):
            parts = cmd.split()
            if len(parts) != 2:
                print("格式错误，请输入 'g 编号'")
                continue
            try:
                num = int(parts[1])
                if num < 1 or num > 24:
                    print("编号必须在 1~24 之间")
                    continue
                coord = brain.glass_coordinates[num - 1]
                if coord is None:
                    print(f"警告：第 {num} 片玻璃未标定，坐标为 (0,0,0)")
                    # 可以跳过一个未标定的，但为了演示，我们仍尝试移动
                    # 但最好提示未标定
                    continue
                # 移动到存储的坐标（包含X,Y,ZH,ZM）
                brain.moveTo(coord)
                print(f"已移动到第 {num} 片玻璃")
                print(f"  计算坐标: X={coord.x:.2f}, Y={coord.y:.2f}, ZH={coord.zh:.2f}, ZM={coord.zm:.2f}")
                # 更新当前Z变量，以便后续微调显示
                current_zh = coord.zh
                current_zm = coord.zm
                if num not in verified_list:
                    verified_list.append(num)
            except ValueError:
                print("请输入有效数字")

        # ---- 打印当前位置 ----
        elif cmd == 'p':
            x = brain.leg.getCurrentPos_x()
            y = brain.leg.getCurrentPos_y()
            print(f"当前位置: X={x:.2f}, Y={y:.2f}, ZH={current_zh:.2f}, ZM={current_zm:.2f}")

        # ---- 夹紧/释放 ----
        elif cmd == 'pick':
            print("夹持测试...")
            brain.clamp_with_detection()
            print("夹持完成")
        elif cmd == 'place':
            print("释放测试...")
            brain.relax()
            print("释放完成")

        # ---- 移动滑轨（手动微调） ----
        elif cmd.startswith('m '):
            parts = cmd.split()
            if len(parts) == 3:
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    # 先抬升Z轴到安全高度，再移动XY
                    brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
                    brain.leg.moveTo(x, y)
                    brain.leg.wait_x()
                    brain.leg.wait_y()
                    print(f"移动到 ({x}, {y})")
                except Exception as e:
                    print(f"移动失败: {e}")
            else:
                print("格式错误，请输入 'm x y'")

        # ---- 设置手爪Z高度 ----
        elif cmd.startswith('zh '):
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    current_zh = float(parts[1])
                    brain.moveTo_upAndDown(current_zh, current_zm)
                    print(f"手爪Z设置为 {current_zh}")
                except Exception as e:
                    print(f"设置Z高度失败: {e}")
            else:
                print("格式错误，请输入 'zh 数值'")

        # ---- 设置注射泵Z高度 ----
        elif cmd.startswith('zm '):
            parts = cmd.split()
            if len(parts) == 2:
                try:
                    current_zm = float(parts[1])
                    brain.moveTo_upAndDown(current_zh, current_zm)
                    print(f"注射泵Z设置为 {current_zm}")
                except Exception as e:
                    print(f"设置Z失败: {e}")
            else:
                print("格式错误，请输入 'zm 数值'")

        # ---- 未知命令 ----
        else:
            print("未知命令，请参考提示输入")

    # ---- 退出时打印已验证的玻璃编号 ----
    print("\n===== 已验证的玻璃编号 =====")
    if verified_list:
        print(f"共 {len(verified_list)} 片：{sorted(verified_list)}")
    else:
        print("未验证任何玻璃")
    print("验证结束")

    brain.close()


# if __name__ == '__main__':
#     verify_coordinates()

#测试手爪拧瓶盖
# if __name__ == '__main__':
#     try:
#         brain = masterController()
#         brain.init()  # 初始化：回零、抬升安全高度等
#
#         print("\n========== 手动控制模式 ==========")
#         print("输入 help 查看所有命令")
#         print("提示：移动滑轨前会自动将手爪和移液器抬到安全高度")
#         print("==================================\n")
#
#         while True:
#             cmd = input(">>> ").strip().split()
#             if not cmd:
#                 continue
#             op = cmd[0].lower()
#
#             if op == 'help':
#                 print("""
# 命令列表：
#   goto X Y           移动滑轨到坐标 (X, Y)，移动前自动抬升Z轴到安全高度
#   zh Z               手爪Z轴移动到 Z（例：zh 80）
#   zm Z               移液器Z轴移动到 Z（例：zm 18）
#   clamp              夹紧手爪（夹到预设位置）
#   relax              松开手爪（松开到较松位置）
#   spiral DEG         手爪旋转 DEG 度（正数拧紧，负数拧松，例：spiral -720）
#   open N             自动打开第 N 个瓶子（N=1,2,3），包含移动、夹紧、旋转
#   close N            自动关闭第 N 个瓶子（N=1,2,3）
#   status             显示当前滑轨位置和Z轴高度
#   quit               退出程序
# """)
#
#             elif op == 'goto':
#                 if len(cmd) < 3:
#                     print("用法：goto X Y")
#                     continue
#                 x, y = float(cmd[1]), float(cmd[2])
#                 # 先抬升到安全高度
#                 brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
#                 # 移动滑轨
#                 brain.move_leg_to(x, y)
#                 print(f"滑轨已移动到 X={x:.2f}, Y={y:.2f}")
#
#             elif op == 'zh':
#                 if len(cmd) < 2:
#                     print("用法：zh Z")
#                     continue
#                 z = float(cmd[1])
#                 brain.moveTo_upAndDown(z, brain.coordinate_cur.zm)
#                 print(f"手爪Z已设置为 {z}")
#
#             elif op == 'zm':
#                 if len(cmd) < 2:
#                     print("用法：zm Z")
#                     continue
#                 z = float(cmd[1])
#                 brain.moveTo_upAndDown(brain.coordinate_cur.zh, z)
#                 print(f"移液器Z已设置为 {z}")
#
#             elif op == 'clamp':
#                 brain.clamp()
#                 print("手爪已夹紧（夹到预设位置）")
#
#             elif op == 'relax':
#                 brain.relax()
#                 print("手爪已松开")
#
#             elif op == 'spiral':
#                 if len(cmd) < 2:
#                     print("用法：spiral DEG")
#                     continue
#                 deg = int(cmd[1])
#                 brain.hand.spiral(deg)
#                 print(f"手爪旋转 {deg} 度")
#
#             elif op == 'open':
#                 if len(cmd) < 2:
#                     print("用法：open N（N=1,2,3）")
#                     continue
#                 num = int(cmd[1])
#                 if num == 1:
#                     brain.openBottleOne()
#                 elif num == 2:
#                     brain.openBottleTwo()
#                 elif num == 3:
#                     brain.openBottleThree()
#                 else:
#                     print("瓶子编号只能是 1、2、3")
#                     continue
#                 print(f"已执行打开 {num} 号瓶")
#
#             elif op == 'close':
#                 if len(cmd) < 2:
#                     print("用法：close N（N=1,2,3）")
#                     continue
#                 num = int(cmd[1])
#                 if num == 1:
#                     brain.closeBottleOne()
#                 elif num == 2:
#                     brain.closeBottleTwo()
#                 elif num == 3:
#                     brain.closeBottleThree()
#                 else:
#                     print("瓶子编号只能是 1、2、3")
#                     continue
#                 print(f"已执行关闭 {num} 号瓶")
#
#             elif op == 'status':
#                 x = brain.leg.getCurrentPos_x()
#                 y = brain.leg.getCurrentPos_y()
#                 zh = brain.coordinate_cur.zh if brain.coordinate_cur else 0
#                 zm = brain.coordinate_cur.zm if brain.coordinate_cur else 0
#                 print(f"当前状态：滑轨 X={x:.2f}, Y={y:.2f}, 手爪Z={zh}, 移液器Z={zm}")
#
#             elif op == 'quit':
#                 break
#
#             else:
#                 print("未知命令，输入 help 查看帮助")
#
#     except Exception as e:
#         print(f"程序异常：{e}")
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
#         except:
#             pass
#         raise e
#     finally:
#         # 退出前回到原点并关闭设备
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
#             print("设备已关闭，程序结束。")
#         except:
#             pass

#测试移液头
# if __name__ == '__main__':
#     try:
#         brain = masterController()
#         brain.init()  # 执行初始化（回零、抬升等）
#
#         # 先抬升到最高安全位置，确保安全
#         brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
#
#         print("\n========== 吸头取放测试程序 ==========")
#         print(f"吸头总数：{len(brain.lips_coordinates)} 个（编号 1~{len(brain.lips_coordinates)}）")
#         print("命令说明：")
#         print("  输入数字编号（如 1） → 滑轨移动到该吸头位置，Z轴抬升到安全高度")
#         print("  输入 'pick'        → 执行取吸头（下压安装）")
#         print("  输入 'drop'        → 执行放回吸头（下压、弹出、抬升）")
#         print("  输入 'quit'        → 退出程序")
#         print("提示：取头前请确保移液器上没有吸头；放回前请确保已取了吸头。")
#         print("=====================================\n")
#
#         current_num = None  # 记录当前选中的吸头编号
#
#         while True:
#             cmd = input("请输入命令: ").strip()
#
#             if cmd == 'quit':
#                 break
#
#             elif cmd == 'pick':
#                 if current_num is None:
#                     print("错误：请先输入一个吸头编号！")
#                     continue
#                 print(f"正在取吸头 {current_num} ...")
#                 brain.pickLip(current_num)  # 该函数会移动到位并下压安装
#                 print("取吸头完成！请检查吸头是否安装牢固。")
#
#             elif cmd == 'drop':
#                 if current_num is None:
#                     print("错误：请先输入一个吸头编号！")
#                     continue
#                 print(f"正在放回吸头 {current_num} ...")
#                 brain.relinquishLip(current_num)  # 该函数会下压、弹出、然后抬升
#                 print("放回吸头完成！移液器已抬升至安全高度。")
#
#             else:
#                 # 尝试解析为数字编号
#                 try:
#                     num = int(cmd)
#                     if num < 1 or num > len(brain.lips_coordinates):
#                         print(f"编号超出范围（1~{len(brain.lips_coordinates)}），请重新输入")
#                         continue
#                     current_num = num
#                     # 获取吸头坐标
#                     co = brain.getLipsCoordinate(num)
#                     if co is None:
#                         continue
#                     # 移动到该位置，但将Z轴（zh和zm）设为安全高度，避免压到吸头
#                     safe_zh = Z_SAFE_HAND      # 手爪安全高度（1.0）
#                     safe_zm = Z_SAFE_MOUTH     # 移液器安全高度（0.0）
#                     brain.moveTo(coordinate(co.x, co.y, safe_zh, safe_zm))
#                     print(f"已移动到吸头 {num} 的上方（XY已对准，Z轴在安全高度）。")
#                     print("请观察位置是否准确，然后输入 'pick' 取头 或 'drop' 放回头。")
#                 except ValueError:
#                     print("无效命令，请输入数字编号、'pick'、'drop' 或 'quit'")
#
#     except Exception as e:
#         print(f"程序异常：{e}")
#         # 发生异常时，尝试回到原点并关闭设备
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
#         except:
#             pass
#         raise e
#     finally:
#         # 正常退出时也执行清理
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
#             print("设备已关闭，测试结束。")
#         except:
#             pass

# import hand
# import time
#
#
# def explore_z_limits():
#     print("===== 探索Z轴物理限位 =====")
#     print("命令：")
#     print("  +步长   -> 向上移动指定步长（如 +5）")
#     print("  -步长   -> 向下移动指定步长（如 -5）")
#     print("  pos     -> 显示当前位置（虚拟值）")
#     print("  set 值  -> 直接设置位置（可用于跳转）")
#     print("  q       -> 退出并记录限位")
#     print()
#
#     # 创建控制器，超时设为60秒（避免限位时超时）
#     h = hand.controller("COM7", timeout=60)
#
#     # 当前虚拟位置（初始为0，但实际物理位置未知）
#     current_pos = 0.0
#
#     # 记录限位
#     upper_limit = None  # 上限位置
#     lower_limit = None  # 下限位置
#
#     while True:
#         try:
#             cmd = input("> ").strip()
#             if cmd.lower() == 'q':
#                 break
#             elif cmd == 'pos':
#                 print(f"当前位置: {current_pos:.1f}%")
#             elif cmd.startswith('set '):
#                 parts = cmd.split()
#                 if len(parts) == 2:
#                     new_pos = float(parts[1])
#                     current_pos = new_pos
#                     print(f"跳转到 {current_pos:.1f}%...")
#                     h.moveTo(current_pos)
#                     time.sleep(2)
#                     print("移动完成")
#                 else:
#                     print("格式错误，请输入 'set 数值'")
#             elif cmd.startswith('+'):
#                 step = float(cmd[1:]) if len(cmd) > 1 else 1.0
#                 current_pos += step
#                 print(f"向上移动 {step}，目标 {current_pos:.1f}%...")
#                 try:
#                     h.moveTo(current_pos)
#                     time.sleep(2)
#                     print("移动成功")
#                 except Exception as e:
#                     print(f"移动失败（可能到达限位）: {e}")
#                     # 记录上限
#                     upper_limit = current_pos - step
#                     print(f"推测上限在 {upper_limit:.1f} 附近")
#             elif cmd.startswith('-'):
#                 step = float(cmd[1:]) if len(cmd) > 1 else 1.0
#                 current_pos -= step
#                 print(f"向下移动 {step}，目标 {current_pos:.1f}%...")
#                 try:
#                     h.moveTo(current_pos)
#                     time.sleep(2)
#                     print("移动成功")
#                 except Exception as e:
#                     print(f"移动失败（可能到达限位）: {e}")
#                     lower_limit = current_pos + step
#                     print(f"推测下限在 {lower_limit:.1f} 附近")
#             else:
#                 print("未知命令")
#         except KeyboardInterrupt:
#             break
#
#     h.close()
#     print("\n===== 探索结果 =====")
#     if upper_limit is not None:
#         print(f"上限（撞限位位置）: {upper_limit:.1f}")
#     else:
#         print("未探索上限")
#     if lower_limit is not None:
#         print(f"下限（撞限位位置）: {lower_limit:.1f}")
#     else:
#         print("未探索下限")
#     print("请将这些值作为软限位使用。")


# if __name__ == '__main__':
#     explore_z_limits()

#测试所有功能主函数
if __name__ == '__main__':
    try:
        brain = masterController()
        brain.init()  # 初始化：回零、抬升安全高度

        print("\n========== 手动测试主函数 ==========")
        print("提示：移动滑轨前会自动将手爪和移液器抬到安全高度")
        print("操作真空泵盖子和电磁阀前，请确保机械臂已离开真空泵区域！")
        print("输入 help 查看所有命令")
        print("=====================================\n")

        while True:
            cmd = input(">>> ").strip().split()
            if not cmd:
                continue
            op = cmd[0].lower()

            if op == 'help':
                print("""
命令列表：
  m X Y              移动滑轨到坐标 (X, Y)（自动抬升Z轴到安全高度）
  zh Z               设置手爪Z轴高度（例：zh 80）
  zm Z               设置移液器Z轴高度（例：zm 18）
  c                  夹紧手爪
  r                  松开手爪
  s DEG              手爪旋转 DEG 度（整数，正数拧紧，负数拧松）
  su VOL             吸取 VOL 微升液体（整数，例：su 30）
  sp VOL             吐出 VOL 微升液体（整数，例：sp 30，若 VOL=0 表示全部吐出）
  se                 弹出吸头（自动脱离移液器）
  x SPEED ACC SPIN   启动旋涂仪（speed模式）
                     SPEED: rpm，ACC: 加速度(rpm/s)，SPIN: 旋涂时间(s)
                     例：x 5000 5000 30
  zk [STEP NUM]      执行 zksz 完整工艺流程（可选指定退火平台位置）
                     例：zk           （默认 step=1, num=1）
                     例：zk 1 2       （step=1, num=2）
  lo                 打开真空泵盖子
  lc                 关闭真空泵盖子
  vo                 打开电磁阀
  vc                 关闭电磁阀
  st                 显示当前滑轨位置和Z轴高度
  home               回零机械臂(x轴、y轴)
  q                  退出程序
""")
            if op == 'home':
                brain._homing_x()
                brain._homing_y()
                brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)  # 回零后再次确认
                print("机械臂已回零，Z轴高度设置为安全值")

            elif op == 'm':
                if len(cmd) < 3:
                    print("用法：m X Y")
                    continue
                try:
                    x, y = float(cmd[1]), float(cmd[2])
                except ValueError:
                    print("坐标必须是数字")
                    continue
                brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
                brain.move_leg_to(x, y)
                print(f"滑轨已移动到 X={x:.2f}, Y={y:.2f}")

            elif op == 'zh':
                if len(cmd) < 2:
                    print("用法：zh Z")
                    continue
                try:
                    z = float(cmd[1])
                except ValueError:
                    print("Z 必须是数字")
                    continue
                brain.moveTo_upAndDown(z, brain.coordinate_cur.zm)
                print(f"手爪Z已设置为 {z}")

            elif op == 'zm':
                if len(cmd) < 2:
                    print("用法：zm Z")
                    continue
                try:
                    z = float(cmd[1])
                except ValueError:
                    print("Z 必须是数字")
                    continue
                brain.moveTo_upAndDown(brain.coordinate_cur.zh, z)
                print(f"移液器Z已设置为 {z}")

            elif op == 'c':
                brain.clamp()
                print("手爪已夹紧")

            elif op == 'r':
                brain.relax()
                print("手爪已松开")

            elif op == 's':
                if len(cmd) < 2:
                    print("用法：s DEG")
                    continue
                try:
                    deg = int(cmd[1])
                except ValueError:
                    print("角度必须是整数，例如：s -720")
                    continue
                brain.hand.spiral(deg)
                print(f"手爪旋转 {deg} 度")

            elif op == 'su':
                if len(cmd) < 2:
                    print("用法：su VOL（整数，单位：微升）")
                    continue
                try:
                    vol = int(cmd[1])
                except ValueError:
                    print("体积必须是整数，例如：su 30")
                    continue
                brain.mouth.suck(vol)
                print(f"已吸取 {vol} 微升")

            elif op == 'sp':
                if len(cmd) < 2:
                    print("用法：sp VOL（整数，单位：微升，0 表示全部吐出）")
                    continue
                try:
                    vol = int(cmd[1])
                except ValueError:
                    print("体积必须是整数，例如：sp 30")
                    continue
                brain.mouth.spit(vol)
                print(f"已吐出 {vol} 微升")

            elif op == 'se':
                brain.mouth.secedeTip()
                print("已弹出吸头")

            elif op == 'x':
                if len(cmd) < 4:
                    print("用法：x SPEED ACC SPIN（整数/浮点）")
                    print("SPEED: rpm，ACC: 加速度(rpm/s)，SPIN: 时间(s)")
                    print("例如：x 5000 5000 30")
                    continue
                try:
                    speed = float(cmd[1])
                    accel = float(cmd[2])
                    spin_time = float(cmd[3])
                except ValueError:
                    print("参数必须是数字")
                    continue
                if accel <= 0:
                    print("加速度必须大于 0")
                    continue
                accelerating_time = speed / accel  # 秒
                spin_info = SpinInfo(
                    speed=int(round(speed)),
                    spinTime=spin_time,
                    acceleratingTime=accelerating_time,
                    deceleratingTime=accelerating_time,
                )
                brain.spin([spin_info], mode="speed")
                print(f"旋涂已启动：speed={speed} rpm, accel={accel} rpm/s, spinTime={spin_time}s (accTime={accelerating_time:.3f}s)")


            elif op == 'zk':

                print("开始执行 zksz 工艺流程...")

                brain.zksz()

                print("zksz 工艺流程执行完毕。")

            elif op == 'lo':
                brain.evacuationSpace.openLid()
                print("真空泵盖子已打开")

            elif op == 'lc':
                brain.evacuationSpace.closeLid()
                print("真空泵盖子已关闭")

            elif op == 'vo':
                brain.valve.setPowerOn()
                print("电磁阀已打开")

            elif op == 'vc':
                brain.valve.setPowerOff()
                print("电磁阀已关闭")

            elif op == 'st':
                x = brain.leg.getCurrentPos_x()
                y = brain.leg.getCurrentPos_y()
                zh = brain.coordinate_cur.zh if brain.coordinate_cur else 0
                zm = brain.coordinate_cur.zm if brain.coordinate_cur else 0
                print(f"当前状态：滑轨 X={x:.2f}, Y={y:.2f}, 手爪Z={zh}, 移液器Z={zm}")

            elif op == 'q':
                break

            else:
                print("未知命令，输入 help 查看帮助")

    except Exception as e:
        print(f"程序异常：{e}")
        try:
            brain.moveTo(brain.coordinate_origin)
            brain.close()
        except:
            pass
        raise e
    finally:
        try:
            brain.moveTo(brain.coordinate_origin)
            brain.close()
            print("设备已关闭，程序结束。")
        except:
            pass
