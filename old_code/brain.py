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

# Safe Z height to avoid the travel limit.
Z_SAFE_HAND = 1.0    # Minimum safe gripper position; values below 1 are forbidden.
Z_SAFE_MOUTH = 0.0   # Minimum safe pipette position.

class masterController:
    """Represent master controller and its associated operations."""
    def __init__(self):
        """Initialize master controller dependencies and internal state."""
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
        self.glass_coordinates = [None] * 24  # Indices 0..23 correspond to glass numbers 1..24.
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
        """Ybf 1."""
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
        """Ybf 2."""
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
            """Move the rail to a percentage position in 0..140 and wait for arrival."""
            self.leg.moveTo(x, y)
            self.leg.wait_x()
            self.leg.wait_y()

        end = time.time()
        time2_mid = end_mid - start
        time2 = end - start
        print("time2_mid", time2_mid)
        print("time2", time2)

    def YBF_3(self, params : dict,bottleNum = 1):
        """Ybf 3."""
        start = time.time()
        self.moveTo(brain.coordinate_spinCoater_wait_hand)
        mid = time.time()
        self.pickGlassFromSpinCoater()
        self.putToHeater(2, 3)
        self.relinquishLip(bottleNum)  # Return the pipette after heating.
        self.moveTo(self.coordinate_origin)
        end = time.time()
        time3 = end - start
        print("time3", time3)
        print("time3_mid", mid - start)

    def YBF_4(self, params : dict):
        """Ybf 4."""
        start = time.time()
        self.pickGlassFromHeater(2, 3)
        self.putToPlatform(1)
        self.moveTo(self.coordinate_origin)
        end = time.time()
        time4 = end - start
        print("time4", time4)

    def LBF_2(self):
        """Lbf 2."""
        start = time.time()
        self.pickGlassFromSpinCoater()
        self.putToHeater(2, 3)
        self.moveTo(brain.coordinate_origin)
        end = time.time()
        time5 = end - start
        print("time5", time5)

    def LBF_3(self, bottleNum = 1):
        """Lbf 3."""
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
        """Home X with offsets temporarily disabled to avoid affecting the sensor search."""
        print("正在执行X轴回零...")

        # 1. Save the previous offset and temporarily clear it.
        old_offset = self.leg.offset_x
        self.leg.offset_x = 0
        print(f"临时禁用X偏移量，从当前位置开始搜索")

        max_steps = 500
        step = 1.0
        sensor_triggered = False

        # 2. Read the current raw position.
        cur_pos = self.leg.getCurrentPos_x()
        raw_pos = cur_pos
        print(f"起始X位置: {cur_pos:.2f}")

        # 3. Check whether the sensor is already triggered.
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

        # 4. Move incrementally in the negative direction.
        for i in range(1, max_steps + 1):
            target = cur_pos - i * step
            print(f"  尝试移动到 X = {target:.2f}")
            try:
                self.leg.moveTo_x(target, ignore_limit=True)
                self.leg.wait_x()
            except TLE as e:
                print(f"移动到 {target:.2f} 超时，可能到达限位")
                # Check the sensor after a motion timeout.
                if self.positionSensor.detection_x():
                    raw_pos = self.leg.getCurrentPos_x()
                    print(f"X传感器触发！当前位置: {raw_pos:.2f}")
                    self.leg.offset_x = raw_pos
                    self.leg.save_offset()
                    print(f"X零点已锁定，偏移量 X = {raw_pos:.2f}")
                    sensor_triggered = True
                break

            # Check the sensor after normal motion.
            if self.positionSensor.detection_x():
                raw_pos = self.leg.getCurrentPos_x()
                print(f"X传感器触发！当前位置: {raw_pos:.2f}")
                '''self.leg.offset_x = raw_pos
                self.leg.save_offset()
                print(f"X零点已锁定，偏移量 X = {raw_pos:.2f}")'''
                sensor_triggered = True
                break

        # 5. Restore the previous offset if homing fails.
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
        """Home Y with offsets temporarily disabled to avoid affecting the sensor search."""
        print("正在执行Y轴回零...")

        # 1. Save the previous offset and temporarily clear it.
        old_offset = self.leg.offset_y
        self.leg.offset_y = 0
        print(f"临时禁用Y偏移量，从当前位置开始搜索")

        max_steps = 500
        step = 1.0
        sensor_triggered = False

        # 2. Read the current raw position.
        cur_pos = self.leg.getCurrentPos_y()
        raw_pos = cur_pos
        print(f"起始Y位置: {cur_pos:.2f}")

        # 3. Check whether the sensor is already triggered.
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

        # 4. Move incrementally in the negative direction.
        for i in range(1, max_steps + 1):
            target = cur_pos - i * step
            print(f"  尝试移动到 Y = {target:.2f}")
            try:
                self.leg.moveTo_y(target, ignore_limit=True)
                self.leg.wait_y()
            except TLE as e:
                print(f" 移动到 {target:.2f} 超时，可能到达限位")
                # Check the sensor after a motion timeout.
                if self.positionSensor.detection_y():
                    raw_pos = self.leg.getCurrentPos_y()
                    print(f"Y传感器触发！当前位置: {raw_pos:.2f}")
                    self.leg.offset_y = raw_pos
                    self.leg.save_offset()
                    print(f"Y零点已锁定，偏移量 Y = {raw_pos:.2f}")
                    sensor_triggered = True
                break

            # Check the sensor after normal motion.
            if self.positionSensor.detection_y():
                raw_pos = self.leg.getCurrentPos_y()
                print(f"Y传感器触发！当前位置: {raw_pos:.2f}")
                '''self.leg.offset_y = raw_pos
                self.leg.save_offset()
                print(f"Y零点已锁定，偏移量 Y = {raw_pos:.2f}")'''
                sensor_triggered = True
                break

        # 5. Restore the previous offset if homing fails.
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
        """Get lips coordinate."""
        if num == -1:
            num = self.lip_num
        if num < 1 or num > len(self.lips_coordinates):
            print(f"错误：吸头编号 {num} 超出范围（1~{len(self.lips_coordinates)}）")
            return None
        return self.lips_coordinates[num - 1]

    def init(self):
        """Init."""
        self.lip_num = 1
        self.last_picked_num = None  # Remember the last selected tip number.
        self.hand.init()
        self.mouth.init()
        self.leg.init()
        self.leg.set()
        self.coordinate_cur = coordinate(0, 0, 0, 0)

        # Release the gripper before raising Z.
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
        # Raise Z to the safe height first.
        """Move to."""
        self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
        self.coordinate_cur = coordinate(aim.x, aim.y, aim.zh, aim.zm)
        self.hand.moveTo(0)
        self.mouth.moveTo(0)
        self.leg.moveToDirectly(aim.x, aim.y)
        self.hand.moveTo(aim.zh)
        self.mouth.moveTo(aim.zm)

    def moveTo_upAndDown(self, zh=0, zm=0):
        # Clamp the gripper target to at least Z_SAFE_HAND (1).
        """Move to up and down."""
        if zh < Z_SAFE_HAND:
            zh = Z_SAFE_HAND
        # The pipette target is not clamped here; Z_SAFE_MOUTH is a possible limit.
        if zm < Z_SAFE_MOUTH:
            zm = Z_SAFE_MOUTH

        if self.coordinate_cur is None:
            self.coordinate_cur = coordinate(0, 0, 0, 0)
        self.coordinate_cur = coordinate(self.coordinate_cur.x, self.coordinate_cur.y, zh, zm)
        self.hand.moveTo(zh)
        self.mouth.moveTo(zm)

    def move_leg_to(self, x, y):
        """Move the rail to a percentage position in 0..140 and wait for arrival."""
        self.leg.moveTo(x, y)
        self.leg.wait_x()
        self.leg.wait_y()

    def spin(self, spinInfoList, mode = "speed"):
        """Spin."""
        if self.coordinate_cur.x == self.coordinate_spinCoater_hand.x and self.coordinate_cur.y == self.coordinate_spinCoater_hand.y:
            self.coordinate_cur.zh = 0
            self.moveTo(self.coordinate_cur)
        self.spinCoater.spin(spinInfoList, mode)

    def clamp(self, aim = 30):
        """Clamp."""
        self.hand.set_rj_clampTorque(50)
        self.hand.clamp(self.hand_aim_position)
        pos = self.hand.query_rj_position()
        if pos < aim:
            return True
        return False

    def clamp_with_detection(self):
        """Clamp with detection."""
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
        """Relax."""
        self.hand.set_rj_clampTorque(50)
        self.hand.clamp_position(36)

    def relax_thorough(self):
        """Relax thorough."""
        self.hand.set_rj_clampTorque(50)
        self.hand.clamp(0)

    def detect_hand_loose(self):
        """Detect hand loose."""
        self.clamp()
        pos = self.hand.query_rj_position()
        if pos >= self.hand_aim_position:
            self.emergence = True
            self.emergence_info = "hand does not clamp tight"
            return True
        return False

    def detect_mouth_suck(self):
        """Detect mouth suck."""
        response = self.mouth.query_adp()
        if response == 'not sucked':
            self.emergence = True
            self.emergence_info = "mouth does not suck"
            return True
        return False

    def pickLip(self, num=-1):
        """Pick tip number 1..25; -1 selects lip_num and advances the automatic counter."""
        auto = (num == -1)
        if auto:
            # Wrap the tip number to 1 after reaching the total count.
            if self.lip_num > len(self.lips_coordinates):
                self.lip_num = 1
            num = self.lip_num
            # Increment immediately after pickup for the next operation.
            self.lip_num += 1
        co = self.getLipsCoordinate(num)
        if co is None:
            return
        # Move to the tip and descend to the normal attachment depth.
        self.moveTo(co)
        # Descend 2 additional units to seat the tip firmly.
        co.zm += 2
        self.moveTo_upAndDown(0, co.zm)
        # Raise to the safe height before lateral travel.
        self.moveTo_upAndDown(0, Z_SAFE_MOUTH)
        # Remember the selected tip in automatic mode.
        if auto:
            self.last_picked_num = num

    def relinquishLip(self, num=-1):
        """Return a tip to its slot; -1 uses the previous automatic pickup number."""
        if num == -1:
            # pickLip already incremented lip_num; use the previous number.
            if hasattr(self, 'last_picked_num'):
                num = self.last_picked_num
            else:
                num = self.lip_num - 1  # Step back by one number.
        co = self.getLipsCoordinate(num)
        if co is None:
            return
        # 1. Descend 10 additional units to return the tip fully into its slot.
        co.zm -= 10
        self.moveTo(co)
        # 2. Activate the pipette tip ejection mechanism.
        self.mouth.secedeTip()
        # 3. Raise the pipette to zm=0 before lateral travel.
        self.moveTo_up_andDown(0, Z_SAFE_MOUTH)

    def suckFromBottleOne(self, vol):
        """Suck from bottle one."""
        if(self.volume_current > 1e-9):
            print("sucking with liquids!!!!")

        self.volume_current += vol
        self.moveTo(self.coordinate_bottle_one_mouth)
        self.mouth.suck(vol)
        # if self.detect_mouth_suck(): self.moveTo(self.coordinate_origin)
        if self.detect_mouth_suck(): print("mouth does not suck")

    def suckFromBottleTwo(self, vol):
        """Suck from bottle two."""
        if (self.volume_current > 1e-9):
            print("sucking with liquids!!!!")

        self.volume_current += vol
        self.moveTo(self.coordinate_bottle_two_mouth)
        self.mouth.suck(vol)

        # if self.detect_mouth_suck(): self.moveTo(self.coordinate_origin)
        if self.detect_mouth_suck(): print("mouth does not suck")

    def suckFromBottleThree(self, vol):
        """Suck from bottle three."""
        if (self.volume_current > 1e-9):
            print("sucking with liquids!!!!")

        self.volume_current += vol
        self.moveTo(self.coordinate_bottle_three_mouth)
        self.mouth.suck(vol)
        # if self.detect_mouth_suck(): self.moveTo(self.coordinate_origin)
        if self.detect_mouth_suck(): print("mouth does not suck")

    def spitToSpinCoater(self, vol = -1):
        """Spit to spin coater."""
        if vol == -1:
            vol = self.volume_current

        self.moveTo(self.coordinate_spinCoater_mouth)
        print("spit : ", vol)
        self.mouth.spit(0)
        self.volume_current = 0

    def pickGlassFromPlatform(self, num=1, flag=0):
        """Pick glass from platform."""
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
        """Put to spin coater."""
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
        """Pick glass from spin coater."""
        self.relax_thorough()
        self.moveTo(self.coordinate_spinCoater_hand)
        self.clamp_with_detection()

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def putToPlatform(self, num=1):
        """Put to platform."""
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
        # Subtract the height compensation when placing the glass.
        zh = aimCoordinate.zh - self.distance_platform_pick_and_put
        self.moveTo(coordinate(aimCoordinate.x, aimCoordinate.y, zh, 0))
        self.relax()

    def pickGlassFromHeater(self, step = 1, num = 1, flag = 0): #flag = 1 : change to vertical direction to grab glass from heater whose space is limited
        """Pick glass from heater."""
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
        """Put to heater."""
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
        """Open bottle one."""
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
        """Close bottle one."""
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return

        self.moveTo(self.coordinate_bottle_one_hand)
        self.hand.spiral(0)  # be careful !!!!!!!!!!!!!!!!!!!!!!
        self.relax_thorough()

    def openBottleTwo(self):
        """Open bottle two."""
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
        """Close bottle two."""
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return

        self.moveTo(self.coordinate_bottle_two_hand)
        self.hand.spiral(0)  # be careful !!!!!!!!!!!!!!!!!!!!!!
        self.relax_thorough()

    def openBottleThree(self):
        """Open bottle three."""
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
        """Close bottle three."""
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return

        self.moveTo(self.coordinate_bottle_three_hand)
        self.hand.spiral(0)  # be careful !!!!!!!!!!!!!!!!!!!
        self.relax_thorough()

    def prepareForGlass_onlyTheFirstPosition(self, num):
        """Prepare for glass only the first position."""
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
        """Prepare for heater."""
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
        """Put to evacuation space."""
        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()
            return
        self.moveTo(self.coordinate_evacuation_space)
        self.relax()

    def pickGlassFromEvacuationSpace(self):
        """Pick glass from evacuation space."""
        self.moveTo(self.coordinate_evacuation_space)
        self.clamp_with_detection()

        if self.detect_hand_loose():
            print('hand loose')
            self.moveTo(self.coordinate_origin)
            self.relax()

    def OneStepMethod_A(self, id, vol = 30, spinInfoList = None):
        """One step method a."""
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
        """One step method b."""
        self.pickLip(2)
        self.openBottleTwo()
        self.suckFromBottleTwo(vol)  # 30
        self.closeBottleTwo()
        self.moveTo(self.coordinate_spinCoater_wait_mouth)
        self.spitToSpinCoater(-1)
        self.moveTo_upAndDown(0,0)

    def OneStepMethod_H(self, id):
        """One step method h."""
        self.moveTo(self.coordinate_spinCoater_wait_hand)
        self.pickGlassFromSpinCoater()
        heater_id = self.Heater_All.AssignGlass(id) # Use heater_all in place of heater1.
        self.putToHeater((heater_id - 1) // 4 + 1, (heater_id - 1) % 4 + 1)
        self.spinCoater.returnToOriginOfSingleRevolution_notBlocked()
        self.relinquishLip(2)  # Return the pipette after heating.
        self.moveTo(self.coordinate_origin)

    def OneStepMethod_T(self, id):
        """One step method t."""
        print("in T")
        heater_id = self.Heater_All.RemoveGlass(id)
        self.pickGlassFromHeater((heater_id - 1) // 4 + 1, (heater_id - 1) % 4 + 1)
        self.putToPlatform(id)
        self.moveTo(self.coordinate_origin)

    def LBF(self):
        """Lbf."""
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
        time.sleep(4)  # Test the wait after spin coating.
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
        time.sleep(5)  # Test the wait after spin coating.
        self.pickGlassFromSpinCoater()
        self.putToHeater(1,1)
        self.moveTo(brain.coordinate_origin)
        #time.sleep(10)  # step 2 heating test
        self.pickGlassFromHeater(1,1)
        self.putToPlatform(1)
        self.moveTo(brain.coordinate_origin)

    def YBF(self, params : dict):
        """Ybf."""
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

        """Test spin."""
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
        """Run the legacy process with hardcoded coordinates and 1 s inter-step delays.

        Use tips (3, 4) at (98.4, 3.5, 99) and (3, 5) at (96.1, 3.5, 99); discard at pipette Z=90."""
        # Define all coordinates directly.
        # Pipette tip coordinates.
        lip1_x, lip1_y, lip1_z = 97.7, 1.8, 99  # (3,5)
        lip2_x, lip2_y, lip2_z = 95.3, 1.8, 99  # (3,6)
        lip_drop_z = 90  # Pipette Z height for discarding a tip.

        # Spin coater coordinates.
        sc_hand_x, sc_hand_y, sc_hand_z = 46.5, 65.5, 87
        sc_mouth_x, sc_mouth_y, sc_mouth_z = 56.0, 87.8, 18

        # Bottle 1 coordinates.
        b1_hand_x, b1_hand_y, b1_hand_z = 47.3, 11.0, 80
        b1_mouth_x, b1_mouth_y, b1_mouth_z = 56.7, 33.5, 45
        b1_deg = 360

        # Bottle 3 coordinates.
        b3_hand_x, b3_hand_y, b3_hand_z = 39.8, 24.9, 80
        b3_mouth_x, b3_mouth_y, b3_mouth_z = 49.2, 47.0, 45
        b3_deg = 360

        # Coordinates of the second glass.
        glass_x, glass_y, glass_z = 88.7, 19.0, 87.5

        # Annealing station coordinates.
        heater_x, heater_y, heater_z = 15, 10, 75

        # Vacuum station coordinates.
        vacuum_x, vacuum_y, vacuum_z = 0, 97, 96.5

        # Safe height.
        Z_SAFE_HAND = 1.0
        Z_SAFE_MOUTH = 0.0

        # Helper functions.
        def move_hand(x, y, z):
            """Move hand."""
            self.moveTo(coordinate(x, y, z, Z_SAFE_MOUTH))

        def move_mouth(x, y, z):
            """Move mouth."""
            self.moveTo(coordinate(x, y, Z_SAFE_HAND, z))

        def pick_glass(x, y, z):
            """Pick glass."""
            move_hand(x, y, z)
            self.clamp_with_detection()
            if self.detect_hand_loose():
                print('hand loose when picking glass')
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def put_glass(x, y, z):
            """Put glass."""
            move_hand(x, y, z)
            self.relax()
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def pick_lip(x, y, z):
            """Pick lip."""
            move_mouth(x, y, z)
            # Disabled extra descent: self.moveTo_upAndDown(Z_SAFE_HAND, z + 2).
            # self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def drop_lip(x, y):
            """Drop lip."""
            move_mouth(x, y, lip_drop_z)
            self.mouth.secedeTip()
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def open_bottle(x, y, z, deg):
            """Open bottle."""
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
            """Close bottle."""
            move_hand(x, y, z)
            self.hand.spiral(0)
            self.relax_thorough()
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            #self.hand.spiral(deg)
            time.sleep(1)

        def suck(x, y, z, vol):
            """Suck."""
            move_mouth(x, y, z)
            self.mouth.suck(vol)
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        def spit(x, y, z, vol=0):
            """Spit."""
            move_mouth(x, y, z)
            self.mouth.spit(vol)
            self.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
            time.sleep(1)

        # Start the process sequence.

        # 1. Transfer glass 2 from the tray to the spin coater.
        print("取玻璃...")
        pick_glass(glass_x, glass_y, glass_z)
        print("放到旋涂仪...")
        put_glass(sc_hand_x, sc_hand_y, sc_hand_z)

        # 2. Pick the first tip at row 3, column 4.
        print("取吸头 1...")
        pick_lip(lip1_x, lip1_y, lip1_z)

        # 3. Open bottle 1.
        print("开1号瓶...")
        open_bottle(b1_hand_x, b1_hand_y, b1_hand_z, b1_deg)

        # 4. Aspirate 100 microliters of SAM.
        print("吸 SAM...")
        suck(b1_mouth_x, b1_mouth_y, b1_mouth_z, 100)

        # 5. Close bottle 1.
        print("关1号瓶...")
        close_bottle(b1_hand_x, b1_hand_y, b1_hand_z)

        # 6. Dispense onto the spin coater.
        print("滴 SAM...")
        spit(sc_mouth_x, sc_mouth_y, sc_mouth_z)

        # 7. Spin SAM at 5000 rpm for 30 s; 5000 rpm/s gives a 1 s ramp.
        print("旋涂 SAM...")
        spin1 = [SpinInfo(speed=5000, spinTime=10, acceleratingTime=1.0, deceleratingTime=1.0)]
        self.spinCoater.spin(spin1, mode="speed")
        time.sleep(1)

        # 8. Return the tip at row 3, column 4 during spinning.
        print("放回吸头 1...")
        drop_lip(lip1_x, lip1_y)

        # 9. Wait for spinning to finish.
        print("等待 SAM 旋涂结束...")
        if self.spinCoater.spinThread.is_alive():
            self.spinCoater.spinThread.join()
        time.sleep(1)

        # 21. Open the vacuum station lid.
        print("打开真空泵盖子...")
        self.evacuationSpace.openLid()
        time.sleep(1)

        # 22. Transfer the glass from the spin coater to the vacuum station.
        print("从旋涂仪取玻璃...")
        pick_glass(sc_hand_x, sc_hand_y, sc_hand_z)
        print("放到真空泵...")
        put_glass(vacuum_x, vacuum_y, vacuum_z)

        # 23. Close the vacuum station lid.
        print("关闭真空泵盖子...")
        self.evacuationSpace.closeLid()
        time.sleep(1)

        # 24. Open the solenoid valve and close it after 20 s.
        print("打开电磁阀...")
        self.valve.setPowerOn()
        time.sleep(10)
        print("关闭电磁阀...")
        self.valve.setPowerOff()
        time.sleep(1)

        # 25. Open the vacuum station lid.
        print("打开真空泵盖子...")
        self.evacuationSpace.openLid()
        time.sleep(1)

        # 26. Transfer the glass to the annealing station.
        print("从真空泵取玻璃...")
        pick_glass(vacuum_x, vacuum_y, vacuum_z)
        print("放到退火台...")
        put_glass(heater_x, heater_y, heater_z)

        # 27. Close the vacuum station lid.
        print("关闭真空泵盖子...")
        self.evacuationSpace.closeLid()
        time.sleep(1)

        # 28. Anneal for 20 minutes in the intended recipe.
        print("退火 20 分钟...（本次为模拟实验，模拟退火10秒）")
        time.sleep(10)

        # 29. Return the glass from the annealing station to its original tray slot.
        print("从退火台取玻璃...")
        pick_glass(heater_x, heater_y, heater_z)
        print("放回原平台...")
        put_glass(glass_x, glass_y, glass_z)

        print("zksz 流程完成。")



    def close(self):
        """Close."""
        self.hand.close()
        self.mouth.close()
        self.leg.close()
        self.spinCoater.close()
        self.evacuationSpace.close()
        self.valve.close()


    #dx,dy = 8.7 24.5
    def config(self):
        # Precise gripper coordinates for glass pickup and placement.
        """Config."""
        self.coordinate_spinCoater_hand = coordinate(48.5, 64.5, 87.1, 0)
        # Additional gripper descent for placement; retain the existing value pending calibration.
        self.distance_spinCoater_pick_and_drop = 0.5
        # Gripper waiting pose uses the same X/Y and safe Z.
        self.coordinate_spinCoater_wait_hand = coordinate(48.5, 64.5, 0, 0)
        # Pipette dispensing coordinates.
        self.coordinate_spinCoater_mouth = coordinate(57.2, 90.0, 0, 18)
        # Pipette waiting pose uses the same X/Y and safe Z.
        self.coordinate_spinCoater_wait_mouth = coordinate(57.2, 90.0, 0, 0)
        self.coordinate_origin = coordinate(0, 0, 0, 0)

        self.glass_coordinates = [coordinate(0, 0, 0, 0) for _ in range(24)]  # Glass coordinates.
        self.distance_platform_pick_and_put = 0.5

        # self.coordinate_lips_first = coordinate(110, 1.5, 0, 99)#94
        # self.coordinate_lips_12th = coordinate(85.15, 1.5, 0, 99)
        # Disabled tip-coordinate candidate, pending calibration.

        self.coordinate_garbage = coordinate(30, 0, 0, 0)

        # Gripper coordinates for bottles 1..3.
        self.coordinate_bottle_one_hand = coordinate(48.2, 12.2, 80, 0)
        self.coordinate_bottle_two_hand = coordinate(40.8, 11.7, 80, 0)
        self.coordinate_bottle_three_hand = coordinate(41.6, 26.7, 80, 0)
        # Pipette coordinates for bottles 1..3.
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

        # Store the measured coordinates of 24 glasses by index.
        self.glass_coordinates = [None] * 24  # Indices 0..23 correspond to glass numbers 1..24.

        # Row 1.
        self.glass_coordinates[0] = coordinate(95.3, 19.0, 87.5, 0)  # Glass 1.
        self.glass_coordinates[1] = coordinate(88.7, 19.0, 87.5, 0)  # Glass 2.
        self.glass_coordinates[2] = coordinate(79.1, 19.0, 87.5, 0)  # Glass 3.
        self.glass_coordinates[3] = coordinate(72.6, 19.0, 87.5, 0)  # Glass 4.

        # Row 2.
        self.glass_coordinates[4] = coordinate(95.5, 32.0, 87.5, 0)  # Glass 5.
        self.glass_coordinates[5] = coordinate(88.7, 32.0, 87.5, 0)  # Glass 6.
        self.glass_coordinates[6] = coordinate(79.2, 32.0, 87.5, 0)  # Glass 7.
        self.glass_coordinates[7] = coordinate(72.5, 32.0, 87.5, 0)  # Glass 8.

        # Row 3.
        self.glass_coordinates[8] = coordinate(95.5, 45.5, 87.5, 0)  # Glass 9.
        self.glass_coordinates[9] = coordinate(88.7, 45.5, 87.5, 0)  # Glass 10.
        self.glass_coordinates[10] = coordinate(79.1, 45.5, 87.5, 0)  # Glass 11.
        self.glass_coordinates[11] = coordinate(72.6, 45.5, 87.5, 0)  # Glass 12.

        # Row 4.
        self.glass_coordinates[12] = coordinate(95.5, 59.3, 87.5, 0)  # Glass 13.
        self.glass_coordinates[13] = coordinate(88.7, 59.3, 87.5, 0)  # Glass 14.
        self.glass_coordinates[14] = coordinate(79.3, 59.3, 87.5, 0)  # Glass 15.
        self.glass_coordinates[15] = coordinate(72.6, 59.3, 87.5, 0)  # Glass 16.

        # Row 5.
        self.glass_coordinates[16] = coordinate(95.7, 73.2, 87.5, 0)  # Glass 17.
        self.glass_coordinates[17] = coordinate(88.9, 73.2, 87.5, 0)  # Glass 18.
        self.glass_coordinates[18] = coordinate(79.4, 73.2, 87.5, 0)  # Glass 19.
        self.glass_coordinates[19] = coordinate(72.7, 73.2, 87.5, 0)  # Glass 20.

        # Row 6.
        self.glass_coordinates[20] = coordinate(95.5, 86.7, 87.5, 0)  # Glass 21.
        self.glass_coordinates[21] = coordinate(88.9, 86.2, 87.5, 0)  # Glass 22.
        self.glass_coordinates[22] = coordinate(79.4, 86.2, 87.5, 0)  # Glass 23.
        self.glass_coordinates[23] = coordinate(72.9, 86.7, 87.5, 0)  # Glass 24.

        # Historical tray layout: 4 columns by 6 rows, 24 glasses.
        # self.glass_z = 88
        #
        # First-column X is common to all rows; glass 1 has x=95.3.
        # x_first_col = 95.3
        #
        # Column spacings are measured between columns 1->2, 2->3, and 3->4.
        # col_spacings = [6.6, 9.6, 6.5]
        #
        # Calculate column X coordinates by subtracting offsets from the first column.
        # x_offsets = [0.0]
        # for d in col_spacings:
        #     x_offsets.append(x_offsets[-1] + d)
        #
        # Measured X coordinates for each column.
        # col_x = [x_first_col - offset for offset in x_offsets]
        # # col_x = [95.3, 88.7, 79.1, 72.6]
        #
        # Row parameters use glass 1 at y=19.0.
        # Historical first_row_y = 19.0.
        # Historical row_spacing = 13.54.
        #
        # Y coordinates for each row.
        # row_y = [first_row_y + i * row_spacing for i in range(6)]
        # # row_y = [19.0, 32.54, 46.08, 59.62, 73.16, 86.7]
        #
        # Generate the 24 glass coordinates.
        # self.glass_coordinates = []
        # Historical loop over 6 rows.
        #     y = first_row_y + row * row_spacing
        # Historical loop over 4 columns.
        #         x = col_x[col]
        #         self.glass_coordinates.append(coordinate(x, y, self.glass_z, 0))
        #
        # Override glasses 21 and 24 with measurements at the lower diagonal corners.
        # Glass 21 uses index 20; glass 24 uses index 23.
        # Historical glass 21 coordinate: (95.4, 86.7, 88, 0).
        # Historical glass 24 coordinate: (72.9, 86.7, 88, 0).

        # Tip layout: 5 rows by 5 columns, 25 tips.
        # Reference tip at row 3, column 4: (101.3, 4.8), zm=93.
        # Column pitch dx=2.2 decreases X; row pitch dy=4.5 increases Y.
        center_x = 101.3
        center_y = 4.8
        dx = 2.2
        dy = 4.5
        zm_lip = 93

        # Generate rows 1..5 and columns 2..6.
        self.lips_coordinates = []
        for row in range(1, 6):  # Rows 1..5.
            y = center_y + (row - 3) * dy
            for col in range(2, 7):  # Columns 2..6.
                x = center_x + (4 - col) * dx  # Higher column numbers have smaller X.
                self.lips_coordinates.append(coordinate(x, y, 0, zm_lip))


    def prepareForSpinCoater(self):
        """Prepare for spin coater."""
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
        """Prepare for multi glass."""
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
        """Return to origin x."""
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
        """Return to origin y."""
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
        """Return to origin."""
        self.returnToOrigin_x()
        self.returnToOrigin_y()
        print("result in finally: ", self.leg.getCurrentPos_x(), self.leg.getCurrentPos_y())


# if __name__ == '__main__':
#     try:
#         brain = masterController()
#         brain.moveTo(brain.coordinate_spinCoater_hand)
# Historical spin settings: 300 revolutions/s, 10 s acceleration, 20 s spinning.
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
# Keep the arm at its origin before moving the vacuum lid.
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
# Keep the arm at its origin before moving the vacuum lid.
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

# Read measured glass coordinates.
# if __name__ == '__main__':
#     brain = masterController()
#     brain.init()
# Initialize coordinate_cur by moving to the origin.
#
# Historical console heading: calibrate the four tray corners.
# Historical console command help.
# Command p prints X, Y, gripper Z, and pipette Z.
# Command m x y moves the stage to percentage coordinates.
# Command zh sets the gripper Z height, for example zh 60.
# Command zm sets the pipette Z height, for example zm 20.
# Command s saves the current pose under a coordinate name.
# Command q exits.
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
# Historical console reports the current X/Y and Z heights.
#         elif cmd.startswith('m '):
#             parts = cmd.split()
#             if len(parts) == 3:
#                 try:
#                     x = float(parts[1])
#                     y = float(parts[2])
#                     brain.leg.moveTo(x, y)
#                     brain.leg.wait_x()
#                     brain.leg.wait_y()
# Historical console reports the requested X/Y move.
#                 except Exception as e:
# Historical console reports a movement failure.
#             else:
# Historical console reports invalid m x y syntax.
#         elif cmd.startswith('zh '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zh = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
# Historical console reports the new gripper Z height.
#                 except Exception as e:
# Historical console reports a gripper Z failure.
#             else:
# Historical console reports invalid zh syntax.
#         elif cmd.startswith('zm '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zm = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
# Historical console reports the new pipette Z height.
#                 except Exception as e:
# Historical console reports a pipette Z failure.
#             else:
# Historical console reports invalid zm syntax.
#         elif cmd.startswith('s '):
#             parts = cmd.split()
#             if len(parts) != 2:
# Historical console reports invalid coordinate-save syntax.
#                 continue
#             name = parts[1]
#             valid_names = ['coordinate_glass_first', 'coordinate_glass_fifth',
#                            'coordinate_glass_21st', 'coordinate_glass_25th']
#             if name not in valid_names:
# Historical console lists valid coordinate names.
#                 continue
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             setattr(brain, name, coordinate(x, y, current_zh, current_zm))
# Historical console reports the saved coordinate and its X/Y/Z values.
#         else:
# Historical console reports an unknown command.
#
#     brain.close()
# Historical console requests copying calibrated coordinates into config().
# Provide defaults for missing attributes before printing them.
#     for attr in ['coordinate_glass_first', 'coordinate_glass_fifth',
#                  'coordinate_glass_21st', 'coordinate_glass_25th']:
#         val = getattr(brain, attr, None)
#         if val is None:
# Historical console reports an uncalibrated attribute with value None.
#         else:
#             print(f"{attr} = ({val.x:.2f}, {val.y:.2f}, {val.zh:.2f}, {val.zm:.2f})")

# if __name__ == '__main__':
#     try:
# Historical console heading: start the main program.
#         brain = masterController()
# Initialize the controller by homing X and Y.
#
# Historical console reports offset_x.
# Historical console reports the current X position.
# Historical console reports the current Y position.
#
#         if abs(brain.leg.offset_x) > 0.1:
# Historical console announces an origin movement test after homing.
# Move to the origin using a coordinate object.
# Historical console reports completion of the origin move.
#         else:
# Historical console warns that a zero offset may indicate failed homing.
#
#         brain.close()
# Historical console reports normal program completion.
#     except Exception as e:
# Historical console reports an exception.
#         import traceback
#
#         traceback.print_exc()
#         brain.close()

# Inspect position sensor states.
# if __name__ == '__main__':
#     try:
# Historical console heading: photoelectric sensor test.
#         brain = masterController()
# Initialize hardware without homing.
#         brain.hand.init()
#         brain.mouth.init()
#         brain.leg.init()
#         brain.leg.set()
#         brain.coordinate_cur = coordinate(0, 0, 0, 0)
#         brain.moveTo_upAndDown(0, 0)
#         brain.relax()
#
# Historical console describes the 0.5 s sensor polling interval.
# Historical console asks the operator to cover X/Y sensors to test transitions.
# Historical console documents Ctrl+C to exit.
#
#         import time
#
#         try:
#             while True:
#                 x_val = brain.positionSensor.detection_x()
#                 y_val = brain.positionSensor.detection_y()
# Historical console reports the X/Y sensor readings.
#                 time.sleep(0.5)
#         except KeyboardInterrupt:
# Historical console reports the end of the sensor test.
#
#         brain.close()
#     except Exception as e:
# Historical console reports an exception.
#         import traceback
#
#         traceback.print_exc()
#         brain.close()

# if __name__ == '__main__':
#     try:
# Historical console heading: X/Y stage debugging.
#         brain = masterController()
#         brain.hand.init()
#         brain.mouth.init()
#         brain.leg.init()
#         brain.leg.set()
#         brain.coordinate_cur = coordinate(0, 0, 0, 0)
#         brain.moveTo_upAndDown(0, 0)
#         brain.relax()
#
# Historical console command help.
# Command mx moves X using the configured offset.
# Command my moves Y using the configured offset.
# Command rx moves X without an offset.
# Command ry moves Y without an offset.
# Command sx reports the X sensor.
# Command sy reports the Y sensor.
# Command p reports positions and offsets.
# Command homex homes X.
# Command homey homes Y.
# Command resetx clears the X offset.
# Command resety clears the Y offset.
# Command setx sets the X offset manually.
# Command sety sets the Y offset manually.
# Command q exits.
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
# Historical console reports whether the X sensor is triggered.
#                 elif cmd == 'sy':
#                     val = brain.positionSensor.detection_y()
# Historical console reports whether the Y sensor is triggered.
#
#                 elif cmd == 'p':
# Historical console reports X position and offset.
# Historical console reports Y position and offset.
#
#                 elif cmd == 'homex':
#                     brain._homing_x()
# Historical console reports completion of X homing.
#                 elif cmd == 'homey':
#                     brain._homing_y()
# Historical console reports completion of Y homing.
#
#                 elif cmd == 'resetx':
#                     brain.leg.offset_x = 0
#                     brain.leg.save_offset()
# Historical console reports that the X offset was reset.
#                 elif cmd == 'resety':
#                     brain.leg.offset_y = 0
#                     brain.leg.save_offset()
# Historical console reports that the Y offset was reset.
#
#                 elif cmd.startswith('setx '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             v = float(parts[1])
#                             brain.leg.offset_x = v
#                             brain.leg.save_offset()
# Historical console reports the assigned X offset.
#                         except:
# Historical console requests a valid numeric value.
#                     else:
# Historical console reports invalid setx syntax.
#                 elif cmd.startswith('sety '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             v = float(parts[1])
#                             brain.leg.offset_y = v
#                             brain.leg.save_offset()
# Historical console reports the assigned Y offset.
#                         except:
# Historical console requests a valid numeric value.
#                     else:
# Historical console reports invalid sety syntax.
#
#                 elif cmd.startswith('mx '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             target = float(parts[1])
# Historical console reports the target X position.
#                             brain.leg.moveTo_x(target, ignore_limit=True)
#                             brain.leg.wait_x()
# Historical console reports completion of movement.
#                         except Exception as e:
# Historical console reports a movement failure.
#                     else:
# Historical console reports invalid mx syntax.
#                 elif cmd.startswith('my '):
#                     parts = cmd.split()
#                     if len(parts) == 2:
#                         try:
#                             target = float(parts[1])
# Historical console reports the target Y position.
#                             brain.leg.moveTo_y(target, ignore_limit=True)
#                             brain.leg.wait_y()
# Historical console reports completion of movement.
#                         except Exception as e:
# Historical console reports a movement failure.
#                     else:
# Historical console reports invalid my syntax.
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
# Historical console reports completion of movement.
#                         except Exception as e:
# Historical console reports a movement failure.
#                     else:
# Historical console reports invalid rx syntax.
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
# Historical console reports completion of movement.
#                         except Exception as e:
# Historical console reports a movement failure.
#                     else:
# Historical console reports invalid ry syntax.
#
#                 else:
# Historical console reports an unknown command.
#             except KeyboardInterrupt:
# Historical console reports a user interruption.
#                 break
#
#         brain.close()
# Historical console reports the end of debugging.
#     except Exception as e:
# Historical console reports an exception.
#         import traceback
#
#         traceback.print_exc()
#         brain.close()

# if __name__ == '__main__':
# 1. Initialize the calibration session.
#     brain = masterController()
#     brain.init()
# Initialize coordinate_cur by moving to the origin.
#
# 2. Define names for other coordinates that can be saved.
# Save glass coordinates separately with sg, outside this name list.
#     valid_names = [
#         'coordinate_bottle_one_hand', 'coordinate_bottle_two_hand', 'coordinate_bottle_three_hand',
#         'coordinate_bottle_one_mouth', 'coordinate_bottle_two_mouth', 'coordinate_bottle_three_mouth'
#     ]
#
# Track the Z heights set by the zh and zm commands.
#     current_zh = 0.0
#     current_zm = 0.0
#
# 3. Display command help.
# Historical console heading: calibrate a 4-by-6 tray with 24 glasses.
# Historical console command help.
# Command p prints X, Y, gripper Z, and pipette Z.
# Command m x y moves the stage to percentage coordinates.
# Command zh sets the gripper Z height, for example zh 60.
# Command zm sets the pipette Z height, for example zm 20.
# Command pick tests gripper closure.
# Command place tests gripper release.
# Command sg saves the current pose for glass number 1..24.
# Command s saves another coordinate, such as a bottle-gripper pose.
# Document bottle cap commands.
# Commands open1/close1 use saved bottle 1 coordinates.
# Commands open2/close2 operate bottle 2.
# Commands open3/close3 operate bottle 3.
#     # ========================================
# Command q exits and prints calibrated coordinates.
#     print()
#
# 4. Run the command loop.
#     while True:
#         try:
#             cmd = input("> ").strip()
#         except EOFError:
#             break
#         if not cmd:
#             continue
#
# Handle exit.
#         if cmd == 'q':
#             break
#
# Print the current pose.
#         elif cmd == 'p':
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
# Historical console reports the current X/Y and Z heights.
#
# Test clamping and release.
#         elif cmd == 'pick':
# Historical console announces a clamping test.
#             brain.clamp_with_detection()
# Historical console reports completion of clamping.
#         elif cmd == 'place':
# Historical console announces a release test.
#             brain.relax()
# Historical console reports completion of release.
#
# Handle bottle cap commands.
#         elif cmd == 'open1':
# Historical console announces opening bottle 1.
#             brain.openBottleOne()
# Historical console reports that bottle 1 is open.
#         elif cmd == 'close1':
# Historical console announces closing bottle 1.
#             brain.closeBottleOne()
# Historical console reports that bottle 1 is closed.
#         elif cmd == 'open2':
# Historical console announces opening bottle 2.
#             brain.openBottleTwo()
# Historical console reports that bottle 2 is open.
#         elif cmd == 'close2':
# Historical console announces closing bottle 2.
#             brain.closeBottleTwo()
# Historical console reports that bottle 2 is closed.
#         elif cmd == 'open3':
# Historical console announces opening bottle 3.
#             brain.openBottleThree()
# Historical console reports that bottle 3 is open.
#         elif cmd == 'close3':
# Historical console announces closing bottle 3.
#             brain.closeBottleThree()
# Historical console reports that bottle 3 is closed.
#         # ======================================
#
# Move the stage.
#         elif cmd.startswith('m '):
#             parts = cmd.split()
#             if len(parts) == 3:
#                 try:
#                     x = float(parts[1])
#                     y = float(parts[2])
#                     brain.leg.moveTo(x, y)
#                     brain.leg.wait_x()
#                     brain.leg.wait_y()
# Historical console reports the requested X/Y move.
#                 except Exception as e:
# Historical console reports a movement failure.
#             else:
# Historical console reports invalid m x y syntax.
#
# Set the gripper Z height.
#         elif cmd.startswith('zh '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zh = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
# Historical console reports the new gripper Z height.
#                 except Exception as e:
# Historical console reports a gripper Z failure.
#             else:
# Historical console reports invalid zh syntax.
#
# Set the pipette Z height.
#         elif cmd.startswith('zm '):
#             parts = cmd.split()
#             if len(parts) == 2:
#                 try:
#                     current_zm = float(parts[1])
#                     brain.moveTo_upAndDown(current_zh, current_zm)
# Historical console reports the new pipette Z height.
#                 except Exception as e:
# Historical console reports a pipette Z failure.
#             else:
# Historical console reports invalid zm syntax.
#
# Save a glass pose.
#         elif cmd.startswith('sg '):
#             parts = cmd.split()
#             if len(parts) != 2:
# Historical console reports invalid sg syntax.
#                 continue
#             try:
# Convert operator numbers 1..24 to indices 0..23.
#                 if idx < 0 or idx >= 24:
# Historical console restricts glass numbers to 1..24.
#                     continue
#             except ValueError:
# Historical console requests a valid numeric value.
#                 continue
#
# Read the current pose.
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
# Store the pose in glass_coordinates.
#             brain.glass_coordinates[idx] = coordinate(x, y, current_zh, current_zm)
# Historical console reports the saved glass number and X/Y/Z values.
#
# Save other poses, such as bottle cap coordinates.
#         elif cmd.startswith('s '):
#             parts = cmd.split()
#             if len(parts) != 2:
# Historical console reports invalid coordinate-save syntax.
#                 continue
#             name = parts[1]
#             if name not in valid_names:
# Historical console lists valid coordinate names.
#                 continue
#             x = brain.leg.getCurrentPos_x()
#             y = brain.leg.getCurrentPos_y()
#             setattr(brain, name, coordinate(x, y, current_zh, current_zm))
# Historical console reports the saved coordinate and its X/Y/Z values.
#
# Handle unknown commands.
#         else:
# Historical console reports an unknown command.
#
# 5. Print all calibration results before exiting.
# Historical console heading: calibration results.
#
# Print glass coordinates.
# Historical console heading: 24 glass positions.
#     for i, coord in enumerate(brain.glass_coordinates):
#         if coord is not None:
# Historical console prints a calibrated glass pose.
#         else:
# Historical console reports an uncalibrated glass.
#
# Print other coordinates.
# Historical console heading: other coordinates.
#     for name in valid_names:
#         val = getattr(brain, name, None)
#         if val is not None:
#             print(f"{name}: X={val.x:.2f}, Y={val.y:.2f}, ZH={val.zh:.2f}, ZM={val.zm:.2f}")
#         else:
# Historical console reports an uncalibrated named pose.
#
# Historical console requests copying the poses into config().glass_coordinates.
#     brain.close()

def verify_coordinates():
    """Interactively verify the measured glass coordinates."""
    print("===== 玻璃坐标验证工具 =====")
    brain = masterController()
    brain.init()
    brain.moveTo(brain.coordinate_origin)

    # Track gripper and pipette heights for fine adjustment.
    current_zh = 0.0
    current_zm = 0.0

    # Record verified glass numbers.
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

        # Handle exit.
        if cmd == 'q':
            break

        # Move to the selected glass.
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
                    # An uncalibrated glass could be skipped, but this demonstration attempts the move.
                    # Prefer warning the operator about missing calibration.
                    continue
                # Move to the stored X/Y/gripper-Z/pipette-Z pose.
                brain.moveTo(coord)
                print(f"已移动到第 {num} 片玻璃")
                print(f"  计算坐标: X={coord.x:.2f}, Y={coord.y:.2f}, ZH={coord.zh:.2f}, ZM={coord.zm:.2f}")
                # Update tracked Z values for later fine-adjustment display.
                current_zh = coord.zh
                current_zm = coord.zm
                if num not in verified_list:
                    verified_list.append(num)
            except ValueError:
                print("请输入有效数字")

        # Print the current pose.
        elif cmd == 'p':
            x = brain.leg.getCurrentPos_x()
            y = brain.leg.getCurrentPos_y()
            print(f"当前位置: X={x:.2f}, Y={y:.2f}, ZH={current_zh:.2f}, ZM={current_zm:.2f}")

        # Clamp or release the gripper.
        elif cmd == 'pick':
            print("夹持测试...")
            brain.clamp_with_detection()
            print("夹持完成")
        elif cmd == 'place':
            print("释放测试...")
            brain.relax()
            print("释放完成")

        # Move the stage for manual fine adjustment.
        elif cmd.startswith('m '):
            parts = cmd.split()
            if len(parts) == 3:
                try:
                    x = float(parts[1])
                    y = float(parts[2])
                    # Raise Z to a safe height before moving X/Y.
                    brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
                    brain.leg.moveTo(x, y)
                    brain.leg.wait_x()
                    brain.leg.wait_y()
                    print(f"移动到 ({x}, {y})")
                except Exception as e:
                    print(f"移动失败: {e}")
            else:
                print("格式错误，请输入 'm x y'")

        # Set the gripper Z height.
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

        # Set the pipette Z height.
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

        # Handle unknown commands.
        else:
            print("未知命令，请参考提示输入")

    # Print verified glass numbers on exit.
    print("\n===== 已验证的玻璃编号 =====")
    if verified_list:
        print(f"共 {len(verified_list)} 片：{sorted(verified_list)}")
    else:
        print("未验证任何玻璃")
    print("验证结束")

    brain.close()


# if __name__ == '__main__':
#     verify_coordinates()

# Test bottle cap rotation with the gripper.
# if __name__ == '__main__':
#     try:
#         brain = masterController()
# Initialize by homing and raising Z to safe heights.
#
# Historical console heading: manual control mode.
# Historical console documents the help command.
# Historical console explains automatic Z raising before stage movement.
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
# Available commands.
# goto X Y raises Z first and then moves the stage.
# zh Z sets the gripper Z position, for example zh 80.
# zm Z sets the pipette Z position, for example zm 18.
# clamp closes the gripper to its preset position.
# relax opens the gripper to its release position.
# spiral DEG rotates the gripper; positive tightens and negative loosens.
# open N opens bottle 1, 2, or 3 using movement, clamping, and rotation.
# close N closes bottle 1, 2, or 3.
# status reports stage positions and Z heights.
# quit exits.
# """)
#
#             elif op == 'goto':
#                 if len(cmd) < 3:
# Historical console reports goto X Y usage.
#                     continue
#                 x, y = float(cmd[1]), float(cmd[2])
# Raise to the safe height first.
#                 brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
# Move the stage.
#                 brain.move_leg_to(x, y)
# Historical console reports the new X/Y positions.
#
#             elif op == 'zh':
#                 if len(cmd) < 2:
# Historical console reports zh Z usage.
#                     continue
#                 z = float(cmd[1])
#                 brain.moveTo_upAndDown(z, brain.coordinate_cur.zm)
# Historical console reports the assigned gripper Z height.
#
#             elif op == 'zm':
#                 if len(cmd) < 2:
# Historical console reports zm Z usage.
#                     continue
#                 z = float(cmd[1])
#                 brain.moveTo_upAndDown(brain.coordinate_cur.zh, z)
# Historical console reports the assigned pipette Z height.
#
#             elif op == 'clamp':
#                 brain.clamp()
# Historical console reports closure to the preset gripper position.
#
#             elif op == 'relax':
#                 brain.relax()
# Historical console reports gripper release.
#
#             elif op == 'spiral':
#                 if len(cmd) < 2:
# Historical console reports spiral DEG usage.
#                     continue
#                 deg = int(cmd[1])
#                 brain.hand.spiral(deg)
# Historical console reports the gripper rotation angle.
#
#             elif op == 'open':
#                 if len(cmd) < 2:
# Historical console reports open N usage with N=1,2,3.
#                     continue
#                 num = int(cmd[1])
#                 if num == 1:
#                     brain.openBottleOne()
#                 elif num == 2:
#                     brain.openBottleTwo()
#                 elif num == 3:
#                     brain.openBottleThree()
#                 else:
# Historical console restricts bottle numbers to 1, 2, or 3.
#                     continue
# Historical console reports the opened bottle number.
#
#             elif op == 'close':
#                 if len(cmd) < 2:
# Historical console reports close N usage with N=1,2,3.
#                     continue
#                 num = int(cmd[1])
#                 if num == 1:
#                     brain.closeBottleOne()
#                 elif num == 2:
#                     brain.closeBottleTwo()
#                 elif num == 3:
#                     brain.closeBottleThree()
#                 else:
# Historical console restricts bottle numbers to 1, 2, or 3.
#                     continue
# Historical console reports the closed bottle number.
#
#             elif op == 'status':
#                 x = brain.leg.getCurrentPos_x()
#                 y = brain.leg.getCurrentPos_y()
#                 zh = brain.coordinate_cur.zh if brain.coordinate_cur else 0
#                 zm = brain.coordinate_cur.zm if brain.coordinate_cur else 0
# Historical console reports stage positions and gripper/pipette Z heights.
#
#             elif op == 'quit':
#                 break
#
#             else:
# Historical console requests help for an unknown command.
#
#     except Exception as e:
# Historical console reports an exception.
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
#         except:
#             pass
#         raise e
#     finally:
# Return to the origin and close devices before exiting.
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
# Historical console reports closed devices and program completion.
#         except:
#             pass

# Test pipette tips.
# if __name__ == '__main__':
#     try:
#         brain = masterController()
# Initialize by homing and raising the axes.
#
# Raise to the highest safe pose before testing.
#         brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)
#
# Historical console heading: tip pickup and return test.
# Historical console reports the total number and range of tips.
# Historical console command help.
# Entering a tip number aligns X/Y above the tip at safe Z heights.
# Command pick descends to attach the tip.
# Command drop descends, ejects the tip, and raises Z.
# Command quit exits.
# Ensure no tip is attached before pickup and a tip is attached before return.
#         print("=====================================\n")
#
# Remember the currently selected tip number.
#
#         while True:
# Historical input prompt requests a command.
#
#             if cmd == 'quit':
#                 break
#
#             elif cmd == 'pick':
#                 if current_num is None:
# Historical console requests a tip number before an action.
#                     continue
# Historical console announces tip pickup.
# pickLip aligns the pipette and descends to attach the tip.
# Historical console requests checking that the tip is firmly attached.
#
#             elif cmd == 'drop':
#                 if current_num is None:
# Historical console requests a tip number before an action.
#                     continue
# Historical console announces tip return.
# relinquishLip descends, ejects the tip, and raises Z.
# Historical console reports return completion and safe pipette height.
#
#             else:
# Try parsing the input as a tip number.
#                 try:
#                     num = int(cmd)
#                     if num < 1 or num > len(brain.lips_coordinates):
# Historical console reports a tip number outside the valid range.
#                         continue
#                     current_num = num
# Look up the tip coordinates.
#                     co = brain.getLipsCoordinate(num)
#                     if co is None:
#                         continue
# Align X/Y at safe gripper and pipette Z heights to avoid pressing the tip.
# Historical safe_zh = Z_SAFE_HAND, corresponding to 1.0.
# Historical safe_zm = Z_SAFE_MOUTH, corresponding to 0.0.
#                     brain.moveTo(coordinate(co.x, co.y, safe_zh, safe_zm))
# Historical console reports alignment above the selected tip.
# Historical console requests checking alignment before pick or drop.
#                 except ValueError:
# Historical console lists numeric, pick, drop, and quit inputs.
#
#     except Exception as e:
# Historical console reports an exception.
# On exception, attempt to return to the origin and close devices.
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
#         except:
#             pass
#         raise e
#     finally:
# Clean up on normal exit as well.
#         try:
#             brain.moveTo(brain.coordinate_origin)
#             brain.close()
# Historical console reports closed devices and test completion.
#         except:
#             pass

# import hand
# import time
#
#
# def explore_z_limits():
# Historical console heading: explore physical Z limits.
# Historical console command help.
# Command +step moves upward by a specified increment.
# Command -step moves downward by a specified increment.
# Command pos shows the virtual position.
# Command set assigns a target position directly.
# Command q exits and records the observed limits.
#     print()
#
# Create the controller with a 60 s timeout for limit exploration.
#     h = hand.controller("COM7", timeout=60)
#
# Virtual position starts at 0; the physical position is initially unknown.
#     current_pos = 0.0
#
# Record observed travel limits.
# Historical upper_limit starts as None.
# Historical lower_limit starts as None.
#
#     while True:
#         try:
#             cmd = input("> ").strip()
#             if cmd.lower() == 'q':
#                 break
#             elif cmd == 'pos':
# Historical console reports the current percentage position.
#             elif cmd.startswith('set '):
#                 parts = cmd.split()
#                 if len(parts) == 2:
#                     new_pos = float(parts[1])
#                     current_pos = new_pos
# Historical console reports the requested target position.
#                     h.moveTo(current_pos)
#                     time.sleep(2)
# Historical console reports completion of movement.
#                 else:
# Historical console reports invalid set syntax.
#             elif cmd.startswith('+'):
#                 step = float(cmd[1:]) if len(cmd) > 1 else 1.0
#                 current_pos += step
# Historical console reports the upward step and target.
#                 try:
#                     h.moveTo(current_pos)
#                     time.sleep(2)
# Historical console reports successful movement.
#                 except Exception as e:
# Historical console reports failure, possibly caused by reaching a limit.
# Record the upper limit.
#                     upper_limit = current_pos - step
# Historical console reports the estimated upper limit.
#             elif cmd.startswith('-'):
#                 step = float(cmd[1:]) if len(cmd) > 1 else 1.0
#                 current_pos -= step
# Historical console reports the downward step and target.
#                 try:
#                     h.moveTo(current_pos)
#                     time.sleep(2)
# Historical console reports successful movement.
#                 except Exception as e:
# Historical console reports failure, possibly caused by reaching a limit.
#                     lower_limit = current_pos + step
# Historical console reports the estimated lower limit.
#             else:
# Historical console reports an unknown command.
#         except KeyboardInterrupt:
#             break
#
#     h.close()
# Historical console heading: exploration results.
#     if upper_limit is not None:
# Historical console reports the upper collision-limit position.
#     else:
# Historical console reports that the upper limit was not explored.
#     if lower_limit is not None:
# Historical console reports the lower collision-limit position.
#     else:
# Historical console reports that the lower limit was not explored.
# Historical console requests using the observed values as software limits.


# if __name__ == '__main__':
#     explore_z_limits()

# Main test entry for all legacy functions.
if __name__ == '__main__':
    try:
        brain = masterController()
        brain.init()  # Initialize by homing and raising Z to a safe height.

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
                brain.moveTo_upAndDown(Z_SAFE_HAND, Z_SAFE_MOUTH)  # Confirm the state again after homing.
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
                accelerating_time = speed / accel  # Seconds.
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
