import serial
import time
import copy
from errors import TLE
from tools import Calculator
from errors import ModbusError

setPosition_x = [0x02, 0x06, 0x21, 0x09, 0x00, 0x01, 0x92, 0x07] # set mode to 位置模式
setAbsolute_x = [0x02, 0x06, 0x23, 0x11, 0x00, 0x01, 0x13, 0xB8]
setRelative_x = [0x02, 0x06, 0x23, 0x11, 0x00, 0x00, 0xD2, 0x78]
setSomething_x = [0x02, 0x06, 0x23, 0x10, 0x00, 0x03, 0xC3, 0xB9] #设定为通讯设定段号运行
setPosition_y = [0x01, 0x06, 0x21, 0x09, 0x00, 0x01, 0x92, 0x34] # set mode to 位置模式
setAbsolute_y = [0x01, 0x06, 0x23, 0x11, 0x00, 0x01, 0x13, 0x8B]
setRelative_y = [0x01, 0x06, 0x23, 0x11, 0x00, 0x00, 0xD2, 0x4B]
setSomething_y = [0x01, 0x06, 0x23, 0x10, 0x00, 0x03, 0xC3, 0x8A] #设定为通讯设定段号运行
query_x = [0x02, 0x03, 0x23, 0x03, 0x00, 0x01, 0x7F, 0xBD]
moveToCommand_x = [0x02, 0x10, 0x23, 0x20, 0x00, 0x02, 0x04]
query_y = [0x01, 0x03, 0x23, 0x03, 0x00, 0x01, 0x7F, 0x8E]
moveToCommand_y = [0x01, 0x10, 0x23, 0x20, 0x00, 0x02, 0x04]
flushOne_x = [0x02, 0x06, 0x23, 0x16, 0x00, 0x00, 0x63, 0xB9]
flushTwo_x = [0x02, 0x06, 0x23, 0x16, 0x00, 0x01, 0xA2, 0x79]
flushOne_y = [0x01, 0x06, 0x23, 0x16, 0x00, 0x00, 0x63, 0x8A]
flushTwo_y = [0x01, 0x06, 0x23, 0x16, 0x00, 0x01, 0xA2, 0x4A]

