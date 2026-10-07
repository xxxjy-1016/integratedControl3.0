class coordinate:
    """Represent coordinate and its associated operations."""
    def __init__(self, x, y, zh, zm):
        """Initialize coordinate dependencies and internal state."""
        self.x = x
        self.y = y
        self.zh = zh
        self.zm = zm

    def copy(self):
        """Copy."""
        return coordinate(self.x, self.y, self.zh, self.zm)


class SpinInfo:
    """Represent spin info and its associated operations."""
    def __init__(self, speed, spinTime, acceleratingTime = 2, deceleratingTime = -1, flag = 'new'):
        """Initialize spin info dependencies and internal state."""
        if deceleratingTime == -1:
            deceleratingTime = acceleratingTime

        self.speed = speed
        if flag == 'old' : self.spinTime = spinTime + acceleratingTime
        else: self.spinTime = spinTime
        self.acceleratingTime = int(acceleratingTime * 1000.0)
        self.deceleratingTime = int(deceleratingTime * 1000.0)

    def toString(self):
        """To string."""
        string = "SpinInfo(speed="
        string += str(self.speed)
        string += ", spinTime="
        string += str(self.spinTime)
        string += ", acceleratingTime="
        string += str(self.acceleratingTime)
        string += ", deceleratingTime="
        string += str(self.deceleratingTime)
        string += ")"
        return string

    def getAcceleratngTimeInMs(self):
        """Get acceleratng time in ms."""
        return self.acceleratingTime

    def getDeceleratngTimeInMs(self):
        """Get deceleratng time in ms."""
        return self.deceleratingTime

    def getAcceleratingTimeInSecs(self):
        """Get accelerating time in secs."""
        return float(self.acceleratingTime / 1000.0)

    def getDeceleratingTimeInSecs(self):
        """Get decelerating time in secs."""
        return float(self.deceleratingTime / 1000.0)

if __name__ == "__main__":
    test = SpinInfo(100, 2, 2, 2)
    print("Acceleration time in ms: %d" % (test.getAcceleratngTimeInMs()))
    print("Deceleration time in ms: %d" % (test.getDeceleratngTimeInMs()))
    print("Acceleration time in secs: %f" % (test.getAcceleratingTimeInSecs()))
    print("Deceleration time in secs: %f" % (test.getDeceleratingTimeInSecs()))