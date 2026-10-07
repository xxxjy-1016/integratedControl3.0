"""Actor accepts error-free partial feedback and applies task-specific checks."""
from .contracts import ResultCheck, TaskHandler, TaskSpec, TaskStatus
from integrated_control.domain.results import ActionResult
from integrated_control.domain.models import DeviceState
from .feedback import FeedbackPolicy, FeedbackTolerance
from .viewer import Viewer
from copy import deepcopy
import math


class Actor:
    """Reserve resources, execute accepted handlers, and publish device feedback and execution results."""
    def __init__(self, viewer: Viewer | None = None, *, tasks=None) -> None:
        """Initialize actor dependencies and internal state."""
        self._handlers = {}
        self._tasks = tasks
        self._started = set()
        self._viewer = viewer
        self._feedback: dict[str, FeedbackTolerance] = {}
        self.execution_records = {}

    def configure_resources(self, capacities) -> None:
        """Initialize resource capacities and availability, rejecting resets while resources are allocated."""
        if self._viewer is None:
            raise ValueError("Resource allocation requires Viewer")
        with self._viewer.transaction():
            existing = self._viewer.snapshot()["resources"]
            if any(r["allocations"] for r in existing.values()):
                raise ValueError("Cannot reset occupied resources")
            if any(not math.isfinite(v) or v < 0 for v in capacities.values()):
                raise ValueError("Resource capacities must be finite and nonnegative")
            self._viewer.publish_confirmed("resources", {
                name: {"capacity": amount, "available": amount, "allocations": {}}
                for name, amount in capacities.items()})

    @staticmethod
    def resources_fit(task, snapshot) -> bool:
        """Check whether the snapshot has enough available resources for the task."""
        return all(name in task.resources for name in task.retain_resources) and all(math.isfinite(amount) and amount >= 0 and
            name in snapshot["resources"] and amount <= snapshot["resources"][name]["available"]
            for name, amount in task.resources.items())

    def reserve_resources(self, owner, resources) -> None:
        """Reserve the task resource quantities and associate them with a request identifier."""
        with self._viewer.transaction():
            state = self._viewer.snapshot()["resources"]
            for name, amount in resources.items():
                resource = state[name]
                if owner in resource["allocations"] or amount > resource["available"]:
                    raise ValueError("Resource reservation conflict")
            for name, amount in resources.items():
                state[name]["available"] -= amount
                state[name]["allocations"][owner] = amount
            self._viewer.publish_confirmed("resources", state)

    def release_resources(self, owner, *, except_names=(), only_names=None) -> None:
        """Release owned allocations, optionally limiting which resource names are returned."""
        with self._viewer.transaction():
            state = self._viewer.snapshot()["resources"]
            for name, resource in state.items():
                if name in except_names or (only_names is not None and name not in only_names):
                    continue
                resource["available"] += resource["allocations"].pop(owner, 0)
            self._viewer.publish_confirmed("resources", state)

    def configure_feedback(self, device_id: str, policy: FeedbackPolicy) -> None:
        """Configure per-device grace before its first observation."""
        if device_id in self._feedback:
            raise ValueError("Feedback monitor already configured")
        self._feedback[device_id] = FeedbackTolerance(policy)

    def observe_device(self, state: DeviceState) -> DeviceState:
        """Apply feedback tolerance to a device observation and publish the resulting state."""
        monitor = self._feedback.setdefault(state.device_id, FeedbackTolerance())
        return self._publish(monitor.observe(state))

    def communication_failed(self, device_id: str, message: str) -> DeviceState:
        """Record a communication gap and return cached or invalid state according to feedback tolerance."""
        monitor = self._feedback.setdefault(device_id, FeedbackTolerance())
        return self._publish(monitor.communication_failed(device_id, message))

    def _publish(self, state: DeviceState) -> DeviceState:
        """Publish the filtered device state to Viewer and return it."""
        if self._viewer is not None:
            self._viewer.publish_confirmed("devices", {state.device_id: state})
        return state

    def register(self, kind: str, handler: TaskHandler, *,
                 confirm: ResultCheck | None = None,
                 replace_existing: bool = False) -> None:
        """Optional task-specific checks; missing optional evidence is tolerated.

        Handler integration must also check interlocks before internal actions,
        publish checkpoints through Viewer, and retain uncertain resource claims.
        Camera.capture/locate can be used by these same validators."""
        if kind in self._handlers and not replace_existing:
            raise ValueError("Task handler already registered")
        self._handlers[kind] = (handler, confirm)

    def execute_accepted(self, task: TaskSpec, request_id: str) -> ActionResult:
        """Execute once, report outcome; do not re-run scheduling/preflight checks."""
        with self._viewer.transaction():
            self._tasks.expire()
            record = next(r for r in self._tasks.snapshot() if r.spec.task_id == task.task_id)
            if record.request_id != request_id or request_id in self._started:
                raise ValueError("Stale or already executed request")
            if record.status == TaskStatus.TIMED_OUT:
                return record.result
            if record.status != TaskStatus.RUNNING:
                raise ValueError("Task has not been accepted")
            self._started.add(request_id)
        result = self.execute(record.spec)
        with self._viewer.transaction():
            self._tasks.expire()
            record = next(r for r in self._tasks.snapshot() if r.spec.task_id == task.task_id)
            if record.status == TaskStatus.TIMED_OUT:
                return record.result
            status = (TaskStatus.SUCCEEDED if result.success else
                      TaskStatus.UNKNOWN if result.status == "UNKNOWN" else TaskStatus.FAILED)
            self._tasks.actor_update(task.task_id, request_id, status, result)
            if result.success:
                self.release_resources(request_id, except_names=task.retain_resources)
        return result

    def execute(self, task: TaskSpec) -> ActionResult:
        """Invoke the registered task handler and optional result validator, retaining uncertainty on exceptions."""
        if task.kind not in self._handlers:
            return ActionResult.failed("HANDLER_NOT_REGISTERED", task.kind)
        handler, confirm = self._handlers[task.kind]
        self.execution_records[task.task_id] = {
            "before": self._viewer.snapshot() if self._viewer is not None else {},
            "expected": deepcopy(dict(task.parameters)), "confirmed": None}
        try:
            result = handler(task)
            # The validator owns partial-failure/unknown interpretation too.
            # Default trusts the handler's result, never changes a failure into
            # success merely because optional measurements are absent.
            result = confirm(task, result) if confirm is not None else result
            self.execution_records[task.task_id]["confirmed"] = (
                self._viewer.snapshot() if self._viewer is not None else {})
            return result
        except Exception as exc:
            # A raised error does not prove that no physical action occurred.
            return ActionResult(False, "UNKNOWN", "EXECUTION_UNCERTAIN", str(exc))
