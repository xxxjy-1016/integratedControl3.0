import json
import os
import serial
import time
import copy
from errors import TLE
from tools import Calculator
from errors import ModbusError

setPosition_x = [0x02, 0x06, 0x21, 0x09, 0x00, 0x01, 0x92, 0x07]  # set mode to 位置模式
setAbsolute_x = [0x02, 0x06, 0x23, 0x11, 0x00, 0x01, 0x13, 0xB8]
setRelative_x = [0x02, 0x06, 0x23, 0x11, 0x00, 0x00, 0xD2, 0x78]
setSomething_x = [0x02, 0x06, 0x23, 0x10, 0x00, 0x03, 0xC3, 0xB9]  # 设定为通讯设定段号运行
setPosition_y = [0x01, 0x06, 0x21, 0x09, 0x00, 0x01, 0x92, 0x34]  # set mode to 位置模式
setAbsolute_y = [0x01, 0x06, 0x23, 0x11, 0x00, 0x01, 0x13, 0x8B]
setRelative_y = [0x01, 0x06, 0x23, 0x11, 0x00, 0x00, 0xD2, 0x4B]
setSomething_y = [0x01, 0x06, 0x23, 0x10, 0x00, 0x03, 0xC3, 0x8A]  # 设定为通讯设定段号运行
query_x = [0x02, 0x03, 0x23, 0x03, 0x00, 0x01, 0x7F, 0xBD]
moveToCommand_x = [0x02, 0x10, 0x23, 0x20, 0x00, 0x02, 0x04]
query_y = [0x01, 0x03, 0x23, 0x03, 0x00, 0x01, 0x7F, 0x8E]
moveToCommand_y = [0x01, 0x10, 0x23, 0x20, 0x00, 0x02, 0x04]
flushOne_x = [0x02, 0x06, 0x23, 0x16, 0x00, 0x00, 0x63, 0xB9]
flushTwo_x = [0x02, 0x06, 0x23, 0x16, 0x00, 0x01, 0xA2, 0x79]
flushOne_y = [0x01, 0x06, 0x23, 0x16, 0x00, 0x00, 0x63, 0x8A]
flushTwo_y = [0x01, 0x06, 0x23, 0x16, 0x00, 0x01, 0xA2, 0x4A]


