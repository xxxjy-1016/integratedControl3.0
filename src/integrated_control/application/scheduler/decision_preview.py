"""Linear FIFO pickup-chain preview using actual placement checkpoints."""
from dataclasses import dataclass, replace
import math
import time


@dataclass(frozen=True)
class OnlineTiming:
    """Bound step durations and placement/pickup offsets for conservative online heating previews."""
    step1_bound_s: float
    step2_bound_s: float
    heat_min_s: float
    heat_max_s: float
    put_offset_min_s: float
    put_offset_max_s: float
    pickup_offset_min_s: float
    pickup_offset_max_s: float
    pickup_margin_s: float = 0.0

    def __post_init__(self):
        """Validate and normalize the initialized online timing fields."""
        values = tuple(vars(self).values())
        if any(not math.isfinite(v) or v < 0 for v in values):
            raise ValueError("Online timing must be finite and nonnegative")
        if self.step1_bound_s <= 0 or self.step2_bound_s <= 0:
            raise ValueError("Action duration bounds must be positive")
        if not (self.heat_min_s <= self.heat_max_s and
                self.put_offset_min_s <= self.put_offset_max_s <= self.step1_bound_s and
                self.pickup_offset_min_s <= self.pickup_offset_max_s <= self.step2_bound_s):
            raise ValueError("Invalid heating window or action-to-event offsets")


class FifoPreview:
    """Prepare heater assignments and check the complete FIFO pickup chain for the glass process."""
    def __init__(self, timing: OnlineTiming, *, clock=time.monotonic):
        """Initialize fifo preview dependencies and internal state."""
        self.timing, self.clock = timing, clock

    def queue(self, snapshot):
        """Return heater-resident samples ordered by actual placement time and glass number."""
        return sorted((s for s in snapshot["samples"].values() if s.get("position") == "heater"),
                      key=lambda s: (s["placed_at"], s["n"]))

    def prepare(self, task, snapshot):
        """Bind a glass task to a concrete heater slot and the resources required for dispatch."""
        n = task.parameters["n"]
        if task.kind == "step1":
            free = [int(name.split(":")[1]) for name, r in snapshot["resources"].items()
                    if name.startswith("heater:") and r["available"] >= 1]
            if not free:
                return None
            m = min(free)
            return replace(task, parameters={**task.parameters, "m": m},
                           resources={"arm": 1, f"heater:{m}": 1},
                           retain_resources=(f"heater:{m}",))
        sample = snapshot["samples"].get(str(n))
        if sample is None or sample.get("position") != "heater":
            return None
        return replace(task, parameters={**task.parameters, "m": sample["m"]}, resources={"arm": 1})

    def release_at(self, placed_at):
        """Return the earliest pickup-action start allowed by the minimum heating time and pickup offset."""
        return placed_at + self.timing.heat_min_s - self.timing.pickup_offset_min_s

    def planning_capacities(self, snapshot):
        """Pool individual heater slots into generic capacity and current availability for search."""
        slots = [r for name, r in snapshot["resources"].items() if name.startswith("heater:")]
        return ({"arm": snapshot["resources"]["arm"]["capacity"],
                 "heaters": sum(r["capacity"] for r in slots)},
                {"arm": snapshot["resources"]["arm"]["available"],
                 "heaters": sum(r["available"] for r in slots)})

    def planning_model(self, task, snapshot):
        """Translate this experiment only; generic searches remain device-neutral."""
        from .contracts import SchedulingTask, TimeLink
        p = self.timing
        if task.kind == "step1":
            return SchedulingTask(task.task_id, p.step1_bound_s, task.dependencies,
                resources={"arm": 1, "heaters": 1}, retain_resources=("heaters",), priority=1)
        sample = snapshot["samples"].get(str(task.parameters["n"]), {})
        if sample.get("position") == "heater":
            return SchedulingTask(task.task_id, p.step2_bound_s, task.dependencies,
                release_at=self.release_at(sample["placed_at"]),
                deadline_at=sample["placed_at"] + p.heat_max_s - p.pickup_offset_max_s - p.pickup_margin_s + p.step2_bound_s,
                resources={"arm": 1}, resource_returns={"heaters": 1})
        return SchedulingTask(task.task_id, p.step2_bound_s, task.dependencies,
            resources={"arm": 1}, resource_returns={"heaters": 1},
            time_links=tuple(TimeLink(dep,
                p.put_offset_max_s - p.step1_bound_s + p.heat_min_s - p.pickup_offset_min_s,
                p.put_offset_min_s - p.step1_bound_s + p.heat_max_s - p.pickup_offset_max_s - p.pickup_margin_s)
                for dep in task.dependencies))

    def chain_ok(self, now, intervals):
        """Check whether sequential FIFO pickups can all meet their heating windows using bounded timings."""
        p = self.timing
        for put_min, put_max in intervals:
            start = max(now, self.release_at(put_max))
            if start + p.pickup_offset_max_s > put_min + p.heat_max_s - p.pickup_margin_s:
                return False
            now = start + p.step2_bound_s
        return True

    def __call__(self, task, snapshot):
        """Check current resources, heating windows, FIFO order, and the complete resulting pickup chain."""
        p, now = self.timing, self.clock()
        from .actor import Actor
        if not Actor.resources_fit(task, snapshot):
            return False
        queue = self.queue(snapshot)
        intervals = [(s["placed_at"], s["placed_at"]) for s in queue]
        if task.kind == "step1":
            intervals.append((now + p.put_offset_min_s, now + p.put_offset_max_s))
            return self.chain_ok(now + p.step1_bound_s, intervals)
        if task.kind != "step2" or not queue or queue[0]["n"] != task.parameters["n"]:
            return False
        sample = queue[0]
        if task.parameters["m"] != sample["m"] or now < self.release_at(sample["placed_at"]):
            return False
        if now + p.pickup_offset_max_s > sample["placed_at"] + p.heat_max_s - p.pickup_margin_s:
            return False
        return self.chain_ok(now + p.step2_bound_s, intervals[1:])
