import serial
import time
import binascii,re
from errors import TLE
from tools import Calculator
from PIL import Image, ImageDraw, ImageFont

order_snap = [0x56, 0x00, 0x36, 0x01, 0x00]
order_refresh = [0x56, 0x00, 0x26, 0x00]
query_picLength = [0x56, 0x00, 0x34, 0x01, 0x00]
order_flush = [0x56, 0x00, 0x36, 0x01, 0x03]

class camera:
    def __init__(self, serName, bps=115200, timeout=10):
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.sendingTime = 0.2

    def writeList(self, command, len = 40):
        print("write : ", Calculator.listToString(command))
        self.ser.write(bytes(command))
        time.sleep(self.sendingTime)

        if len > 4000:
            response = self.readLong()
        else:
            response = self.readList(len)

        print("get   : ", response)
        return response

    def readList(self, len = 40):
        self.ser.flush()
        time.sleep(self.sendingTime)
        feedback = self.ser.read(len)
        return list(feedback)

    def readLong(self, flag1 = bytes([0xFF]), flag2 = bytes([0xD9])):
        result = []
        lastByte = 0
        while 1 :
            curByte = self.ser.read(1)
            result += list(curByte)
            if curByte == flag2 and lastByte == flag1:
                break

            lastByte = curByte

        return result

    def snap(self):
        #self.writeList(order_refresh)
        self.writeList(order_snap)
        lengthFeedback = self.writeList(query_picLength)
        print("the length : ", Calculator.listToString(lengthFeedback))
        lengthNumber = lengthFeedback[7]*256 + lengthFeedback[8]
        snapCommand = [0x56, 0x00, 0x32, 0x0C, 0x00, 0x0A ,0x00, 0x00, 0x00, 0x00, 0x00, 0x00, lengthFeedback[7], lengthFeedback[8], 0x00, 0xFF]
        pic = self.writeList(snapCommand, 100000)
        #print(len(pic))
        #print(Calculator.listToString(pic[5:]))
        self.writeList(order_flush)

        with open('spinCoater.jpg', 'wb') as f:
            f.write(bytes(pic[5:]))

    def refresh(self):
        self.writeList(order_refresh)

    def cut_image(self, path, savePath):
        img = Image.open(path)
        w, h = img.size
        cut = (291, 316, 343, 353)
        cropped = img.crop(cut)
        cropped.save(savePath, quality=95, subsampling=0)

    def close(self):
        self.ser.close()

if __name__ == "__main__":
    test = camera(serName="COM13", bps=115200)
    #test.refresh()
    #time.sleep(3)
    #print("after refresh")
    test.snap()
    test.cut_image("spinCoater.jpg", r'D:\anaconda\python_files\python_test\integratedControl2.0\dataset1\test1.jpg')
    print(1)
    test.snap()
    time.sleep(10)
    test.cut_image("spinCoater.jpg", r'D:\anaconda\python_files\python_test\integratedControl2.0\dataset1\test2.jpg')
    print(2)
    time.sleep(10)
    test.snap()
    test.cut_image("spinCoater.jpg", r'D:\anaconda\python_files\python_test\integratedControl2.0\dataset1\test3.jpg')
    print(3)
    time.sleep(10)
    test.snap()
    test.cut_image("spinCoater.jpg", r'D:\anaconda\python_files\python_test\integratedControl2.0\dataset1\test4.jpg')
    print(4)
    time.sleep(10)
    test.snap()
    test.cut_image("spinCoater.jpg", r'D:\anaconda\python_files\python_test\integratedControl2.0\dataset1\test5.jpg')
    print(5)
    test.close()