"""Executer previews candidates and requests one plan from schedule."""
from .contracts import DecisionPreview, TaskSpec, TaskStatus
from .viewer import Viewer
from .algorithm import AlgorithmConfig
from . import algorithm
from .actor import Actor
import time
import math
from uuid import uuid4


class Executer:
    """Select preview-approved tasks through one generic search and accept them under a shared lock."""
    def __init__(self, viewer: Viewer, *, tasks=None, actor=None, config=None,
                 clock=time.monotonic, cooldown_s=0.1) -> None:
        """Initialize executer dependencies and internal state."""
        self.viewer = viewer
        if not math.isfinite(cooldown_s) or cooldown_s < 0:
            raise ValueError("Decision cooldown must be finite and nonnegative")
        self.tasks, self.actor = tasks, actor
        self.cooldown_s = cooldown_s
        self._cooldown_until = -math.inf
        self.config = config
        self.clock = clock

    @property
    def cooldown_remaining(self):
        """Return the remaining decision cooldown in seconds, clamped to zero."""
        return max(0.0, self._cooldown_until - self.clock())

    def accept(self, task: TaskSpec) -> str:
        """Publish RUNNING and occupied resources together, before hardware I/O."""
        with self.viewer.transaction():
            if self.cooldown_remaining:
                raise ValueError("Executer is cooling down")
            request_id = uuid4().hex
            self.actor.reserve_resources(request_id, task.resources)
            try:
                self.tasks.claim(task.task_id, request_id, task)
            except Exception:
                self.actor.release_resources(request_id)
                raise
            self._cooldown_until = self.clock() + self.cooldown_s
            return request_id

    def configure(self, config: AlgorithmConfig) -> None:
        """Set the algorithm configuration used for subsequent Executor decisions."""
        if any(r.status in (TaskStatus.PENDING, TaskStatus.RUNNING) for r in self.viewer.decision_snapshot()["tasks"]):
            raise ValueError("Cannot change algorithm while a task is active")
        self.config = config

    def propose(self, preview: DecisionPreview, prepare=None, *,
                model_builder=None, planning_capacities=None) -> TaskSpec | None:
        """Prepare and preview READY tasks, search once, and return the selected executable first task."""
        with self.viewer.transaction():
            return self._propose(preview, prepare, model_builder=model_builder,
                                 planning_capacities=planning_capacities)

    def _propose(self, preview, prepare, *, model_builder, planning_capacities):
        """Preview the first-step candidates, schedule once, return its first task."""
        if self.config is None:
            raise ValueError("Configure Executer's algorithm before proposing tasks")
        if self.cooldown_remaining:
            return None
        snapshot = self.viewer.decision_snapshot()
        ready = tuple(r for r in snapshot["tasks"] if r.status == TaskStatus.READY)
        candidates = []
        for record in ready:
            task = prepare(record.spec, snapshot) if prepare is not None else record.spec
            if task is not None and Actor.resources_fit(task, snapshot) and preview(task, snapshot):
                candidates.append(task)
        if not candidates:
            return None
        now = self.clock()
        records = snapshot["tasks"]
        completed = {r.spec.task_id: r.state_since if r.state_since is not None else now
                     for r in records if r.status == TaskStatus.SUCCEEDED}
        prepared = {task.task_id: task for task in candidates}
        remaining = [prepared.get(r.spec.task_id, r.spec) for r in records
                     if r.status in (TaskStatus.READY, TaskStatus.BLOCKED)]
        models = [model_builder(task, snapshot) if model_builder is not None else
                  algorithm.from_spec(task, require_duration=self.config.method in ("exact", "beam", "auto"))
                  for task in remaining]
        capacities = {name: r["capacity"] for name, r in snapshot["resources"].items()}
        available = {name: r["available"] for name, r in snapshot["resources"].items()}
        if planning_capacities is not None:
            capacities, available = planning_capacities(snapshot)
        plan = algorithm.schedule(models, capacities, self.config, now=now, completed=completed,
                                  horizon=self.config.lookahead_depth, initial_available=available,
                                  first_candidates=prepared.keys())
        return prepared[plan.commands[0].task_id] if plan.feasible and plan.commands else None
