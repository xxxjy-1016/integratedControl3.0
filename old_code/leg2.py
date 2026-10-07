import json
import os
import serial
import time
import copy
from errors import TLE
from tools import Calculator
from errors import ModbusError

setPosition_x = [0x02, 0x06, 0x21, 0x09, 0x00, 0x01, 0x92, 0x07]  # Set position mode.
setAbsolute_x = [0x02, 0x06, 0x23, 0x11, 0x00, 0x01, 0x13, 0xB8]
setRelative_x = [0x02, 0x06, 0x23, 0x11, 0x00, 0x00, 0xD2, 0x78]
setSomething_x = [0x02, 0x06, 0x23, 0x10, 0x00, 0x03, 0xC3, 0xB9]  # Use the segment number supplied through communication.
setPosition_y = [0x01, 0x06, 0x21, 0x09, 0x00, 0x01, 0x92, 0x34]  # Set position mode.
setAbsolute_y = [0x01, 0x06, 0x23, 0x11, 0x00, 0x01, 0x13, 0x8B]
setRelative_y = [0x01, 0x06, 0x23, 0x11, 0x00, 0x00, 0xD2, 0x4B]
setSomething_y = [0x01, 0x06, 0x23, 0x10, 0x00, 0x03, 0xC3, 0x8A]  # Use the segment number supplied through communication.
query_x = [0x02, 0x03, 0x23, 0x03, 0x00, 0x01, 0x7F, 0xBD]
moveToCommand_x = [0x02, 0x10, 0x23, 0x20, 0x00, 0x02, 0x04]
query_y = [0x01, 0x03, 0x23, 0x03, 0x00, 0x01, 0x7F, 0x8E]
moveToCommand_y = [0x01, 0x10, 0x23, 0x20, 0x00, 0x02, 0x04]
flushOne_x = [0x02, 0x06, 0x23, 0x16, 0x00, 0x00, 0x63, 0xB9]
flushTwo_x = [0x02, 0x06, 0x23, 0x16, 0x00, 0x01, 0xA2, 0x79]
flushOne_y = [0x01, 0x06, 0x23, 0x16, 0x00, 0x00, 0x63, 0x8A]
flushTwo_y = [0x01, 0x06, 0x23, 0x16, 0x00, 0x01, 0xA2, 0x4A]


