import serial
import time
from errors import TLE
from tools import Calculator
import threading
from dataStructures import *

class controller:
    def __init__(self, serName, bps = 9600, timeout = 10):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout = 0)
        
        self.spinThread = threading.Thread(target = self.blockSpin, args = (0, 2,))
        self.closeThread = threading.Thread(target = self.blockClose)
        self.processing = False
        self.sendingTime = 0.1

    def writeList(self, command):
        self.ser.write(bytes(command))
        time.sleep(self.sendingTime)

    def enable(self):
        command = [0x01, 0x06, 0x00, 0xB6, 0x00, 0x01, 0xA9, 0xEC]
        self.writeList(command)
        
    
    def setSpeed(self, speed):
        command = [0x01, 0x06, 0x00, 0x56]
        command += Calculator.intToList(speed)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.writeList(command)

    def setAcceleratingTime(self, acceleratingTime):
        command = [0x01, 0x06, 0x00, 0x93]
        command += Calculator.intToList(acceleratingTime)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.writeList(command)

    def setDeceleratingTime(self, deceleratingTime):
        command = [0x01, 0x06, 0x00, 0x94]
        command += Calculator.intToList(deceleratingTime)
        command += Calculator.crc(bytes(command), flag = 'list')
        self.writeList(command)

    def start(self, flag = False):
        command = [0x01, 0x06, 0x00, 0x66, 0x00, 0x01]
        if flag:
            command = [0x01, 0x06, 0x00, 0x66, 0x00, 0x02]
        command += Calculator.crc(bytes(command), flag = 'list')
        self.writeList(command)

        
    def stop(self):
        command = [0x01, 0x06, 0x00, 0x66, 0x00, 0x00, 0x69, 0xD5]
        self.writeList(command)

    def blockSpin(self, spinInfoList): #without thread
        while(self.processing == True):
            time.sleep(0.1)

        self.processing = True
        self.enable()

        for i in range(len(spinInfoList)):
            self.setSpeed(spinInfoList[i].speed)
            self.setAcceleratingTime(spinInfoList[i].acceleratingTime)
            self.setDeceleratingTime(spinInfoList[i].deceleratingTime)
            self.stop()
            self.start()
            time.sleep(spinInfoList[i].spinTime - self.sendingTime * 4)

        time.sleep(self.sendingTime * 3)
        self.stop()

        self.processing = False
    
    def spin(self, spinInfoList):
        self.spinThread = threading.Thread(target = self.blockSpin, args = (spinInfoList,))
        self.spinThread.start()
    
    def blockClose(self):
        if self.spinThread.is_alive() : self.spinThread.join()
        self.ser.close()

    def close(self):
        self.closeThread = threading.Thread(target = self.blockClose)
        self.closeThread.start()
        

if __name__ == '__main__':
    spinCoater = controller('COM10')
    try:
        info = [SpinInfo(5000, 1, 10, 10), SpinInfo(1000, 1, 10, 10)]
        spinCoater.spin(info)
        #spinCoater.spin(speed = 5000, spinTime = 6)
        spinCoater.close()
    except Exception as e:
        spinCoater.close()
        raise e