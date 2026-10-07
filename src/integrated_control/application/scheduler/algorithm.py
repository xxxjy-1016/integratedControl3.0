"""Generic serial-task searches. No algorithm interprets task/device kinds."""
from dataclasses import dataclass
import math
import time
from .contracts import SchedulingTask, TimeLink, ScheduledTask, TaskPlan


@dataclass(frozen=True)
class AlgorithmConfig:
    """Configure a solver; None lookahead searches every remaining task."""
    method: str
    beam_width: int = 200
    time_limit_s: float = 0.05
    exact_task_limit: int = 8
    lookahead_depth: int | None = None

    def __post_init__(self):
        """Validate and normalize the initialized algorithm config fields."""
        if self.method not in ("fifo", "greedy", "exact", "beam", "auto"):
            raise ValueError("Unknown scheduling algorithm")
        if any(type(v) is not int or v < 1 for v in (
                self.beam_width, self.exact_task_limit)):
            raise ValueError("Search widths and thresholds must be positive integers")
        if self.lookahead_depth is not None and (
                type(self.lookahead_depth) is not int or self.lookahead_depth < 1):
            raise ValueError("Lookahead depth must be a positive integer or None")
        if not math.isfinite(self.time_limit_s) or self.time_limit_s <= 0:
            raise ValueError("Search time limit must be positive and finite")


def _validate(tasks, capacities, completed):
    """Validate task identities, dependency cycles, time links, and resource quantities before search."""
    by_id = {t.task_id: t for t in tasks}
    if len(by_id) != len(tasks) or any(not t.task_id or t.task_id in completed for t in tasks):
        raise ValueError("Task identifiers must be unique and unfinished")
    if any(not math.isfinite(v) or v < 0 for v in capacities.values()):
        raise ValueError("Resource capacities must be finite and nonnegative")
    if any(not math.isfinite(v) for v in completed.values()):
        raise ValueError("Completed times must be finite")
    seen, visiting = set(), set()
    def visit(key):
        """Visit a dependency while collecting or validating the syntax tree."""
        if key in completed or key in seen:
            return
        if key in visiting:
            raise ValueError("Cyclic task dependencies")
        if key not in by_id:
            raise ValueError("Unknown dependency")
        visiting.add(key)
        for dep in by_id[key].dependencies:
            visit(dep)
        visiting.remove(key)
        seen.add(key)
    for task in tasks:
        visit(task.task_id)
        if not math.isfinite(task.duration_s) or task.duration_s <= 0:
            raise ValueError("Task durations must be positive and finite")
        if not math.isfinite(task.release_at) or (task.deadline_at is not None and not math.isfinite(task.deadline_at)):
            raise ValueError("Task windows must be finite")
        if not math.isfinite(task.priority):
            raise ValueError("Task priority must be finite")
        for values in (task.resources, task.resource_returns):
            if any(k not in capacities or not math.isfinite(v) or v < 0 for k, v in values.items()):
                raise ValueError("Invalid task resource requirement/return")
        if any(k not in task.resources for k in task.retain_resources):
            raise ValueError("Only required resources can be retained")
        for link in task.time_links:
            if link.predecessor not in task.dependencies or not math.isfinite(link.min_delay_s) or (
                    link.max_delay_s is not None and (not math.isfinite(link.max_delay_s) or link.max_delay_s < link.min_delay_s)):
                raise ValueError("Invalid predecessor time link")
    return by_id


def _times(order, by_id, completed, now, *, start_now=False):
    """Solve difference constraints; max-lags may delay earlier tasks.

    Fixed zero detects deadlines/cycles. Recomputing prefixes includes required
    idle before predecessors, instead of assuming earliest-start is dominant."""
    index = {key: i + 1 for i, key in enumerate(order)}
    edges = []
    for i, key in enumerate(order):
        task, node = by_id[key], index[key]
        edges.append((0, node, max(now, task.release_at)))
        if i == 0 and start_now:
            # Keep the first action executable now even when later max-lags
            # would otherwise move its start forward during prefix solving.
            edges.append((node, 0, -now))
        if i:
            prev = order[i - 1]
            edges.append((index[prev], node, by_id[prev].duration_s))
        if task.deadline_at is not None:
            edges.append((node, 0, task.duration_s - task.deadline_at))
        linked = {link.predecessor: link for link in task.time_links}
        for dep in task.dependencies:
            link = linked.get(dep, TimeLink(dep))
            if dep in completed:
                edges.append((0, node, completed[dep] + link.min_delay_s))
                if link.max_delay_s is not None:
                    edges.append((node, 0, -completed[dep] - link.max_delay_s))
            else:
                duration = by_id[dep].duration_s
                edges.append((index[dep], node, duration + link.min_delay_s))
                if link.max_delay_s is not None:
                    edges.append((node, index[dep], -duration - link.max_delay_s))
    distances = [0.0] * (len(order) + 1)
    for _ in range(len(distances)):
        changed = False
        for source, target, delay in edges:
            value = distances[source] + delay
            if distances[target] + 1e-9 < value:
                if target == 0:
                    return None
                distances[target], changed = value, True
        if not changed:
            return tuple(ScheduledTask(key, distances[index[key]],
                distances[index[key]] + by_id[key].duration_s) for key in order)
    return None


