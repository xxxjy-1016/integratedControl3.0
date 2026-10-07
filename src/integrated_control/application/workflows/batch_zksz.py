# -*- coding: utf-8 -*-
"""Validated batch parameters and online glass experiment orchestration."""

from __future__ import annotations

import time
import math
from dataclasses import dataclass, replace
from typing import Any, Callable, Mapping

from integrated_control.application.scheduler import algorithm
from integrated_control.bootstrap import ApplicationContext
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
import json
from pathlib import Path
from uuid import uuid4
from integrated_control.application.scheduler import build_scheduler
from integrated_control.application.scheduler.contracts import TaskStatus
from integrated_control.application.scheduler.decision_preview import FifoPreview, OnlineTiming
from integrated_control.domain.results import ActionResult
from .zksz import ZkszWorkflow



@dataclass(frozen=True)
class BatchParams:
    """Store and validate batch process parameters.

    When counts are None, resolve num_glass from glass_platform.slots and num_heater from stations.heater in coordinates.yaml."""

    time_step1: float = 100.0  # Estimated duration of step1: preparation and heater loading, in seconds.
    time_step2: float = 20.0  # Estimated duration of step2: heater pickup and tray return, in seconds.
    heat_time_min: float = 1200.0  # Minimum residence time on the heater, in seconds.
    heat_time_max: float = 1210.0  # Maximum residence time on the heater, in seconds.
    num_heater: int | None = None  # Heater count; None derives it from configured coordinates.
    num_glass: int | None = None  # Glass count; None derives it from configured tray slots.
    method: str = "auto"
    beam_width: int = 800
    time_limit: float = 30.0

    def __post_init__(self) -> None:
        """Validate and normalize the initialized batch params fields."""
        for name in ("time_step1", "time_step2", "heat_time_min", "heat_time_max"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{name} 必须为有限数值")
        if self.time_step1 <= 0 or self.time_step2 <= 0:
            raise ValueError("time_step1 / time_step2 必须为正")
        if self.heat_time_min < 0 or self.heat_time_max < self.heat_time_min:
            raise ValueError("加热时间必须满足 0 <= heat_time_min <= heat_time_max")
        for name, minimum in (("num_glass", 0), ("num_heater", 1)):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value < minimum):
                raise ValueError(f"{name} 必须为 >= {minimum} 的整数或 None")
        algorithm.AlgorithmConfig(self.method, beam_width=self.beam_width, time_limit_s=self.time_limit)

    @property
    def slack(self) -> float:
        """Return the difference between the maximum and minimum heating residence times."""
        return self.heat_time_max - self.heat_time_min

    def to_dict(self) -> dict[str, Any]:
        """Return process parameters without mixing in algorithm settings."""
        return {name: getattr(self, name) for name in (
            "time_step1", "time_step2", "heat_time_min", "heat_time_max",
            "num_heater", "num_glass")}

    def resolve(self, coordinates: Mapping[str, Any]) -> BatchParams:
        """Derive omitted counts from coordinates and revalidate the resulting BatchParams."""
        return replace(self,
            num_glass=self.num_glass if self.num_glass is not None else
                len(coordinates.get("glass_platform", {}).get("slots", [])),
            num_heater=self.num_heater if self.num_heater is not None else
                len(coordinates.get("stations", {}).get("heater", [])))


def run_batch_zksz(
    application: ApplicationContext,
    *,
    batch: BatchParams | None = None,
    mode: str = "online",
    log_path: str | None = None,
    sleep: Callable[[float], None] | None = None,
    online_timing=None,
    algorithm_config=None,
    clock: Callable[[], float] = time.monotonic,
    visual_check=None,
):
    """Run an online batch using the same scheduling loop for simulated and native devices."""
    if mode != "online":
        raise ValueError("Batch execution supports online only; use diagnostics_cli dry/gantt for planning")
    batch = batch or BatchParams()
    params = batch.resolve(application.coordinates)
    if online_timing is None:
        raise ValueError("Online mode requires explicit duration bounds and checkpoint offsets")
    if application.scheduler is None:
        raise ValueError("Application scheduler is required for online mode")
    if algorithm_config is not None:
        application.scheduler.executer.configure(algorithm_config)
    return _run_experiment(application, params, online_timing, sleep=sleep or time.sleep,
                           clock=clock, log_path=log_path, visual_check=visual_check)


@dataclass(frozen=True)
class OnlineRunReport:
    """Summarize online batch completion, task records, elapsed time, and errors."""
    success: bool
    records: tuple
    makespan: float
    errors: tuple[str, ...] = ()

    @property
    def feasible(self):
        """Check whether the candidate order satisfies the independent scheduling constraints."""
        return self.success


