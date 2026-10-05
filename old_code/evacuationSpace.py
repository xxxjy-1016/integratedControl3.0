import serial
import time

from mypy.plugins.enums import enum_value_callback

from errors import TLE
from tools import Calculator
import threading
from dataStructures import *

setAbsolutePosition = [0x01, 0x06, 0x00, 0x36, 0x00, 0x01, 0xCF, 0x28]
setEnable = [0x01, 0x06, 0x00, 0x39, 0x00, 0x01, 0x98, 0x07]
setRun = [0x01, 0x06, 0x00, 0x37, 0x00, 0x01, 0xF9, 0xC4]

stop = [0x01, 0x06, 0x00, 0x38, 0x00, 0x00, 0x08, 0x07]
emergentStop = [0x01, 0x06, 0x00, 0x38, 0x00, 0x01, 0xC9, 0xC7]
expectedStop = [0x01, 0x06, 0x00, 0x38, 0x00, 0x02, 0x89, 0xC6]

class controller:
    def __init__(self, serName, bps=9600, timeout=10):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.openPos = 0
        self.closePos = 250
        self.motionTime = 2.5#原来是2.1
        self.sendingTime = 0.1

    def setArgs(self, accTime, decTime, speed, initSpeed = 10):
        command = [0x01, 0x06, 0x00, 0x1E, 0x07, 0xD0, 0xEA, 0x60]
        self.writeList(command)
        command = [0x01, 0x06, 0x00, 0x1F, 0x03, 0xE8, 0xB8, 0xB2]
        self.writeList(command)

        setInitSpeed = [0x01, 0x06, 0x00, 0x30]
        setInitSpeed += Calculator.intToList(initSpeed)
        setInitSpeed += Calculator.crc(bytes(setInitSpeed), 'list')
        self.writeList(setInitSpeed)

        setSpeed = [0x01, 0x06, 0x00, 0x33]
        setSpeed += Calculator.intToList(speed)
        setSpeed += Calculator.crc(bytes(setSpeed), 'list')
        self.writeList(setSpeed)

        setAcc = [0x01, 0x06, 0x00, 0x30]
        setAcc += Calculator.intToList(accTime)
        setAcc += Calculator.crc(bytes(setAcc), 'list')
        self.writeList(setAcc)

        setDec = [0x01, 0x06, 0x00, 0x30]
        setDec += Calculator.intToList(decTime)
        setDec += Calculator.crc(bytes(setDec), 'list')
        self.writeList(setDec)

    def setAbsolutePositionMode(self):
        self.writeList(setAbsolutePosition)

    def enable(self):
        self.writeList(setEnable)

    def run(self):
        self.writeList(setRun)

    def setPosition(self, pos):
        command = [0x01, 0x06, 0x00, 0x34]
        if pos >= 0:
            command += Calculator.intToList(pos)
        else:
            command += Calculator.intToList(2**16-abs(pos))
        command += Calculator.crc(bytes(command), 'list')
        self.writeList(command)

        command = [0x01, 0x06, 0x00, 0x35]
        if pos >= 0:
            command += Calculator.intToList(0)
        else:
            command += Calculator.intToList(2**16-1)
        command += Calculator.crc(bytes(command), 'list')
        self.writeList(command)

    def openLid(self):
        self.expectedStop()
        # 开盖负载极小（无密封圈阻力），速度可以很快，比如 -200
        self.setArgs(50, 50, -120)
        self.enable()
        self.setPosition(self.openPos)
        self.run()
        # 关键：开盖时间独立设定。
        time.sleep(2.8)#2.9
        self.stop()

    def closeLid(self):
        self.expectedStop()
        # 关盖负载极大（压缩密封圈），速度必须慢，扭矩才够，比如降到 60 或 80
        self.setArgs(50, 50, 105)
        self.enable()
        self.setPosition(self.closePos)
        self.run()
        # 关键：关盖时间独立设定
        time.sleep(3.3)#3.5
        self.stop()

    # def openLid(self):
    #     self.expectedStop()
    #     self.setArgs(50, 50, -130)
    #     self.enable()
    #     #self.setAbsolutePositionMode()
    #     self.setPosition(self.openPos)
    #     self.run()
    #     time.sleep(self.motionTime)
    #     self.stop()
    #
    # def closeLid(self):
    #     self.expectedStop()
    #     self.setArgs(50, 50, 130)
    #     self.enable()
    #     #self.setAbsolutePositionMode()
    #     self.setPosition(self.closePos)
    #     self.run()
    #     time.sleep(self.motionTime)
    #     self.stop()

    def stop(self):
        self.writeList(stop)

    def emergentStop(self):
        self.writeList(emergentStop)

    def expectedStop(self):
        self.writeList(expectedStop)

    def writeList(self, command):
        self.ser.write(bytes(command))
        #print("send    : ", Calculator.listToString(command))
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(self.sendingTime)
        time.sleep(0.1)
        feedback = self.ser.read(40)
        #print("receive : ", Calculator.listToString(list(feedback)))

    def close(self):
        self.ser.close()


if __name__ == '__main__':
    evacuationSpace = controller('COM15')
    try:
        evacuationSpace.openLid()
        evacuationSpace.closeLid()


        evacuationSpace.close()
    except Exception as e:
        evacuationSpace.close()
        raise e