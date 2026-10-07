from enum import Enum


class SystemState(str, Enum):
    """Enumerate supported system state values."""
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
    """Enumerate supported device lifecycle values."""
    OFFLINE = "OFFLINE"
    READY = "READY"
    FAULT = "FAULT"
