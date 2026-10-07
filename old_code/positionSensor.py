from tools import Calculator
from tools import ModbusCommunicator

class sensor:
    """Represent sensor and its associated operations."""
    def __init__(self, serName, bps = 9600, timeout = 10, sendingTime = 0.2):
        """Initialize sensor dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.sendingTime = sendingTime
        self.communicator = ModbusCommunicator(self.serName, self.bps, self.timeout, self.sendingTime)

    def setRange(self, id = 0):
        """Set range."""
        response = self.communicator.writeByBytes(200 + id, 0x000B) # 500mV
        return response

    def read(self, id = 0):
        """Read."""
        response = self.communicator.queryByBytes(0 + id, 1, 1, 'register')
        #print(response)
        D = response[0]
        voltage = D / 65535 * 1000 - 500
        #print(voltage)
        return voltage

    def detection_x(self):
        """Detection x."""
        self.setRange(0)
        voltage = self.read(0)
        if voltage > 0:
            return True
        else:
            return False

    def detection_y(self):
        """Detection y."""
        self.setRange(1)
        voltage = self.read(1)
        if voltage > 0:
            return True
        else:
            return False

    def located_x(self):
        """Located x."""
        voltage_x = False
        while not voltage_x:
            voltage_x = self.detection_x()
            if voltage_x:
                print(voltage_x)
                break
        return voltage_x

    def located_y(self):
        """Located y."""
        voltage_y = False
        while not voltage_y:
            voltage_y = self.detection_y()
            if voltage_y:
                print(voltage_y)
                break
        return voltage_y

    def close(self):
        """Close."""
        self.communicator.close()

if __name__ == '__main__':
    try:
        s = sensor('COM10')
        s.located_y()
        s.close()
    except Exception as e:
        s.close()
        raise e
#01 03 9C 41 00 01 FA 4E