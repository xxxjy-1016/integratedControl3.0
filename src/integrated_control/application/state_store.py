from dataclasses import dataclass
from threading import RLock

from integrated_control.domain.enums import SystemState


@dataclass(frozen=True)
class SystemSnapshot:
    state: SystemState
    message: str = ""
    error_code: str | None = None


class StateStore:
    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot = SystemSnapshot(SystemState.BOOTING)

    def set(
        self,
        state: SystemState,
        message: str = "",
        error_code: str | None = None,
    ) -> SystemSnapshot:
        with self._lock:
            self._snapshot = SystemSnapshot(state, message, error_code)
            return self._snapshot

    def get(self) -> SystemSnapshot:
        with self._lock:
            return self._snapshot
