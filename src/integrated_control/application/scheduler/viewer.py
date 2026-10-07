"""Read-only task/substance snapshots; future hardware and camera feeds meet here."""
from copy import deepcopy
from threading import RLock
from typing import Any, Mapping

from .contracts import TaskRecord, TaskStatus
from .task_manager import TaskManager


class Viewer:
    """Expose synchronized snapshots of tasks, resources, samples, and device states."""
    def __init__(self, tasks: TaskManager, *, lock=None) -> None:
        """Initialize viewer dependencies and internal state."""
        self._tasks = tasks
        self._state: dict[str, Any] = {"resources": {}, "samples": {}, "devices": {}}
        self._lock = lock if lock is not None else RLock()

    def decision_snapshot(self) -> dict[str, Any]:
        """Factory uses one lock for task states and resource occupancy."""
        with self._lock:
            snapshot = deepcopy(self._state)
            snapshot["tasks"] = self._tasks.snapshot()
            return snapshot

    def ready(self) -> tuple[TaskRecord, ...]:
        """Return task records whose dependency state is READY."""
        return tuple(r for r in self._tasks.snapshot() if r.status == TaskStatus.READY)

    def transaction(self):
        """Return the shared lock context used to synchronize View and task updates."""
        return self._lock

    def snapshot(self) -> dict[str, Any]:
        """Return a detached snapshot of resource, sample, and device Views under the shared lock."""
        with self._lock:
            return deepcopy(self._state)

    def publish_confirmed(self, category: str, changes: Mapping[str, Any]) -> None:
        """Actor's publication entry; readers receive independent copies."""
        with self._lock:
            if category not in self._state:
                raise ValueError("Unknown View category")
            self._state[category].update(deepcopy(dict(changes)))
