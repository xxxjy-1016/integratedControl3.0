from dataclasses import dataclass
from threading import RLock

from integrated_control.domain.enums import SystemState


@dataclass(frozen=True)
class SystemSnapshot:
    """Store an immutable snapshot of system lifecycle and its diagnostic message."""
    state: SystemState
    message: str = ""
    error_code: str | None = None


class StateStore:
    """Store the current system lifecycle, message, and fault code."""
    def __init__(self) -> None:
        """Initialize state store dependencies and internal state."""
        self._lock = RLock()
        self._snapshot = SystemSnapshot(SystemState.BOOTING)

    def set(
        self,
        state: SystemState,
        message: str = "",
        error_code: str | None = None,
    ) -> SystemSnapshot:
        """Replace the stored system lifecycle, message, and optional error code."""
        with self._lock:
            self._snapshot = SystemSnapshot(state, message, error_code)
            return self._snapshot

    def get(self) -> SystemSnapshot:
        """Return the currently stored system snapshot."""
        with self._lock:
            return self._snapshot
