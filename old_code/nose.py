import serial
import time
from tools import Calculator
from errors import TLE

class controller:
    """Represent controller and its associated operations."""
    def __init__(self, serName, bps = 115200, timeout = 10):
        """Initialize controller dependencies and internal state."""
        self.serName = serName
        self.bps = bps
        self.timeout = timeout
        self.ser = serial.Serial(self.serName, self.bps, timeout = 0)

