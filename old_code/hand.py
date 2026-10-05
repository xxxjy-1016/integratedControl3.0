import serial
import time
import binascii
from errors import TLE
from tools import Calculator

init_rj_clamp = bytes([0x01, 0x06, 0x01, 0x00, 0x00, 0x01, 0x49, 0xF6])
init_rj_spiral = bytes([0x01, 0x06, 0x01, 0x01, 0x00, 0x01, 0x18, 0x36])
init_dcm = '>02G9158'#9158

query_rj_clamp = bytes([0x01, 0x03, 0x02, 0x02, 0x00, 0x01, 0x24, 0x72])
query_rj_spiral = bytes([0x01, 0x03, 0x02, 0x03, 0x00, 0x01, 0x75, 0xB2])
query_dcm = '>02d4819'


class controller:
    def __init__(self, serName, bps=115200, timeout=10):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)

    def query_rj_position(self):
        """
        查询夹爪当前开度位置（0~100）
        """
        command = [0x01, 0x03, 0x02, 0x04, 0x00, 0x01, 0xC4, 0x73]
        self.ser.write(command)
        time.sleep(0.1)
        response = list(self.ser.read(40))
        # 响应格式：设备地址、功能码、数据长度、数据高字节、数据低字节、CRC...
        if len(response) >= 5:
            return response[4]  # 返回位置值（0~100）
        else:
            return 0

    def wait_rj_clamp_tight(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_rj_clamp)
        time.sleep(0.1)
        stTime = time.time()
        while True:
            # print("query sent")
            feedback = self.ser.read(40)

            # print("in wait_tj_clamp_tight, feedback = " + binascii.hexlify(feedback).decode('ascii'))

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if feedback.strip() == bytes([0x01, 0x03, 0x02, 0x00, 0x02, 0x39, 0x85]) or bytes(
                    [0x01, 0x03, 0x02, 0x00, 0x01, 0x79, 0x84]):  # 卡在中间位置，也就是说夹住了
                # print("done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("hand : RJ TLE")

            self.ser.write(query_rj_clamp)
            time.sleep(0.1)

    def wait_rj_clamp_position(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_rj_clamp)
        time.sleep(0.1)
        stTime = time.time()
        while True:
            # print("query sent")
            feedback = self.ser.read(40)

            # print("in wait_tj_clamp_position, feedback = " + binascii.hexlify(feedback).decode('ascii'))

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if feedback.strip() == bytes([0x01, 0x03, 0x02, 0x00, 0x01, 0x79, 0x84]):  # 到位
                # print("done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("hand : RJ TLE")

            self.ser.write(query_rj_clamp)
            time.sleep(0.1)

    def wait_rj_spiral_tight(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_rj_spiral)
        time.sleep(0.1)
        stTime = time.time()
        while True:
            # print("query sent")
            feedback = self.ser.read(40)

            # print("in wait_tj_spiral_position, feedback = " + binascii.hexlify(feedback).decode('ascii'))

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if feedback.strip() == bytes([0x01, 0x03, 0x02, 0x00, 0x02, 0x39, 0x85]) or feedback.strip() == bytes(
                    [0x01, 0x03, 0x02, 0x00, 0x01, 0x79, 0x84]):
                # print("done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("hand : RJ TLE")

            self.ser.write(query_rj_spiral)
            time.sleep(0.1)

    def wait_rj_spiral_position(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_rj_spiral)
        time.sleep(0.1)
        stTime = time.time()
        while True:
            # print("query sent")
            feedback = self.ser.read(40)

            # print("in wait_tj_spiral_position, feedback = " + binascii.hexlify(feedback).decode('ascii'))

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if feedback.strip() == bytes([0x01, 0x03, 0x02, 0x00, 0x01, 0x79, 0x84]):
                # print("done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("hand : RJ TLE")

            self.ser.write(query_rj_spiral)
            time.sleep(0.1)

    def wait_dcm_position(self):
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_dcm.encode('utf-8'))
        time.sleep(0.1)
        stTime = time.time()
        while True:
            # print("query sent")
            feedback = self.ser.read(40).decode('ascii', errors='ignore')

            # print("in wait_tj_dcm, feedback = " + feedback)

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            if feedback.strip() == '>02d0172DE':
                # print("done, exiting")
                return

            curTime = time.time()

            if curTime - stTime > self.timeout:
                raise TLE("hand : DCM TLE")

            self.ser.write(query_dcm.encode('utf-8'))
            time.sleep(0.1)

    def init_rj_clamp(self):
        self.ser.write(init_rj_clamp)
        time.sleep(0.1)
        self.wait_rj_clamp_position()

    def init_rj_spiral(self):
        self.ser.write(init_rj_spiral)
        time.sleep(0.1)
        self.wait_rj_spiral_position()

    def init_rj(self):
        self.init_rj_clamp()
        self.init_rj_spiral()

    def init_dcm(self):
        self.ser.write(init_dcm.encode('utf-8'))
        time.sleep(0.1)
        self.wait_dcm_position()

    def init(self):
        self.init_rj()
        self.init_dcm()

    def set_rj_clampTorque(self, ratio):
        """
        设置夹爪扭矩
        ratio: 0~100 的数值，表示扭矩百分比
        """
        command = [0x01, 0x06, 0x01, 0x03]
        command += Calculator.intToList(ratio, 2)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.1)

    def clamp(self, grabby=100):  # grabby: 0-100, the extend of grabbing
        command = [0x01, 0x06, 0x01, 0x05]
        command += [grabby // 256, grabby % 256]
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.1)
        self.wait_rj_clamp_tight()

    def clamp_position(self, grabby):
        command = [0x01, 0x06, 0x01, 0x05]
        command += [grabby // 256, grabby % 256]
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.1)
        self.wait_rj_clamp_position()

    def spiral(self, deg=0):
        command = [0x01, 0x06, 0x01, 0x08]
        command += Calculator.intToList(deg)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.1)
        self.wait_rj_spiral_tight()

    def spiral_position(self, deg):
        command = [0x01, 0x06, 0x01, 0x08]
        command += Calculator.intToList(deg)
        command += Calculator.crc(bytes(command), flag='list')
        self.ser.write(bytes(command))
        time.sleep(0.1)
        self.wait_rj_spiral_position()

    def moveTo(self, idis):
        dis = int(idis / 100.0 * 15000)
        command = '>02D'
        list_dis = Calculator.intToList(dis, length=4)
        for i in range(4):
            command += hex(list_dis[i])[2:].zfill(2)
        command += Calculator.crc(command.encode('utf-8'), 'str')
        self.ser.write(command.encode('utf-8'))
        time.sleep(0.1)
        self.wait_dcm_position()

    def moveBy(self, dis):
        print("error! undefined function")
        raise TLE('not a tle')

    def close(self):
        self.ser.close()


if __name__ == '__main__':
    try:
        hand = controller("COM7")
        hand.init()
        hand.moveTo(30)
        hand.clamp()
        hand.spiral(-540)
        hand.clamp(0)
        hand.moveTo(0)
        hand.init()
        hand.close()
    except Exception as e:
        hand.close()
        raise e