class controller:

    def __init__(self, serName, bps=115200, timeout=10, sendingTime=0.1):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.max_x = 40000
        self.max_y = 80000
        self.offset_x = 0.0  # 零点偏移，单位：%
        self.offset_y = 0.0
        self.load_offset()

    def write(self, command):
        self.ser.write(bytes(command))

    def init_x(self):
        self.ser.write(bytes(setPosition_x))
        time.sleep(0.01)
        self.ser.write(bytes(setAbsolute_x))
        time.sleep(0.01)
        self.ser.write(bytes(setSomething_x))
        time.sleep(0.01)

    # def init_y(self):
    #     self.writeByBytes(0x6040, 0x0F)
    #     self.writeByBytes(0x6060, 1) # position mode
    #     #self.ser.write(bytes(setAbsolute_y))
    #     #time.sleep(0.01)

    def init_y(self):
        self.writeByBytes(0x6040, 0x06)  # Shutdown
        time.sleep(0.05)
        self.writeByBytes(0x6040, 0x07)  # Switch on disabled
        time.sleep(0.05)
        self.writeByBytes(0x6040, 0x0F)  # Enable operation
        time.sleep(0.05)
        self.writeByBytes(0x6060, 1)  # 位置模式

    def init(self):
        self.init_x()
        self.init_y()

    def set_x(self, speed, acceleration, deceleration):
        command = [0x02, 0x06, 0x23, 0x21]
        command += Calculator.intToList(speed)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        command = [0x02, 0x06, 0x23, 0x22]
        command += Calculator.intToList(acceleration)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        command = [0x02, 0x06, 0x23, 0x23]
        command += Calculator.intToList(deceleration)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.01)

    def set_y(self, speed, acceleration, deceleration):
        self.writeByBytes(0x6081, Calculator.intToList(speed, length = 4), writeLength = 2)
        self.writeByBytes(0x6083, acceleration)
        self.writeByBytes(0x6084, deceleration)

    def set(self, speed_x=700, acceleration_x=100, deceleration_x=100, speed_y=70, acceleration_y=100,
            deceleration_y=100):
        self.set_x(speed=speed_x, acceleration=acceleration_x, deceleration=deceleration_x)
        self.set_y(speed=speed_y, acceleration=acceleration_y, deceleration=deceleration_y)

    def flush_x(self):
        self.ser.write(bytes(flushOne_x))
        time.sleep(0.01)
        self.ser.write(bytes(flushTwo_x))
        time.sleep(0.01)

    def flush_y(self):
        self.writeByBytes(0x6040, 0b10011111)
        self.writeByBytes(0x6040, 0b10001111)

    # def wait_x(self):
    #     self.ser.reset_input_buffer()
    #     self.ser.reset_output_buffer()
    #     self.ser.write(query_x)
    #     time.sleep(0.01)
    #     stTime = time.time()
    #     while True:
    #         # print("query sent")
    #         feedback = self.ser.read(40)
    #
    #         # print("in wait_x, feedback = " + ' '.join(f'{x:02X}' for x in feedback))
    #
    #         self.ser.reset_input_buffer()
    #         self.ser.reset_output_buffer()
    #
    #         if feedback.strip() == bytes([0x02, 0x03, 0x02, 0x00, 0x42, 0x7C, 0x75]):  # 到位
    #             # print("X done, exiting")
    #             return
    #
    #         curTime = time.time()
    #
    #         if curTime - stTime > self.timeout:
    #             raise TLE("leg : X TLE")
    #
    #         self.ser.write(query_x)
    #         time.sleep(0.01)

    def wait_x(self):
        stTime = time.time()
        while True:
            self.ser.write(query_x)
            time.sleep(0.05)  # 给硬件处理时间
            feedback = self.ser.read(40)

            if feedback.strip() == bytes([0x02, 0x03, 0x02, 0x00, 0x42, 0x7C, 0x75]):
                print("X轴到位")
                return
            if time.time() - stTime > self.timeout:
                raise TLE("leg : X TLE")
            time.sleep(0.05)

    def wait_y(self):
        feedback = self.queryByBytes(0x6041)
        stTime = time.time()
        while True:
            if (feedback[0] & (1 << 10)) != 0:  # 到位
                print("Y done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("leg : Y TLE")

            feedback = self.queryByBytes(0x6041)
            #print("feedback : ", feedback)

    def wait(self):
        self.wait_x()
        self.wait_y()

    # def moveTo_x(self, input_val):
    #     if input_val > 120:   #新导轨长度支持移动到140
    #         print("wrong x input!")
    #         return
    #     val = int(input_val / 100.0 * self.max_x)
    #     command = copy.deepcopy(moveToCommand_x)
    #     command += Calculator.intToList(val, length=4)
    #     command += Calculator.crc(bytes(command), flag='list')
    #     self.ser.write(bytes(command))
    #     time.sleep(0.01)
    #     self.flush_x()
    #     time.sleep(0.01)

    def moveTo_x(self, input_val, ignore_limit=False):
        # 应用加法偏移：实际目标 = 用户输入 + 偏移量
        actual_input = input_val + self.offset_x
        if not ignore_limit:
            # 限位检查基于实际目标值
            if actual_input < -140 or actual_input > 140:
                print(f"错误：X轴目标 {actual_input:.2f}% 超出允许范围 (-140~140)")
                return
        val = int(actual_input / 100.0 * self.max_x)
        command = copy.deepcopy(moveToCommand_x)
        command += Calculator.intToList(val, length=4)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        self.flush_x()
        time.sleep(0.01)

    # def moveTo_y(self, input_val):
    #     if input_val > 100:
    #         print("wrong y input!")
    #         return
    #     val = int(input_val / 100.0 * self.max_y)
    #     self.writeByBytes(0x607A, Calculator.intToList(val, length=4), writeLength = 2)
    #     self.flush_y()

    def moveTo_y(self, input_val, ignore_limit=False):
        # 应用加法偏移
        actual_input = input_val + self.offset_y
        if not ignore_limit:
            if actual_input < -100 or actual_input > 100:
                print(f"错误：Y轴目标 {actual_input:.2f}% 超出允许范围 (-100~100)")
                return
        val = int(actual_input / 100.0 * self.max_y)
        self.writeByBytes(0x607A, Calculator.intToList(val, length=4), writeLength=2)
        self.flush_y()

    def moveTo(self, x, y):
        self.set()
        self.moveTo_x(x)
        self.wait_x()
        self.moveTo_y(y)
        self.wait_y()

    def moveToDirectly(self, x, y, ignore_limit=False):
        self.set()
        self.moveTo_x(x, ignore_limit=ignore_limit)
        self.moveTo_y(y, ignore_limit=ignore_limit)
        self.wait()

    def calibrate_zero(self):
        """
        手动将滑轨推到物理零点后调用，记录当前位置并保存到文件。
        """
        self.offset_x = self.getCurrentPos_x()
        self.offset_y = self.getCurrentPos_y()
        print(f"零点校准完成：X偏移={self.offset_x:.2f}, Y偏移={self.offset_y:.2f}")

    def save_offset(self):
        data = {"offset_x": self.offset_x, "offset_y": self.offset_y}
        with open("leg_offset.json", "w") as f:
            json.dump(data, f)
        print(f"偏移量已保存: X={self.offset_x:.2f}, Y={self.offset_y:.2f}")

    def load_offset(self):
        if os.path.exists("leg_offset.json"):
            with open("leg_offset.json", "r") as f:
                data = json.load(f)
            self.offset_x = data.get("offset_x", 0.0)
            self.offset_y = data.get("offset_y", 0.0)
            print(f"偏移量已加载: X={self.offset_x:.2f}, Y={self.offset_y:.2f}")
        else:
            print("未找到偏移量文件，使用默认偏移 (0, 0)")

    def close(self):
        self.ser.close()

    # def communicateByList(self, command):
    #     self.ser.reset_input_buffer()
    #     self.ser.reset_output_buffer()
    #     self.ser.write(bytes(command))
    #     time.sleep(self.sendingTime)
    #     feedback = self.ser.read(40)
    #     feedbackList = list(feedback.strip())
    #     return feedbackList

    # def communicateByList(self, command):
    #     self.ser.reset_input_buffer()
    #     self.ser.reset_output_buffer()
    #     self.ser.write(bytes(command))
    #     time.sleep(self.sendingTime)  # 0.02秒可能太短，改为 0.1 试试
    #     feedback = self.ser.read(40)
    #     feedbackList = list(feedback.strip())
    #
    #     # 调试打印：看看实际收到了什么
    #     print(f"发送命令: {' '.join(f'{x:02X}' for x in command)}")
    #     print(f"接收反馈: {' '.join(f'{x:02X}' for x in feedbackList)}")
    #
    #     return feedbackList

    def communicateByList(self, command):
        # self.ser.reset_input_buffer()   # 注释或删除
        # self.ser.reset_output_buffer()  # 注释或删除
        self.ser.write(bytes(command))
        time.sleep(self.sendingTime)
        feedback = self.ser.read(40)
        feedbackList = list(feedback.strip())
        return feedbackList

    def queryByBytes(self, queryAddress, queryLength=2, queryDevice=1, returnType="register"):
        command = [queryDevice, 0x03] + Calculator.intToList(queryAddress) + Calculator.intToList(queryLength)
        command += Calculator.crc(bytes(command), flag='list')
        feedbackList = self.communicateByList(command)
        # return feedbackList
        if feedbackList[1] > 0x20:
            feedbackList = self.communicateByList(command)
            if feedbackList[1] > 0x20:
                raise ModbusError

        ans = []
        if returnType == "register":
            for i in range(queryLength):
                ans.append(feedbackList[2 * i + 3] * 256 + feedbackList[2 * i + 4])

        if returnType == "bytes":
            for i in range(queryLength * 2):
                ans.append(feedbackList[i + 3])

        return ans

    def writeByBytes(self, writeAddress, data, writeLength = 1, writeDevice = 1):
        command = []
        if writeLength == 1:
            command = [writeDevice, 0x06] + Calculator.intToList(writeAddress) + Calculator.intToList(data)
            command += Calculator.crc(bytes(command), flag = 'list')
        else:
            command = [writeDevice, 0x10] + Calculator.intToList(writeAddress) + Calculator.intToList(writeLength) + [2 * writeLength]
            for cur in data:
                command += Calculator.intToList(cur, length = 1)
            command += Calculator.crc(bytes(command), flag = 'list')

        feedbackList = self.communicateByList(command)

        # 如果反馈列表为空，抛出更明确的错误
        if not feedbackList:
            raise ModbusError("No response from device (writeByBytes)")
        if len(feedbackList) < 2:
            raise ModbusError(f"Incomplete response: {feedbackList}")

        if feedbackList[1] > 0x20:
            feedbackList = self.communicateByList(command)
            if feedbackList[1] > 0x20:
                raise ModbusError
        return 0

    def getCurrentPos_x(self):
        pos = self.queryByBytes(0x6064, 2, 2, 'bytes')
        pos_100_x = int.from_bytes(pos, byteorder='big', signed=True)
        pos_100_x = pos_100_x / self.max_x * 100
        return pos_100_x

    def getCurrentPos_y(self):
        pos = self.queryByBytes(0x6064, 2, 1, 'bytes')
        pos_100_y = int.from_bytes(pos, byteorder='big', signed=True)
        pos_100_y = pos_100_y / self.max_y * 100
        return pos_100_y


# if __name__ == "__main__":
#     try:
#         leg = controller("COM8")
#         # leg.init_x()
#         # leg.set()
#         # leg.moveTo_x(20)
#         # leg.wait_x()
#         # leg.moveTo_x(0)
#         # leg.wait_x()
#         '''leg.moveTo_x(50)
#         leg.wait_x()
#         leg.moveTo_x(0)
#         leg.wait_x()
#         leg.moveTo_x(100)
#         leg.wait_x()
#         leg.moveTo_x(0)
#         leg.wait_x()'''
#         leg.init()
#         leg.set()
#         leg.moveTo(0,0)
#         for i in range(100):
#            print(leg.getCurrentPos_y())
#         leg.moveToDirectly(100, 100)
#         leg.moveToDirectly(70, 70)
#         leg.getCurrentPos_x()
#         leg.getCurrentPos_y()
#         leg.moveTo_x(0)
#         leg.wait_x()
#         leg.moveTo_y(0)
#         leg.wait_y()
#         leg.close()
#     except Exception as e:
#         leg.close()
#         raise e

# if __name__ == "__main__":
#     try:
#         leg = controller("COM8")
#         leg.init_x()
#         leg.set_x(speed=700, acceleration=100, deceleration=100)  # 只设置 X 轴
#         leg.moveTo_x(20)
#         leg.wait_x()
#         leg.moveTo_x(0)
#         leg.wait_x()
#         leg.close()
#     except Exception as e:
#         leg.close()
#         raise e

# if __name__ == "__main__":
#     try:
#         leg = controller("COM8")        # 使用 COM8
#         leg.init_y()                    # 初始化 Y 轴（模式、使能）
#         leg.set_y(speed=700, acceleration=100, deceleration=100)  # 设置速度、加减速
#         leg.moveTo_y(20)                # 移动到 20% 位置
#         leg.wait_y()                    # 等待到位
#         leg.moveTo_y(0)                 # 回到 0
#         leg.wait_y()
#         leg.close()
#     except Exception as e:
#         leg.close()
#         raise e

if __name__ == "__main__":
    try:
        leg = controller("COM8")
        leg.init()
        leg.set()
        # 校准零点（首次使用需要手动推到物理零点后执行一次，之后可以注释掉）
        leg.calibrate_zero()

        # 执行一些运动测试
        leg.moveTo(0, 0)
        leg.wait_x()
        leg.wait_y()
        print("移动到原点")

        leg.moveTo(70, 50)
        leg.wait_x()
        leg.wait_y()
        print("移动到中间")

        leg.moveTo(140, 100)  # X轴最大140
        leg.wait_x()
        leg.wait_y()
        print("移动到最大位置")

        # ---------- 完成所有进程后回到原位 ----------
        leg.moveTo(0, 0)
        leg.wait_x()
        leg.wait_y()
        print("回到原位")

        leg.close()
    except Exception as e:
        leg.close()
        raise e