import serial
import time
from tools import Calculator
from errors import TLE

init_adp = '>02G9158'
init_dcm = '>01G6158'
secede = '>02Q5FD9'
query_adp = '>02g4959'    # Query execution status.
query_dcm = '>01dB819'

class controller:
    """Represent controller and its associated operations."""
    def __init__(self, serName, bps = 115200, timeout = 10):
        """Initialize controller dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout = 0)

    def wait_adp(self):
        """Wait adp."""
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_adp.encode('utf-8'))
        time.sleep(0.1)
        stTime = time.time()
        while True:
            feedback = self.ser.read(20).decode('ascii', errors = 'ignore')

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()

            #print("get "+ feedback.strip())
            
            if feedback.strip() == '>02g01722E': # Execution has completed.
                #print("done, exiting")
                return
                
            curTime = time.time()
            
            if curTime - stTime > self.timeout:
                raise TLE("mouth : ADP TLE")
            
            self.ser.write(query_adp.encode('utf-8'))
            time.sleep(0.1)

    def wait_dcm_position(self):
        """Wait dcm position."""
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(query_dcm.encode('utf-8'))
        time.sleep(0.1)
        stTime = time.time()
        while True:
            #print("query sent")
            feedback = self.ser.read(40).decode('ascii', errors = 'ignore')

            #print("in wait_tj_dcm, feedback = " + feedback)

            self.ser.reset_input_buffer()
            self.ser.reset_output_buffer()
            
            if feedback.strip() == '>01d0136DE':
                #print("done, exiting")
                return
                
            curTime = time.time()
            
            if curTime - stTime > self.timeout:
                raise TLE("mouth : DCM TLE")
            
            self.ser.write(query_dcm.encode('utf-8'))
            time.sleep(0.1)

    
    def init_adp(self):
        """Init adp."""
        self.ser.write(init_adp.encode('utf-8'))
        time.sleep(0.1)
        self.wait_adp()

    def init_dcm(self):
        """Init dcm."""
        self.ser.write(init_dcm.encode('utf-8'))
        time.sleep(0.1)
        self.wait_dcm_position()

    def init(self):
        """Init."""
        self.init_adp()
        self.init_dcm()

    def moveTo(self, idis):
        """Move to."""
        dis = int(idis / 100.0 * 150000)
        command = '>01D'
        list_dis = Calculator.intToList(dis, length = 4)
        for i in range(4):
            command += hex(list_dis[i])[2:].zfill(2)
        command += Calculator.crc(command.encode('utf-8'), 'str')
        self.ser.write(command.encode('utf-8'))
        time.sleep(0.1)
        self.wait_dcm_position()

    def secedeTip(self):
        """Secede tip."""
        self.ser.write(secede.encode('utf-8'))
        time.sleep(0.1)
        self.wait_adp()

    def suck(self, vol):
        """Suck."""
        command = '>02n'
        list_vol = Calculator.intToList(vol)
        command += str(hex(list_vol[0])[2:].zfill(2)) + str(hex(list_vol[1])[2:].zfill(2))
        command += Calculator.crc(command.encode('utf-8'), 'str')
        self.ser.write(command.encode('utf-8'))
        time.sleep(0.1)
        self.wait_adp()

        if self.query_adp() == 'not sucked':
            return 'not sucked'

        return 'sucked'

    def spit(self, vol):
        """Spit."""
        command = '>02p'
        list_vol = Calculator.intToList(vol)
        command += str(hex(list_vol[0])[2:].zfill(2)) + str(hex(list_vol[1])[2:].zfill(2))
        command += Calculator.crc(command.encode('utf-8'), 'str')
        self.ser.write(command.encode('utf-8'))
        time.sleep(0.1)
        self.wait_adp()

    def query_adp(self):
        """Query adp."""
        command = '>02d4819'
        self.ser.reset_input_buffer()
        self.ser.reset_output_buffer()
        self.ser.write(command.encode('utf-8'))
        time.sleep(0.1)
        feedback = self.ser.read(40).decode('ascii', errors = 'ignore')
        if feedback[4:6] == '09' or feedback[4:6] == '0A':
            return 'not sucked'

        return 'sucked'

    def close(self):
        """Close."""
        self.ser.close()

if __name__ == '__main__':
    try:
        mouth = controller("COM9")
        mouth.init()
        mouth.query_adp()
        mouth.suck(20)
        mouth.query_adp()
        #time.sleep(3)
        #time.sleep(3)
        #mouth.suck(50)
        #time.sleep(3)
        #mouth.spit(0)
        #time.sleep(3)
        #mouth.secedeTip()
        #mouth.spit(0)
        mouth.close()
    except Exception as e:
        mouth.close()
        raise