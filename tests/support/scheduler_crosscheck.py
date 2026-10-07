"""Independent crosschecks of shared dry planning, without the legacy model."""
import math
import random
from integrated_control.application.scheduler.algorithm import AlgorithmConfig
from integrated_control.application.scheduler.cli import dry
from integrated_control.application.scheduler.decision_preview import OnlineTiming
from integrated_control.application.workflows.batch_zksz import BatchParams
from tests.support.bruteforce_scheduler import brute_force


def cases():
    """Generate deterministic randomized and boundary scheduling cases for independent comparison."""
    rng = random.Random(20261005)
    for _ in range(24):
        minimum = round(rng.uniform(0, 6), 2)
        params = BatchParams(round(rng.uniform(.5, 3), 2), round(rng.uniform(.5, 3), 2),
            minimum, round(minimum + rng.uniform(0, 9), 2), rng.randint(1, 3), rng.randint(1, 4))
        yield params, round(rng.uniform(0, params.time_step2), 2)
    for values in ((2, 1, 0, 0, 1, 4), (1, 1, 5, 5, 2, 4), (1, 4, 2, 2, 1, 3),
                   (4, 1, 3, 3, 3, 4), (1, 1, 0, 50, 5, 4), (1, 3, 2, 3, 2, 4)):
        yield BatchParams(*values), 0.0


def validate(plan, params, pickup_offset_s):
    """Check planned task order, duration, heater capacity, and heating windows independently."""
    active, done, previous = {}, set(), 0.0
    assert len(plan.commands) == 2 * params.num_glass
    for command in plan.commands:
        _, n, kind = command.task_id.split(":")
        n = int(n)
        assert command.start >= previous - 1e-7
        duration = params.time_step1 if kind == "step1" else params.time_step2
        assert abs(command.end - command.start - duration) < 1e-7
        if kind == "step1":
            assert n not in active and n not in done
            assert len(active) < params.num_heater
            active[n] = command.end
        else:
            assert kind == "step2" and n in active
            heat = command.start + pickup_offset_s - active.pop(n)
            assert params.heat_time_min - 1e-7 <= heat <= params.heat_time_max + 1e-7
            done.add(n)
        previous = command.end
    assert not active and done == set(range(params.num_glass))


def run_checks():
    """Compare five scheduling algorithms against independent enumeration on every generated case."""
    count = 0
    for params, pickup_offset_s in cases():
        optimal, _ = brute_force(params.num_glass, params.num_heater,
            params.time_step1, params.time_step2, params.heat_time_min,
            params.heat_time_max, pickup_offset_s)
        timing = OnlineTiming(params.time_step1, params.time_step2,
            params.heat_time_min, params.heat_time_max, params.time_step1, params.time_step1,
            pickup_offset_s, pickup_offset_s)
        for method in ("fifo", "greedy", "exact", "beam", "auto"):
            plan = dry(num_glass=params.num_glass, num_heater=params.num_heater, timing=timing,
                       config=AlgorithmConfig(method, beam_width=400, time_limit_s=2))
            if plan.feasible:
                validate(plan, params, pickup_offset_s)
                assert plan.makespan >= optimal - 1e-7, (method, params, plan)
            if method in ("exact", "auto"):
                assert plan.feasible == math.isfinite(optimal), (method, params, plan)
                if plan.feasible:
                    assert plan.proven_optimal
                    assert abs(plan.makespan - optimal) < 1e-7, (method, params, plan, optimal)
        count += 1
    return count


if __name__ == "__main__":
    print(f"Independent crosschecks: {run_checks()} cases / 5 algorithms passed")
