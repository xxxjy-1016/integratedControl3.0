from enum import Enum


class SystemState(str, Enum):
    BOOTING = "BOOTING"
    INITIALIZING = "INITIALIZING"
    HOMING = "HOMING"
    READY = "READY"
    RUNNING = "RUNNING"
    PAUSED = "PAUSED"
    FAULT = "FAULT"
    ESTOP = "ESTOP"
    STOPPED = "STOPPED"


class DeviceLifecycle(str, Enum):
    OFFLINE = "OFFLINE"
    READY = "READY"
    FAULT = "FAULT"
