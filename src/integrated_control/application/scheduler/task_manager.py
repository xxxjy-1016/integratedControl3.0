"""Task ownership and transitions; hardware evidence is validated by Actor."""
from dataclasses import replace
from copy import deepcopy
from threading import RLock
from typing import Sequence
import math
import time

from .contracts import TaskRecord, TaskSpec, TaskStatus
from integrated_control.domain.results import ActionResult


class TaskManager:
    """Maintain task records, dependency readiness, request claims, and timeout transitions."""
    def __init__(self, *, lock=None, clock=time.monotonic) -> None:
        """Initialize task manager dependencies and internal state."""
        self._tasks: dict[str, TaskRecord] = {}
        self._lock = lock if lock is not None else RLock()
        self._clock = clock
        self._tolerances: dict[str, tuple[float, float]] = {}

    def configure_tolerance(self, kind: str, *, pending_s: float, running_s: float) -> None:
        """Set task-kind timeout tolerances for pending and running states."""
        if any(not math.isfinite(v) or v <= 0 for v in (pending_s, running_s)):
            raise ValueError("Task tolerance must be positive and finite")
        with self._lock:
            self._tolerances[kind] = (pending_s, running_s)

    def expire(self) -> tuple[str, ...]:
        """Only mark deadlines; do not stop hardware or release resources."""
        with self._lock:
            expired = []
            now = self._clock()
            for key, record in self._tasks.items():
                limits = self._tolerances.get(record.spec.kind)
                if limits is None or record.status not in (TaskStatus.PENDING, TaskStatus.RUNNING):
                    continue
                limit = limits[0 if record.status == TaskStatus.PENDING else 1]
                if record.state_since is not None and now - record.state_since >= limit:
                    self._tasks[key] = replace(record, status=TaskStatus.TIMED_OUT,
                        result=ActionResult(False, "TIMED_OUT", "TASK_TIMEOUT", key), state_since=now)
                    expired.append(key)
            return tuple(expired)

    def submit(self, specs: Sequence[TaskSpec]) -> None:
        """Register a task graph and derive initial BLOCKED or READY states from its dependencies."""
        with self._lock:
            incoming = {spec.task_id: spec for spec in specs}
            if len(incoming) != len(specs) or any(key in self._tasks for key in incoming):
                raise ValueError("Duplicate task id")
            all_ids = set(self._tasks) | set(incoming)
            for spec in specs:
                if not spec.task_id or not spec.kind:
                    raise ValueError("Task id and kind are required")
                if any(dep not in all_ids for dep in spec.dependencies):
                    raise ValueError("Unknown task dependency")
            visiting: set[str] = set()
            visited: set[str] = set()
            def visit(key: str) -> None:
                """Visit a dependency while collecting or validating the syntax tree."""
                if key in visiting:
                    raise ValueError("Cyclic task dependencies")
                if key in visited or key not in incoming:
                    return
                visiting.add(key)
                for dep in incoming[key].dependencies:
                    visit(dep)
                visiting.remove(key)
                visited.add(key)
            for key in incoming:
                visit(key)
            for spec in specs:
                # Copy caller-owned dictionaries before storing task definitions.
                owned = deepcopy(spec)
                self._tasks[spec.task_id] = TaskRecord(owned, TaskStatus.BLOCKED)
            self._unlock_ready()

    def snapshot(self) -> tuple[TaskRecord, ...]:
        """Return the registered task records in registration order under the shared lock."""
        with self._lock:
            return deepcopy(tuple(self._tasks.values()))

    def claim(self, task_id: str, request_id: str, decision: TaskSpec | None = None) -> TaskRecord:
        """Claim a READY task with a request identifier and register its prepared specification as RUNNING."""
        with self._lock:
            if not request_id:
                raise ValueError("Request id is required")
            record = self._tasks[task_id]
            if record.request_id == request_id:
                return deepcopy(record)
            if record.status != TaskStatus.READY:
                raise ValueError("Only READY tasks can be claimed")
            if any(r.request_id == request_id for r in self._tasks.values()):
                raise ValueError("Request id belongs to another task")
            if decision is not None:
                if (decision.task_id, decision.kind, decision.dependencies) != (
                        record.spec.task_id, record.spec.kind, record.spec.dependencies):
                    raise ValueError("Decision changed task identity or dependencies")
                record = replace(record, spec=deepcopy(decision))
            record = replace(record, status=TaskStatus.RUNNING, request_id=request_id, state_since=self._clock())
            self._tasks[task_id] = record
            return deepcopy(record)

    def actor_update(self, task_id: str, request_id: str, status: TaskStatus,
                     result: ActionResult | None = None) -> None:
        """Consume Actor-validated results; do not parse device evidence here."""
        allowed = {
            TaskStatus.PENDING: {TaskStatus.RUNNING, TaskStatus.FAILED, TaskStatus.UNKNOWN, TaskStatus.TIMED_OUT},
            TaskStatus.RUNNING: {TaskStatus.SUCCEEDED, TaskStatus.FAILED, TaskStatus.UNKNOWN, TaskStatus.TIMED_OUT},
        }
        with self._lock:
            record = self._tasks[task_id]
            if record.request_id != request_id:
                raise ValueError("Stale or unrelated execution result")
            if record.status == status:
                return
            if status not in allowed.get(record.status, set()):
                raise ValueError("Invalid task transition; late results require reconciliation")
            self._tasks[task_id] = replace(record, status=status, result=deepcopy(result), state_since=self._clock())
            self._unlock_ready()

    def _unlock_ready(self) -> None:
        """Change BLOCKED tasks to READY when all their dependencies have succeeded."""
        for key, record in self._tasks.items():
            if record.status == TaskStatus.BLOCKED and all(
                self._tasks[dep].status == TaskStatus.SUCCEEDED for dep in record.spec.dependencies
            ):
                self._tasks[key] = replace(record, status=TaskStatus.READY)
