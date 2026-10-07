"""Shared task and extension contracts; no workflow or device dependencies."""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Mapping, Protocol, Sequence

from integrated_control.domain.results import ActionResult


class TaskStatus(str, Enum):
    """Enumerate dependency, execution, completion, and uncertainty states for a task."""
    BLOCKED = "BLOCKED"
    READY = "READY"
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    TIMED_OUT = "TIMED_OUT"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class TaskSpec:
    """Describe a workflow task, its dependencies, parameters, and resource requirements."""
    task_id: str
    kind: str
    parameters: Mapping[str, Any] = field(default_factory=dict)
    dependencies: tuple[str, ...] = ()
    resources: Mapping[str, float] = field(default_factory=dict)
    retain_resources: tuple[str, ...] = ()


@dataclass(frozen=True)
class TaskRecord:
    """Store a task specification with its current status, request identity, result, and transition time."""
    spec: TaskSpec
    status: TaskStatus
    request_id: str | None = None
    result: ActionResult | None = None
    state_since: float | None = None


@dataclass(frozen=True)
class TimeLink:
    """Constrain the delay from a predecessor finish to this task start."""
    predecessor: str
    min_delay_s: float = 0.0
    max_delay_s: float | None = None


@dataclass(frozen=True)
class SchedulingTask:
    """Describe a generic serial scheduling task with time windows and resource retention/return rules."""
    task_id: str
    duration_s: float
    dependencies: tuple[str, ...] = ()
    release_at: float = 0.0
    deadline_at: float | None = None  # Latest FINISH.
    resources: Mapping[str, float] = field(default_factory=dict)
    retain_resources: tuple[str, ...] = ()
    resource_returns: Mapping[str, float] = field(default_factory=dict)
    time_links: tuple[TimeLink, ...] = ()
    priority: float = 0.0
    symmetry_group: str | None = None  # Caller explicitly declares equivalence.


@dataclass(frozen=True)
class ScheduledTask:
    """Store one planned task identifier and its start and finish times."""
    task_id: str
    start: float
    end: float


@dataclass(frozen=True)
class TaskPlan:
    """Return scheduled commands with feasibility, optimality, timeout, and error information."""
    commands: tuple[ScheduledTask, ...]
    feasible: bool
    proven_optimal: bool
    method: str
    makespan: float
    timed_out: bool = False
    errors: tuple[str, ...] = ()


class ExperimentCompiler(Protocol):
    """Define the callable contract for converting experiment parameters to tasks."""
    def __call__(self, parameters: Mapping[str, Any]) -> Sequence[TaskSpec]: """Compile experiment parameters into a sequence of task specifications."""; ...


class TaskHandler(Protocol):
    """Define the callable contract for executing a task and returning an ActionResult."""
    def __call__(self, task: TaskSpec) -> ActionResult: """Execute the task and return its action result."""; ...


class DecisionPreview(Protocol):
    """Define the callable contract for checking a candidate against a decision snapshot."""
    def __call__(self, task: TaskSpec, snapshot: Mapping[str, Any]) -> bool: """Return whether the task passes the current decision snapshot checks."""; ...


ResultCheck = Callable[[TaskSpec, ActionResult], ActionResult]
