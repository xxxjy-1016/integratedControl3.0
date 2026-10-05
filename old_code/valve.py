import serial
import time

from mypy.plugins.enums import enum_value_callback

from errors import TLE
from tools import Calculator
import threading
from dataStructures import *

class controller:
    def __init__(self, serName, bps=38400, timeout=10):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.sendingTime = 0.1

    def setPowerOn(self):
        command = [0x01, 0x06, 0x00, 0x00, 0x00, 0x01]
        command += Calculator.crc(bytes(command), 'list')
        self.writeList(command)

    def setPowerOff(self):
        command = [0x01, 0x06, 0x00, 0x00, 0x00, 0x00]
        command += Calculator.crc(bytes(command), 'list')
        self.writeList(command)

    def writeList(self, command):
        self.ser.write(bytes(command))
        #print("send    : ", Calculator.listToString(command))
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(self.sendingTime)
        feedback = self.ser.read(40)
        #print("receive : ", Calculator.listToString(list(feedback)))

    def close(self):
        self.ser.close()


if __name__ == '__main__':
    evacuationSpace = controller('COM13')
    try:
     evacuationSpace.setPowerOn()
       #time.sleep(10)
     #evacuationSpace.setPowerOff()
       #evacuationSpace.close()
    except Exception as e:
        evacuationSpace.close()