class controller:

    """Represent controller and its associated operations."""
    def __init__(self, serName, bps=115200, timeout=10, sendingTime=0.1):
        """Initialize controller dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.max_x = 40000
        self.max_y = 80000
        self.offset_x = 0.0  # Zero offset, in percent.
        self.offset_y = 0.0
        self.load_offset()

    def write(self, command):
        """Write."""
        self.ser.write(bytes(command))

    def init_x(self):
        """Init x."""
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
        """Init y."""
        self.writeByBytes(0x6040, 0x06)  # Shutdown
        time.sleep(0.05)
        self.writeByBytes(0x6040, 0x07)  # Switch on disabled
        time.sleep(0.05)
        self.writeByBytes(0x6040, 0x0F)  # Enable operation
        time.sleep(0.05)
        self.writeByBytes(0x6060, 1)  # Position mode.

    def init(self):
        """Init."""
        self.init_x()
        self.init_y()

    def set_x(self, speed, acceleration, deceleration):
        """Set x."""
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
        """Set y."""
        self.writeByBytes(0x6081, Calculator.intToList(speed, length = 4), writeLength = 2)
        self.writeByBytes(0x6083, acceleration)
        self.writeByBytes(0x6084, deceleration)

    def set(self, speed_x=700, acceleration_x=100, deceleration_x=100, speed_y=70, acceleration_y=100,
            deceleration_y=100):
        """Set."""
        self.set_x(speed=speed_x, acceleration=acceleration_x, deceleration=deceleration_x)
        self.set_y(speed=speed_y, acceleration=acceleration_y, deceleration=deceleration_y)

    def flush_x(self):
        """Flush x."""
        self.ser.write(bytes(flushOne_x))
        time.sleep(0.01)
        self.ser.write(bytes(flushTwo_x))
        time.sleep(0.01)

    def flush_y(self):
        """Flush y."""
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
    # Historical byte comparison identifies the arrival response.
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
        """Wait x."""
        stTime = time.time()
        while True:
            self.ser.write(query_x)
            time.sleep(0.05)  # Allow time for hardware processing.
            feedback = self.ser.read(40)

            if feedback.strip() == bytes([0x02, 0x03, 0x02, 0x00, 0x42, 0x7C, 0x75]):
                print("X轴到位")
                return
            if time.time() - stTime > self.timeout:
                raise TLE("leg : X TLE")
            time.sleep(0.05)

    def wait_y(self):
        """Wait y."""
        feedback = self.queryByBytes(0x6041)
        stTime = time.time()
        while True:
            if (feedback[0] & (1 << 10)) != 0:  # The target position has been reached.
                print("Y done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("leg : Y TLE")

            feedback = self.queryByBytes(0x6041)
            #print("feedback : ", feedback)

    def wait(self):
        """Wait."""
        self.wait_x()
        self.wait_y()

    # def moveTo_x(self, input_val):
    # Historical limit check: the new rail permits movement up to 140.
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
        # Apply the additive offset: physical target = operator input + offset.
        """Move to x."""
        actual_input = input_val + self.offset_x
        if not ignore_limit:
            # Check limits against the physical target.
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
        # Apply the additive offset.
        """Move to y."""
        actual_input = input_val + self.offset_y
        if not ignore_limit:
            if actual_input < -100 or actual_input > 100:
                print(f"错误：Y轴目标 {actual_input:.2f}% 超出允许范围 (-100~100)")
                return
        val = int(actual_input / 100.0 * self.max_y)
        self.writeByBytes(0x607A, Calculator.intToList(val, length=4), writeLength=2)
        self.flush_y()

    def moveTo(self, x, y):
        """Move to."""
        self.set()
        self.moveTo_x(x)
        self.wait_x()
        self.moveTo_y(y)
        self.wait_y()

    def moveToDirectly(self, x, y, ignore_limit=False):
        """Move to directly."""
        self.set()
        self.moveTo_x(x, ignore_limit=ignore_limit)
        self.moveTo_y(y, ignore_limit=ignore_limit)
        self.wait()

    def calibrate_zero(self):
        """Record and persist the position after manually moving the rail to its physical origin."""
        self.offset_x = self.getCurrentPos_x()
        self.offset_y = self.getCurrentPos_y()
        print(f"零点校准完成：X偏移={self.offset_x:.2f}, Y偏移={self.offset_y:.2f}")

    def save_offset(self):
        """Save offset."""
        data = {"offset_x": self.offset_x, "offset_y": self.offset_y}
        with open("leg_offset.json", "w") as f:
            json.dump(data, f)
        print(f"偏移量已保存: X={self.offset_x:.2f}, Y={self.offset_y:.2f}")

    def load_offset(self):
        """Load offset."""
        if os.path.exists("leg_offset.json"):
            with open("leg_offset.json", "r") as f:
                data = json.load(f)
            self.offset_x = data.get("offset_x", 0.0)
            self.offset_y = data.get("offset_y", 0.0)
            print(f"偏移量已加载: X={self.offset_x:.2f}, Y={self.offset_y:.2f}")
        else:
            print("未找到偏移量文件，使用默认偏移 (0, 0)")

    def close(self):
        """Close."""
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
    # Historical timing experiment: increase the send delay from 0.02 s to 0.1 s.
    #     feedback = self.ser.read(40)
    #     feedbackList = list(feedback.strip())
    #
    # Debug the actual received response.
    # Historical debug output prints the transmitted bytes.
    # Historical debug output prints the received bytes.
    #
    #     return feedbackList

    def communicateByList(self, command):
        # Historical input-buffer reset, suggested for removal or disabling.
        # Historical output-buffer reset, suggested for removal or disabling.
        """Communicate by list."""
        self.ser.write(bytes(command))
        time.sleep(self.sendingTime)
        feedback = self.ser.read(40)
        feedbackList = list(feedback.strip())
        return feedbackList

    def queryByBytes(self, queryAddress, queryLength=2, queryDevice=1, returnType="register"):
        """Query by bytes."""
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
        """Write by bytes."""
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

        # Raise a clearer error when the feedback list is empty.
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
        """Get current pos x."""
        pos = self.queryByBytes(0x6064, 2, 2, 'bytes')
        pos_100_x = int.from_bytes(pos, byteorder='big', signed=True)
        pos_100_x = pos_100_x / self.max_x * 100
        return pos_100_x

    def getCurrentPos_y(self):
        """Get current pos y."""
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
# Historical test configures X only: speed=700, acceleration=100, deceleration=100.
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
# Historical controller connection uses COM8.
# Initialize Y mode and enable the axis.
# Configure Y speed, acceleration, and deceleration.
# Historical test moves Y to 20 percent.
# Wait for Y arrival.
# Return Y to 0.
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
        # Calibrate zero after manually placing the rail at its physical origin; needed once initially.
        leg.calibrate_zero()

        # Run movement tests.
        leg.moveTo(0, 0)
        leg.wait_x()
        leg.wait_y()
        print("移动到原点")

        leg.moveTo(70, 50)
        leg.wait_x()
        leg.wait_y()
        print("移动到中间")

        leg.moveTo(140, 100)  # The maximum X value is 140.
        leg.wait_x()
        leg.wait_y()
        print("移动到最大位置")

        # Return to the original pose after all processes finish.
        leg.moveTo(0, 0)
        leg.wait_x()
        leg.wait_y()
        print("回到原位")

        leg.close()
    except Exception as e:
        leg.close()
        raise e