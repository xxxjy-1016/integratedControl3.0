# -*- coding: utf-8 -*-
"""Independent exhaustive glass checker, including idle before placement.

For identical glasses equal windows permit FIFO pickup by the EDF exchange
argument. Enumerate every legal type order, then use all-pairs shortest paths
to solve continuous timing constraints. Production uses different search and
longest-path relaxation. 
"""
EPS = 1e-9


def brute_force(num_glass, num_heater, time_step1, time_step2,
                heat_time_min, heat_time_max, pickup_offset_s):
    """Return the optimal schedule for one explicit pickup checkpoint offset."""
    best, best_seq = float("inf"), None
    def evaluate(order):
        """Evaluate."""
        nonlocal best, best_seq
        size = len(order) + 1
        dist = [[float("inf")] * size for _ in range(size)]
        for i in range(size):
            dist[i][i] = 0
        puts, pending, free, events = {}, [], list(range(1, num_heater + 1)), []
        for i, kind in enumerate(order, 1):
            dist[i][0] = min(dist[i][0], 0)  # start >= 0
            if i > 1:
                prev_duration = time_step1 if order[i - 2] == 1 else time_step2
                dist[i][i - 1] = -prev_duration
            if kind == 1:
                n = len(puts)
                m = free.pop(0)
                puts[n] = i
                pending.append((n, m))
            else:
                n, m = pending.pop(0)
                j = puts[n]
                # heat_min <= start_pick + pickup_offset - end_put <= heat_max
                dist[i][j] = min(dist[i][j],
                                 -time_step1 - heat_time_min + pickup_offset_s)
                dist[j][i] = min(dist[j][i],
                                 time_step1 + heat_time_max - pickup_offset_s)
                free.append(m)
                free.sort()
            events.append((kind, n, m))
        for k in range(size):
            for i in range(size):
                for j in range(size):
                    dist[i][j] = min(dist[i][j], dist[i][k] + dist[k][j])
        if any(dist[i][i] < -EPS for i in range(size)):
            return
        starts = [-dist[i][0] for i in range(1, size)]
        finish = starts[-1] + time_step2 if starts else 0
        if finish < best - EPS:
            best = finish
            best_seq = [(*event, start) for event, start in zip(events, starts)]
    def enumerate_orders(order, put, pick):
        """Enumerate orders."""
        if pick == num_glass:
            evaluate(order)
            return
        if put < num_glass and put - pick < num_heater:
            enumerate_orders(order + (1,), put + 1, pick)
        if pick < put:
            enumerate_orders(order + (2,), put, pick + 1)
    enumerate_orders((), 0, 0)
    return best, best_seq


if __name__ == "__main__":
    # Self-checks with manually derivable cases.
    # Case 1: N=1 gives a + hmin + b for any valid parameters in this model.
    print(brute_force(1, 1, 2.0, 1.0, 5.0, 12.0, 0.0))
    # Case 2: H=1, N=3, a=b=1, hmin=2; each serial glass takes 4, total 12.
    print("expect 12.0 ->", brute_force(3, 1, 1.0, 1.0, 2.0, 9.0, 0.0)[0])
    # Case 3: ample heaters, N=3, a=b=hmin=1, hmax=100; arm utilization gives 6.
    print("expect 6.0 ->", brute_force(3, 4, 1.0, 1.0, 1.0, 100.0, 0.0)[0])
