class heaterController:
    """Represent heater controller and its associated operations."""
    def __init__(self, name, num = 4):
        """Initialize heater controller dependencies and internal state."""
        self.name = name
        self.num = num
        self.list = [0, 0, 0, 0, 0, 0, 0, 0, 0]

    def Set(self, InitialList):
        """Set."""
        self.list = InitialList

    def QueryGlassPosition(self, id):
        """Query glass position."""
        for i in range(self.num):
            curPosition = i + 1;
            if(self.list[curPosition] == id):
                return curPosition

        return 0

    def RemoveGlass(self, id):
        """Remove glass."""
        aimPosition = self.QueryGlassPosition(id)
        if aimPosition == 0:
            print("Error ! Heater" + str(id) + "not found !")
            return 0

        self.list[aimPosition] = 0
        return aimPosition

    def QueryFreePosition(self, id):
        """Query free position."""
        for i in range(self.num):
            curPosition = i + 1;
            if(self.list[curPosition] == 0):
                return curPosition

        return 0

    def AssignGlass(self, id):
        """Assign glass."""
        aimPosition = self.QueryFreePosition(id)
        if aimPosition == 0:
            print("Error ! No free position !")
            return 0

        self.list[aimPosition] = id
        return aimPosition


if __name__ == '__main__':
    hm = heaterController("heater")
    print(hm.QueryFreePosition(1))
    print(hm.AssignGlass(1))
    print(hm.QueryFreePosition(2))
    print(hm.AssignGlass(2))
    print(hm.RemoveGlass(1))
    print(hm.QueryFreePosition(3))
    print(hm.AssignGlass(3))
    print(hm.QueryFreePosition(4))
    print(hm.AssignGlass(4))
    print(hm.QueryFreePosition(5))
    print(hm.AssignGlass(5))
    print(hm.QueryGlassPosition(3))
    print(hm.QueryGlassPosition(5))