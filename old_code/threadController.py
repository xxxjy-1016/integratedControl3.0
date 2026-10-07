from ortools.sat.python import cp_model
import pandas as pd

class threadController:

    """Coordinate the legacy three-phase spin and heating process.

    Phase A loads the coater and dispenses the main solution at S_a, with blocking t_A1 and nonblocking t_A2.
    Phase B dispenses the second solution at S_b, with blocking t_B1 and nonblocking t_B2; enforce
    (S_b + t_addSolution2) - (S_a + t_startSpin) = t_delay. Phase H transfers the glass to the heater at S_h,
    with blocking t_H1 and nonblocking t_H2. Enforce the total spin duration using
    (S_h + t_pickGlassFromSpinCoater) - (S_a + t_startSpin), rather than a single spinInfo segment."""

    t_startSpin = 46 # Start at the origin, dispense the first solution, and begin spinning.
    t_addSolution2 =  29 # Start at the tip station and dispense the second solution.
    t_pickGlassFromSpinCoater = 1
    t_A1 = 51 # First blocking phase: transfer glass to the coater, aspirate/dispense, start spinning, return the tip, return home.
    t_B1 = 30 # Second blocking phase: change tip, aspirate antisolvent, dispense, and raise the pipette.
    t_H1 = 25 # Third blocking phase: transfer glass to the heater, eject the tip, and return home.
    t_T = 21 # Fourth blocking phase: retrieve glass from the heater, return it to the tray, and return home.
    cap_heater = 8  # The heater holds at most 4 glasses.

    def plan_antiSolution(num_glasses, paramList):
        """Plan anti solution."""
        model = cp_model.CpModel()

        # Preset physical timings in seconds; calibrate them for the actual hardware.
        t_spin_max = 100  # Maximum total spin time must exceed t_delay + t_A2.
        t_heat_max = 1200  # Maximum heating duration.

        horizon = num_glasses * (
                    threadController.t_A1 + t_spin_max + threadController.t_H1 + t_heat_max + threadController.t_T)

        jobs = {}
        arm_intervals = []
        spin_intervals = []
        heat_intervals = []
        heat_demands = []

        for i in range(num_glasses):
            t_delay = paramList[i]['t_delay']  # Dispense antisolvent after t_delay seconds of spinning.
            t_spin = paramList[i]['t_spin']  # Total spin duration is t_spin seconds.
            t_heat = paramList[i]['t_heat']  # Heating duration.
            t_win = paramList[i]['t_win']  # Allowed transfer window after spinning.
            t_wait_heat = paramList[i]['t_wait_heat']  # Maximum permitted wait before pickup after heating completes.

            # 1. Define the four arm-action intervals.
            S_A = model.NewIntVar(0, horizon, f'S_A_{i}')
            E_A = model.NewIntVar(0, horizon, f'E_A_{i}')
            I_A = model.NewIntervalVar(S_A, threadController.t_A1, E_A, f'I_A_{i}')

            S_B = model.NewIntVar(0, horizon, f'S_B_{i}')
            E_B = model.NewIntVar(0, horizon, f'E_B_{i}')
            I_B = model.NewIntervalVar(S_B, threadController.t_B1, E_B, f'I_B_{i}')

            S_H = model.NewIntVar(0, horizon, f'S_H_{i}')
            E_H = model.NewIntVar(0, horizon, f'E_H_{i}')
            I_H = model.NewIntervalVar(S_H, threadController.t_H1, E_H, f'I_H_{i}')

            S_T = model.NewIntVar(0, horizon, f'S_T_{i}')
            E_T = model.NewIntVar(0, horizon, f'E_T_{i}')
            I_T = model.NewIntervalVar(S_T, threadController.t_T, E_T, f'I_T_{i}')

            arm_intervals.extend([I_A, I_B, I_H, I_T])

            # 2. Enforce physical ordering and process time windows.
            # A2 (antisolvent) must start exactly t_delay seconds after A1 ends.
            model.Add(S_B + threadController.t_addSolution2 - (S_A + threadController.t_startSpin) == t_delay)  # limit1

            # C (transfer) must start within t_win seconds after spinning finishes.
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (S_A + threadController.t_startSpin) >= t_spin)
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (
                        S_A + threadController.t_startSpin) <= t_spin + t_win)

            # E (pickup) must start after heating finishes.
            model.Add(S_T >= E_H + t_heat)

            # Require pickup to start within t_wait_heat seconds after heating finishes.
            model.Add(S_T <= E_H + t_heat + t_wait_heat)

            # 3. Spin coater occupancy lasts from A1 start to C end, when the glass has left.
            spin_occ_size = model.NewIntVar(t_spin, horizon, f'spin_occ_size_{i}')
            model.Add(spin_occ_size == E_H - S_A)
            I_spin = model.NewIntervalVar(S_A, spin_occ_size, E_H, f'I_spin_{i}')
            spin_intervals.append(I_spin)

            # 4. Reserve heater occupancy from S_H, when transfer toward the heater starts.
            heat_occ_size = model.NewIntVar(t_heat + threadController.t_H1, horizon, f'heat_occ_size_{i}')
            model.Add(heat_occ_size == S_T - S_H)  # Cover the complete placement-to-pickup interval.
            I_heat = model.NewIntervalVar(S_H, heat_occ_size, S_T, f'I_heat_{i}')
            heat_intervals.append(I_heat)
            heat_demands.append(1)

            # Collect key timestamps in a dictionary for later inspection.
            jobs[i] = {'S_A': S_A, 'S_B': S_B, 'S_H': S_H, 'S_T': S_T, 'E_T': E_T, 'glass_id' : paramList[i]['glass_id']}

        # 5. Add global mutual-exclusion and resource constraints.
        model.AddNoOverlap(arm_intervals)  # Arm mutual exclusion.
        model.AddNoOverlap(spin_intervals)  # Spin coater mutual exclusion.
        model.AddCumulative(heat_intervals, heat_demands, threadController.cap_heater)  # Heater capacity.

        # 6. Order glass 1 before glass 2 to break equivalent-solution symmetry.
        for i in range(num_glasses - 1):
            model.Add(jobs[i]['S_A'] < jobs[i + 1]['S_A'])

        # Minimize the maximum completion time (makespan).
        makespan = model.NewIntVar(0, horizon, 'makespan')
        model.AddMaxEquality(makespan, [jobs[i]['E_T'] for i in range(num_glasses)])
        model.Minimize(makespan)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        timeline = []
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for i in range(num_glasses):
                # Read individual step timestamps from the jobs dictionary.
                timeline.append({"time": solver.Value(jobs[i]['S_A']), "glass_id": jobs[i]['glass_id'], "action": "Task_A",
                                 "desc": "上料与主液旋涂"})
                timeline.append(
                    {"time": solver.Value(jobs[i]['S_B']), "glass_id": jobs[i]['glass_id'], "action": "Task_B", "desc": "滴加反溶剂"})
                timeline.append(
                    {"time": solver.Value(jobs[i]['S_H']), "glass_id": jobs[i]['glass_id'], "action": "Task_H", "desc": "移入加热台", "endTime" : solver.Value(jobs[i]['S_T']) } )
                timeline.append(
                    {"time": solver.Value(jobs[i]['S_T']), "glass_id": jobs[i]['glass_id'], "action": "Task_T", "desc": "下料归位"})

            df = pd.DataFrame(timeline).sort_values(by="time")
            return df.to_dict('records')
        else:
            raise Exception("无法找到满足工艺时序的调度方案！")

    def plan_noAntiSolution(num_glasses, paramList):
        """Schedule loading/spinning A, heater transfer H, heating, and tray return T without antisolvent."""
        model = cp_model.CpModel()

        # Preset physical timings in seconds; calibrate them for the actual hardware.
        t_spin_max = 1000  # Maximum total spin duration.
        t_heat_max = 12000  # Maximum heating duration.

        horizon = num_glasses * (
                    threadController.t_A1 + t_spin_max + threadController.t_H1 + t_heat_max + threadController.t_T)

        jobs = {}
        arm_intervals = []
        spin_intervals = []
        heat_intervals = []
        heat_demands = []

        for i in range(num_glasses):
            t_spin = paramList[i]['t_spin']  # Total spin duration.
            t_heat = paramList[i]['t_heat']  # Heating duration.
            t_win = paramList[i]['t_win']  # Allowed transfer window from spin completion to heating.
            t_wait_heat = paramList[i]['t_wait_heat']  # Maximum pickup wait after heating completes.

            # 1. Define the three arm-action intervals A, H, and T.
            S_A = model.NewIntVar(0, horizon, f'S_A_{i}')
            E_A = model.NewIntVar(0, horizon, f'E_A_{i}')
            I_A = model.NewIntervalVar(S_A, threadController.t_A1, E_A, f'I_A_{i}')

            S_H = model.NewIntVar(0, horizon, f'S_H_{i}')
            E_H = model.NewIntVar(0, horizon, f'E_H_{i}')
            I_H = model.NewIntervalVar(S_H, threadController.t_H1, E_H, f'I_H_{i}')

            S_T = model.NewIntVar(0, horizon, f'S_T_{i}')
            E_T = model.NewIntVar(0, horizon, f'E_T_{i}')
            I_T = model.NewIntervalVar(S_T, threadController.t_T, E_T, f'I_T_{i}')

            arm_intervals.extend([I_A, I_H, I_T])

            # 2. Enforce process ordering.
            # Transfer to the heater must start within t_win seconds after spinning finishes.
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (S_A + threadController.t_startSpin) >= t_spin)
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (
                        S_A + threadController.t_startSpin) <= t_spin + t_win)

            # Pickup cannot precede heating completion and must respect t_wait_heat.
            model.Add(S_T >= E_H + t_heat)
            model.Add(S_T <= E_H + t_heat + t_wait_heat)

            # 3. Spin coater occupancy lasts from A start to H end, when the glass has left.
            spin_occ_size = model.NewIntVar(t_spin, horizon, f'spin_occ_size_{i}')
            model.Add(spin_occ_size == E_H - S_A)
            I_spin = model.NewIntervalVar(S_A, spin_occ_size, E_H, f'I_spin_{i}')
            spin_intervals.append(I_spin)

            # 4. Reserve heater occupancy from S_H, when transfer toward the heater starts.
            heat_occ_size = model.NewIntVar(t_heat + threadController.t_H1, horizon, f'heat_occ_size_{i}')
            model.Add(heat_occ_size == S_T - S_H)  # Cover the complete placement-to-pickup interval.
            I_heat = model.NewIntervalVar(S_H, heat_occ_size, S_T, f'I_heat_{i}')
            heat_intervals.append(I_heat)
            heat_demands.append(1)

            # Store key timestamps.
            jobs[i] = {'S_A': S_A, 'S_H': S_H, 'S_T': S_T, 'E_T': E_T, 'glass_id' : paramList[i]['glass_id']}

        # 5. Enforce global resource constraints.
        model.AddNoOverlap(arm_intervals)  # The arm performs only one action at a time.
        model.AddNoOverlap(spin_intervals)  # The spin coater processes only one glass at a time.
        model.AddCumulative(heat_intervals, heat_demands, threadController.cap_heater)  # Limit heater capacity.

        # 6. Break symmetry by ordering glasses by loading time.
        for i in range(num_glasses - 1):
            model.Add(jobs[i]['S_A'] < jobs[i + 1]['S_A'])

        # 7. Minimize maximum completion time.
        makespan = model.NewIntVar(0, horizon, 'makespan')
        model.AddMaxEquality(makespan, [jobs[i]['E_T'] for i in range(num_glasses)])
        model.Minimize(makespan)

        # Solve the model.
        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        timeline = []
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for i in range(num_glasses):
                timeline.append({"time": solver.Value(jobs[i]['S_A']), "glass_id": jobs[i]['glass_id'],
                                 "action": "Task_A", "desc": "上料与旋涂"})
                timeline.append({"time": solver.Value(jobs[i]['S_H']), "glass_id": jobs[i]['glass_id'],
                                 "action": "Task_H", "desc": "移入加热台"})
                timeline.append({"time": solver.Value(jobs[i]['S_T']), "glass_id": jobs[i]['glass_id'],
                                 "action": "Task_T", "desc": "下料归位"})
            df = pd.DataFrame(timeline).sort_values(by="time")
            return df.to_dict('records')
        else:
            raise Exception("无法找到满足工艺时序的调度方案！")


if __name__ == "__main__":
    params = []
    for i in range(24):
        params.append({'t_delay' : 37, 't_spin' : 42, 't_heat' : 1200, 't_win' : 1, 't_wait_heat' : 0, 'glass_id' : i + 1})
    plan = threadController.plan_antiSolution(24, params)
    print("全局调度时刻表：")
    print("-" * 65)
    for step in plan:
        print(f"Time: {step['time']:>4}s | Glass: #{step['glass_id']} | Action: {step['action']:<8} | {step['desc']}")
        #if(step['action'] == 'Task_H'):
            #print("ending time : ", step['endTime'])
    print("-" * 65)