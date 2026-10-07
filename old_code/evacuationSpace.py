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
    """Represent controller and its associated operations."""
    def __init__(self, serName, bps=9600, timeout=10):
        """Initialize controller dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout=0)
        self.openPos = 0
        self.closePos = 250
        self.motionTime = 2.5# The previous value was 2.1.
        self.sendingTime = 0.1

    def setArgs(self, accTime, decTime, speed, initSpeed = 10):
        """Set args."""
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
        """Set absolute position mode."""
        self.writeList(setAbsolutePosition)

    def enable(self):
        """Enable."""
        self.writeList(setEnable)

    def run(self):
        """Run the evacuation space operation sequence."""
        self.writeList(setRun)

    def setPosition(self, pos):
        """Set position."""
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
        """Open lid."""
        self.expectedStop()
        # Opening has little seal resistance and can use a fast speed, such as -200.
        self.setArgs(50, 50, -120)
        self.enable()
        self.setPosition(self.openPos)
        self.run()
        # Configure the lid opening duration independently.
        time.sleep(2.8)#2.9
        self.stop()

    def closeLid(self):
        """Close lid."""
        self.expectedStop()
        # Closing compresses the seal; a lower speed such as 60 or 80 provides sufficient torque.
        self.setArgs(50, 50, 105)
        self.enable()
        self.setPosition(self.closePos)
        self.run()
        # Configure the lid closing duration independently.
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
        """Stop."""
        self.writeList(stop)

    def emergentStop(self):
        """Emergent stop."""
        self.writeList(emergentStop)

    def expectedStop(self):
        """Expected stop."""
        self.writeList(expectedStop)

    def writeList(self, command):
        """Write list."""
        self.ser.write(bytes(command))
        #print("send    : ", Calculator.listToString(command))
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        time.sleep(self.sendingTime)
        time.sleep(0.1)
        feedback = self.ser.read(40)
        #print("receive : ", Calculator.listToString(list(feedback)))

    def close(self):
        """Close."""
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