def _children(node, by_id, capacities, completed, now, *, first_candidates=None):
    """Expand a task prefix with dependency-, resource-, and time-feasible next tasks."""
    order, available, commands = node
    done = set(order) | set(completed)
    children, symmetry = [], set()
    ends = {c.task_id: c.end for c in commands} | dict(completed)
    for task in by_id.values():
        if not order and first_candidates is not None and task.task_id not in first_candidates:
            continue
        if task.task_id in done or not set(task.dependencies) <= done:
            continue
        if any(amount > available[name] + 1e-9 for name, amount in task.resources.items()):
            continue
        if task.symmetry_group is not None:
            signature = (task.symmetry_group, task.duration_s, task.release_at, task.deadline_at,
                tuple(sorted(task.resources.items())), tuple(sorted(task.resource_returns.items())),
                task.retain_resources, tuple(sorted(ends[d] for d in task.dependencies)),
                tuple((l.min_delay_s, l.max_delay_s) for l in task.time_links))
            if signature in symmetry:
                continue
            symmetry.add(signature)
        new_order = order + (task.task_id,)
        times = _times(new_order, by_id, completed, now, start_now=first_candidates is not None)
        if times is None:
            continue
        resources = dict(available)
        for name in task.retain_resources:
            resources[name] -= task.resources[name]
        for name, amount in task.resource_returns.items():
            resources[name] += amount
        if any(v < -1e-9 or v > capacities[k] + 1e-9 for k, v in resources.items()):
            continue
        children.append((new_order, resources, times))
    return children


@dataclass
class _SearchProblem:
    """Hold immutable task models and search settings while expanding ordered task prefixes."""
    tasks: tuple
    by_id: dict
    capacities: dict
    completed: dict
    now: float
    target: int
    horizon: int | None
    root: tuple
    config: AlgorithmConfig
    deadline: float
    first_candidates: frozenset[str] | None = None

    def children(self, node):
        """Return legal extensions of the supplied search node."""
        return _children(node, self.by_id, self.capacities, self.completed, self.now,
                         first_candidates=self.first_candidates)

    def score(self, node):
        """Compute the scheduling score used to retain or prune a search node."""
        finish = node[2][-1].end if node[2] else self.now
        return finish + sum(t.duration_s for t in self.tasks if t.task_id not in node[0])

    def heuristic(self, node):
        """Rank a search node by task priority, deadline, start time, and duration."""
        task = self.by_id[node[0][-1]]
        return (-task.priority, task.deadline_at if task.deadline_at is not None else math.inf,
                node[2][-1].start, task.duration_s)


def _solve_linear(problem, choose):
    """Follow one chosen legal child per depth until reaching the target or stopping on failure/timeout."""
    node, timed_out = problem.root, False
    for _ in range(problem.target):
        if time.perf_counter() >= problem.deadline:
            timed_out = True
            break
        children = problem.children(node)
        if not children:
            break
        node = choose(children)
    return (node if len(node[0]) == problem.target else None), timed_out


def _solve_fifo(problem):
    """Choose the first legal child in task registration order."""
    return _solve_linear(problem, lambda children: children[0])


def _solve_greedy(problem):
    """Choose priority, deadline, start and duration; never backtrack."""
    return _solve_linear(problem, lambda children: min(children, key=problem.heuristic))