def _run_experiment(application, params, timing: OnlineTiming, *, sleep=time.sleep,
                    clock=time.monotonic, log_path=None, visual_check=None,
                    pending_tolerance_s=3.0, running_tolerance_s=3.0):
    """Physical checkpoints use command completion; optional camera may refine them.

    Duration bounds and offsets must match the bench. Timeout marks a task but
    does not assert that hardware stopped; wait for the driver to return, retain
    claims and forbid further dispatch. Existing driver timeouts remain active."""
    if application.controller.snapshot.state.value != "READY":
        raise ValueError("Start the application before online execution")
    if (params.heat_time_min, params.heat_time_max) != (timing.heat_min_s, timing.heat_max_s):
        raise ValueError("Batch heating window and online timing window must match")
    if params.num_glass > len(application.coordinates.get("glass_platform", {}).get("slots", [])):
        raise ValueError("Not enough configured glass slots")
    if params.num_heater > len(application.coordinates.get("stations", {}).get("heater", [])):
        raise ValueError("Not enough configured heater slots")
    log_file = Path(log_path) if log_path is not None else None
    if log_file is not None:
        # Create and validate the destination before any task can be claimed.
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with log_file.open("a", encoding="utf-8"):
            pass
    system = application.scheduler or build_scheduler(clock=clock)
    if any(r.status in (TaskStatus.PENDING, TaskStatus.RUNNING) for r in system.task_manager.snapshot()):
        raise ValueError("Another experiment is active")
    if running_tolerance_s < 0:
        raise ValueError("Running tolerance must be nonnegative")
    preview = FifoPreview(timing, clock=clock)
    actor, viewer = system.actor, system.viewer
    actor.configure_resources({"arm": 1, **{f"heater:{m}": 1 for m in range(1, params.num_heater + 1)}})
    for kind, bound in (("step1", timing.step1_bound_s), ("step2", timing.step2_bound_s)):
        system.task_manager.configure_tolerance(kind, pending_s=pending_tolerance_s,
                                                running_s=bound + running_tolerance_s)
    # Device get_state() may be cached: publish without inventing a timestamp.
    viewer.publish_confirmed("devices", application.controller.devices.states())
    experiment_id = uuid4().hex
    specs = system.experiment_manager.submit("zksz", {
        "experiment_id": experiment_id, "glass_ids": range(params.num_glass)})
    ids = {t.task_id for t in specs}
    viewer.publish_confirmed("samples", {str(n): {"n": n, "position": "tray"}
                                          for n in range(params.num_glass)})

    def log(event, **values):
        """Append a timestamped runtime event to the optional batch log."""
        if log_file is not None:
            with log_file.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps({"event": event, "at": clock(), **values}, ensure_ascii=False) + "\n")

    def checkpoint(event, n, m, at):
        """Publish actual glass placement/pickup facts and release heater occupancy on departure."""
        sample = viewer.snapshot()["samples"][str(n)]
        if event == "placed":
            record = next(r for r in system.task_manager.snapshot()
                          if r.spec.task_id == f"{experiment_id}:{n}:step1")
            sample = {"n": n, "m": m, "placed_at": at, "position": "heater", "owner": record.request_id}
        else:
            # Release heater only after successful gripper lift, even if return later fails.
            actor.release_resources(sample["owner"], only_names=(f"heater:{m}",))
            sample = {**sample, "position": "gripper", "picked_at": at}
        viewer.publish_confirmed("samples", {str(n): sample})
        viewer.publish_confirmed("devices", application.controller.devices.states())
        log(event, n=n, m=m)
        if event == "picked":
            heat = at - sample["placed_at"]
            if heat < timing.heat_min_s or heat > timing.heat_max_s:
                raise RuntimeError(f"Actual heating time outside window: {heat:.3f}s")
        if visual_check is not None:
            result = visual_check(event, n, m)
            if not result.success:
                raise RuntimeError(result.message or "Visual checkpoint rejected")

    workflow = ZkszWorkflow(application, sleep=sleep, checkpoint=checkpoint, clock=clock)

    def handle(task):
        """Execute the selected glass step and publish its resulting sample/device state."""
        n, m = task.parameters["n"], task.parameters["m"]
        getattr(workflow, task.kind)(n, m)
        if task.kind == "step2":
            sample = viewer.snapshot()["samples"][str(n)]
            viewer.publish_confirmed("samples", {str(n): {**sample, "position": "tray"}})
        viewer.publish_confirmed("devices", application.controller.devices.states())
        return ActionResult.done()

    for kind in ("step1", "step2"):
        actor.register(kind, handle, replace_existing=True)
    start = clock()
    errors = []
    with ThreadPoolExecutor(max_workers=1) as worker:
        while True:
            records = tuple(r for r in system.task_manager.snapshot() if r.spec.task_id in ids)
            if all(r.status == TaskStatus.SUCCEEDED for r in records):
                break
            if system.executer.cooldown_remaining > 0:
                sleep(min(system.executer.cooldown_remaining, 0.1))
                continue
            task = system.executer.propose(preview, preview.prepare,
                model_builder=preview.planning_model, planning_capacities=preview.planning_capacities)
            if task is None:
                snapshot = viewer.decision_snapshot()
                queue = preview.queue(snapshot)
                if queue and preview.chain_ok(clock(), [(s["placed_at"], s["placed_at"]) for s in queue]):
                    delay = preview.release_at(queue[0]["placed_at"]) - clock()
                    if delay > 0:
                        sleep(min(delay, 0.1))
                        continue
                errors.append("No admissible task under current resources and heating deadlines")
                break
            try:
                request = system.executer.accept(task)
            except ValueError:
                # Time/resources may change after propose; recompute from Views.
                continue
            log("sent", task_id=task.task_id, request_id=request)
            future = worker.submit(actor.execute_accepted, task, request)
            while True:
                try:
                    result = future.result(timeout=0.05)
                    break
                except FutureTimeout:
                    system.task_manager.expire()
            log("finished", task_id=task.task_id, status=result.status)
            if not result.success:
                errors.append(result.message or result.error_code or result.status)
                break
    records = tuple(r for r in system.task_manager.snapshot() if r.spec.task_id in ids)
    return OnlineRunReport(not errors and all(r.status == TaskStatus.SUCCEEDED for r in records),
                           records, clock() - start, tuple(errors))