class controller:

    def __init__(self, serName, bps = 115200, timeout = 10, sendingTime = 0.15):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.ser = serial.Serial(self.serName, self.bps, timeout = 1)
        self.max_x = 40000
        self.max_y = 20000

    def write(self, command):
        self.ser.write(bytes(command))

    def init_x(self):
        self.ser.write(bytes(setPosition_x))
        time.sleep(0.01)
        self.ser.write(bytes(setAbsolute_x))
        time.sleep(0.01)
        self.ser.write(bytes(setSomething_x))
        time.sleep(0.01)

    def init_y(self):
        self.ser.write(bytes(setPosition_y))
        time.sleep(0.01)
        self.ser.write(bytes(setAbsolute_y))
        time.sleep(0.01)
        self.ser.write(bytes(setSomething_y))
        time.sleep(0.01)

    def init(self):
        self.init_x()
        self.init_y()

    def set_x(self, speed = 500, acceleration = 100, deceleration = 100):
        command = [0x02, 0x06, 0x23, 0x21]
        command += Calculator.intToList(speed)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        command = [0x02, 0x06, 0x23, 0x22]
        command += Calculator.intToList(acceleration)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        command = [0x02, 0x06, 0x23, 0x23]
        command += Calculator.intToList(deceleration)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)

    def set_y(self, speed = 500, acceleration = 100, deceleration = 100):
        command = [0x01, 0x06, 0x23, 0x21]
        command += Calculator.intToList(speed)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        command = [0x01, 0x06, 0x23, 0x22]
        command += Calculator.intToList(acceleration)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        command = [0x01, 0x06, 0x23, 0x23]
        command += Calculator.intToList(deceleration)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)

    def set(self, speed_x = 500, acceleration_x = 100, deceleration_x = 100, speed_y = 500, acceleration_y = 100, deceleration_y = 100):
        self.set_x(speed = speed_x, acceleration = acceleration_x, deceleration = deceleration_x)
        self.set_y(speed = speed_y, acceleration = acceleration_y, deceleration = deceleration_y)

    def flush_x(self):
        self.ser.write(bytes(flushOne_x))
        time.sleep(0.01)
        self.ser.write(bytes(flushTwo_x))
        time.sleep(0.01)

    def flush_y(self):
        self.ser.write(bytes(flushOne_y))
        time.sleep(0.01)
        self.ser.write(bytes(flushTwo_y))
        time.sleep(0.01)

    def wait_x(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_x)
        time.sleep(0.01)
        stTime = time.time()
        while True:
            #print("query sent")
            feedback = self.ser.read(40)

            #print("in wait_x, feedback = " + ' '.join(f'{x:02X}' for x in feedback))

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if feedback.strip() == bytes([0x02, 0x03, 0x02, 0x00, 0x42, 0x7C, 0x75]): #到位
                #print("X done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("leg : X TLE")

            self.ser.write(query_x)
            time.sleep(0.01)

    def wait_y(self):
        stTime = time.time()
        while True:
            self.ser.write(query_y)
            time.sleep(0.05)
            feedback = self.ser.read(40)

            # 打印实际收到的数据（十六进制）
            hex_feedback = ' '.join(f'{x:02X}' for x in feedback)
            print(f"Y轴查询反馈: {hex_feedback}")

            if feedback.strip() == bytes([0x01, 0x03, 0x02, 0x00, 0x42, 0x38, 0x75]):
                print("Y轴到位")
                return
            if time.time() - stTime > self.timeout:
                raise TLE("leg : Y TLE")
            time.sleep(0.05)

    def wait(self):
        self.wait_x()
        self.wait_y()

    def moveTo_x(self, input_val):
        if input_val > 100 :
            print("wrong x input!")
            return
        val = int(input_val /100.0 * self.max_x)
        command = copy.deepcopy(moveToCommand_x)
        command += Calculator.intToList(val, length = 4)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        self.flush_x()
        time.sleep(0.01)

    def moveTo_y(self, input_val):
        if input_val > 100 :
            print("wrong y input!")
            return
        val = int(input_val /100.0 * self.max_y)
        command = copy.deepcopy(moveToCommand_y)
        command += Calculator.intToList(val, length = 4)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.ser.write(bytes(command))
        time.sleep(0.01)
        self.flush_y()
        time.sleep(0.01)

    def moveTo(self, x, y):
        self.ser.reset_input_buffer()
        self.set()
        self.moveTo_x(x)
        self.wait_x()
        self.moveTo_y(y)
        self.wait_y()

    def moveToDirectly(self, x, y):
        self.set()
        self.moveTo_x(x)
        self.moveTo_y(y)
        self.wait()

    def close(self):
        self.ser.close()

    def communicateByList(self, command):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(bytes(command))
        time.sleep(self.sendingTime)
        feedback = self.ser.read(40)
        feedbackList = list(feedback.strip())
        return feedbackList

    def queryByBytes(self, queryAddress, queryLength = 2, queryDevice = 1, returnType = "register"):
        command = [queryDevice, 0x03] + Calculator.intToList(queryAddress) + Calculator.intToList(queryLength)
        command += Calculator.crc(bytes(command), flag = 'list')
        feedbackList = self.communicateByList(command)
        #return feedbackList
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

    def getCurrentPos_x(self):
        pos = self.queryByBytes(0x6064,2,2,'bytes')
        pos_100_x = int.from_bytes(pos, byteorder='big', signed=True)
        pos_100_x = pos_100_x / self.max_x * 100
        return pos_100_x

    def getCurrentPos_y(self):
        pos = self.queryByBytes(0x6064, 2, 1, 'bytes')
        pos_100_y = int.from_bytes(pos, byteorder='big', signed=True)
        pos_100_y = pos_100_y / self.max_y * 100
        return pos_100_y

if __name__ == "__main__":
    try:
        leg = controller("COM8")
        leg.init()
        leg.set()
        leg = controller("COM8")
        leg.init()
        print(f"当前Y轴位置: {leg.getCurrentPos_y()}%")
        leg.moveTo(50, 50)  # 先移动到中间位置
        print(f"移动后Y轴位置: {leg.getCurrentPos_y()}%")
        leg.moveTo(0,0)
        for i in range(100):
            print(leg.getCurrentPos_y())
        leg.moveToDirectly(100, 100)
        leg.moveToDirectly(70, 70)
        leg.getCurrentPos_x()
        leg.getCurrentPos_y()
        leg.close()
    except Exception as e:
        leg.close()
        raise e
#
# import serial.tools.list_ports
# ports = serial.tools.list_ports.comports()
# for port in ports:
#     print(port.device, port.description)