def _solve_beam(problem):
    """Expand each frontier and retain at most beam_width ranked states."""
    frontier, timed_out = [problem.root], False
    for _ in range(problem.target):
        next_nodes = []
        for node in frontier:
            if time.perf_counter() >= problem.deadline:
                timed_out = True
                break
            next_nodes.extend(problem.children(node))
        if timed_out or not next_nodes:
            frontier = []
            break
        frontier = sorted(next_nodes, key=lambda n: (problem.score(n), problem.heuristic(n)))[:problem.config.beam_width]
    best = None
    if frontier and len(frontier[0][0]) == problem.target:
        best = min(frontier, key=lambda n: n[2][-1].end if n[2] else problem.now)
    return best, timed_out


def _solve_exact(problem):
    """Depth-first branch-and-bound over every legal order."""
    stack, best, timed_out = [problem.root], None, False
    while stack:
        if time.perf_counter() >= problem.deadline:
            timed_out = True
            break
        node = stack.pop()
        if len(node[0]) == problem.target:
            finish = node[2][-1].end if node[2] else problem.now
            if best is None or finish < (best[2][-1].end if best[2] else problem.now):
                best = node
            continue
        if best is not None and problem.horizon is None and problem.score(node) >= best[2][-1].end - 1e-9:
            continue
        stack.extend(sorted(problem.children(node), key=problem.heuristic, reverse=True))
    return best, timed_out


def _solve_auto(problem):
    """Select exact/beam by configured unfinished-task count threshold."""
    method = "exact" if len(problem.tasks) <= problem.config.exact_task_limit else "beam"
    best, timed_out = _SOLVERS[method](problem)
    return best, timed_out, method


_SOLVERS = {"fifo": _solve_fifo, "greedy": _solve_greedy,
            "beam": _solve_beam, "exact": _solve_exact}


def schedule(tasks, capacities, config: AlgorithmConfig, *, now=0.0, completed=None,
             horizon=None, initial_available=None, first_candidates=None) -> TaskPlan:
    """Validate/build the shared problem, dispatch a solver, format its result.

    Bounded horizons produce provisional prefixes, never optimality claims.
    Search failure/timeout never produces a plan that violates hard constraints.
    first_candidates restricts only the first action and fixes its start to now;
    later actions may include any remaining task whose constraints permit it."""
    tasks, completed = tuple(tasks), dict(completed or {})
    if not math.isfinite(now):
        raise ValueError("Planning clock must be finite")
    by_id = _validate(tasks, capacities, completed)
    if first_candidates is not None:
        first_candidates = frozenset(first_candidates)
        if not first_candidates <= by_id.keys():
            raise ValueError("Unknown first-step candidate")
    target = len(tasks) if horizon is None else min(len(tasks), horizon)
    if target < 0:
        raise ValueError("Horizon must be nonnegative")
    available = dict(capacities if initial_available is None else initial_available)
    if set(available) != set(capacities) or any(not math.isfinite(v) or v < 0 or v > capacities[k]
                                               for k, v in available.items()):
        raise ValueError("Invalid initial resource availability")
    problem = _SearchProblem(tasks, by_id, dict(capacities), completed, now, target, horizon,
                             ((), available, ()), config, time.perf_counter() + config.time_limit_s,
                             first_candidates)
    method = config.method
    if method == "auto":
        best, timed_out, method = _solve_auto(problem)
    else:
        best, timed_out = _SOLVERS[method](problem)
    feasible = best is not None
    commands = best[2] if feasible else ()
    errors = () if feasible else ("Search time limit reached" if timed_out else "No feasible schedule found",)
    return TaskPlan(commands, feasible, feasible and method == "exact" and not timed_out and horizon is None
                    and first_candidates is None,
                    method, commands[-1].end - now if commands else 0.0, timed_out, errors)


def from_spec(spec, *, require_duration=False):
    """Convert generic TaskSpec scheduling metadata into a SchedulingTask."""
    meta = spec.parameters.get("scheduling", {})
    if require_duration and "duration_s" not in meta:
        raise ValueError(f"Task {spec.task_id} requires scheduling.duration_s for search")
    return SchedulingTask(spec.task_id, float(meta.get("duration_s", 1.0)), spec.dependencies,
        float(meta.get("release_at", 0)), meta.get("deadline_at"), spec.resources,
        spec.retain_resources, meta.get("resource_returns", {}),
        tuple(TimeLink(**link) for link in meta.get("time_links", ())), float(meta.get("priority", 0)))
