from ortools.sat.python import cp_model
import pandas as pd

class threadController:

    '''
    相关参数：
    第一步：把玻璃拿到旋涂仪上，取滴管，吸液，滴液，开始旋涂，然后放滴管，机械臂回到原点。动作开始于S_a，阻塞时间t_A1，非阻塞时间t_A2（这两个都是固定的）。
    第二步：取滴管，吸液，滴液，然后放滴管，机械臂回到原点。动作开始于S_b，阻塞时间t_B1,非阻塞时间t_B2(检查是否对大于0)：第一阶段旋涂时间约束：(S_b + t_addSolution2) - (S_a + t_startSpin) = t_delay)
    第三步：把玻璃片转移到加热台上。动作开始于S_h，阻塞时间t_H1，非阻塞时间t_H2。第二阶段旋涂时间约束：(S_h + t_pickGlassFromSpinCoater) - (S_a + t_startSpin) ~ t_spin 注意，t_spin不是spininfo里面的spinTime，而应该是旋涂仪运行的总时间
    '''

    t_startSpin = 46 # 从原点出发滴加第一步溶液直至开始旋涂
    t_addSolution2 =  29 # 从lips出发到将第二步的溶液滴加到上面
    t_pickGlassFromSpinCoater = 1
    t_A1 = 51 #第一段的阻塞时间：拿玻片 -> 放入旋涂仪 -> 吸主液 -> 滴加 -> 启动 -> 放下枪头 -> 回原点
    t_B1 = 30 #第二段的阻塞时间：换吸头 -> 吸反溶剂 -> 滴加 -> 枪头升起来
    t_H1 = 25 #第三段的阻塞时间：拿出旋涂仪里的玻璃 -> 放入加热台 -> 退枪头-> 回原点
    t_T = 21 # 第四段的阻塞时间：从加热台拿下 -> 放回 Platform -> 回原点
    cap_heater = 8  # 加热台最多放 4 块

    def plan_antiSolution(num_glasses, paramList):
        model = cp_model.CpModel()

        # 物理时间参数预设 (单位: 秒, 需根据你的实际硬件调整)
        t_spin_max = 100  # 旋涂总时长最大值 (大于 t_delay + t_A2)
        t_heat_max = 1200  # 加热台烘烤时间最大值

        horizon = num_glasses * (
                    threadController.t_A1 + t_spin_max + threadController.t_H1 + t_heat_max + threadController.t_T)

        jobs = {}
        arm_intervals = []
        spin_intervals = []
        heat_intervals = []
        heat_demands = []

        for i in range(num_glasses):
            t_delay = paramList[i]['t_delay']  # 旋涂t_delay s后滴加反溶剂
            t_spin = paramList[i]['t_spin']  # 总共旋涂t_spin s
            t_heat = paramList[i]['t_heat']  # 加热时间
            t_win = paramList[i]['t_win']  # 旋涂后多少秒内把玻璃转移
            t_wait_heat = paramList[i]['t_wait_heat']  # 新增：加热完成后最多等待多少秒必须下料

            # 1. 定义机械臂的四个动作时间区间
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

            # 2. 强物理时序与工艺时间窗约束
            # A2 (反溶剂) 必须严格在 A1 结束后 t_delay 秒开始
            model.Add(S_B + threadController.t_addSolution2 - (S_A + threadController.t_startSpin) == t_delay)  # limit1

            # C (转移) 必须在旋涂结束后 t_win 秒内开始
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (S_A + threadController.t_startSpin) >= t_spin)
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (
                        S_A + threadController.t_startSpin) <= t_spin + t_win)

            # E (下料) 必须在加热完成后开始
            model.Add(S_T >= E_H + t_heat)

            # ========== 新约束：加热完成后最多等待 t_wait_heat 秒内必须发起下料 ==========
            model.Add(S_T <= E_H + t_heat + t_wait_heat)

            # 3. 旋涂仪占用区间 (从 A1 开始，直到 C 结束，玻璃才真正离开)
            spin_occ_size = model.NewIntVar(t_spin, horizon, f'spin_occ_size_{i}')
            model.Add(spin_occ_size == E_H - S_A)
            I_spin = model.NewIntervalVar(S_A, spin_occ_size, E_H, f'I_spin_{i}')
            spin_intervals.append(I_spin)

            # 4. 加热台占用区间 (从 S_H 开始算占用，物理上此时机械臂已开始把玻璃往加热台上放)
            heat_occ_size = model.NewIntVar(t_heat + threadController.t_H1, horizon, f'heat_occ_size_{i}')
            model.Add(heat_occ_size == S_T - S_H)  # 覆盖从放玻璃到取玻璃的全过程
            I_heat = model.NewIntervalVar(S_H, heat_occ_size, S_T, f'I_heat_{i}')
            heat_intervals.append(I_heat)
            heat_demands.append(1)

            # 将所有核心时间戳收集到字典里，方便后期提取
            jobs[i] = {'S_A': S_A, 'S_B': S_B, 'S_H': S_H, 'S_T': S_T, 'E_T': E_T, 'glass_id' : paramList[i]['glass_id']}

        # 5. 添加全局互斥与资源约束
        model.AddNoOverlap(arm_intervals)  # 机械臂互斥
        model.AddNoOverlap(spin_intervals)  # 旋涂仪互斥
        model.AddCumulative(heat_intervals, heat_demands, threadController.cap_heater)  # 加热台容量

        # 6. 顺序约束 (强制让 1号比 2号先做，避免相同解的对称性导致求解慢)
        for i in range(num_glasses - 1):
            model.Add(jobs[i]['S_A'] < jobs[i + 1]['S_A'])

        # 目标：最小化最大完成时间 Makespan
        makespan = model.NewIntVar(0, horizon, 'makespan')
        model.AddMaxEquality(makespan, [jobs[i]['E_T'] for i in range(num_glasses)])
        model.Minimize(makespan)

        solver = cp_model.CpSolver()
        status = solver.Solve(model)

        timeline = []
        if status == cp_model.OPTIMAL or status == cp_model.FEASIBLE:
            for i in range(num_glasses):
                # 通过 jobs 字典安全提取每个步骤的具体发生时间
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
        """不含反溶剂的调度：A(上料旋涂) -> H(移入加热台) -> 加热 -> T(下料归位)"""
        model = cp_model.CpModel()

        # 物理时间参数预设 (单位: 秒, 需根据实际硬件调整)
        t_spin_max = 1000  # 旋涂总时长最大值
        t_heat_max = 12000  # 加热台烘烤时间最大值

        horizon = num_glasses * (
                    threadController.t_A1 + t_spin_max + threadController.t_H1 + t_heat_max + threadController.t_T)

        jobs = {}
        arm_intervals = []
        spin_intervals = []
        heat_intervals = []
        heat_demands = []

        for i in range(num_glasses):
            t_spin = paramList[i]['t_spin']  # 旋涂总时间
            t_heat = paramList[i]['t_heat']  # 加热时间
            t_win = paramList[i]['t_win']  # 旋涂结束后必须移入加热台的窗口时间
            t_wait_heat = paramList[i]['t_wait_heat']  # 加热结束后必须下料的最大等待时间

            # 1. 定义机械臂的三个动作区间 (A, H, T)
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

            # 2. 工艺时序约束
            # 移入加热台必须在旋涂结束后 t_win 秒内开始
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (S_A + threadController.t_startSpin) >= t_spin)
            model.Add(S_H + threadController.t_pickGlassFromSpinCoater - (
                        S_A + threadController.t_startSpin) <= t_spin + t_win)

            # 下料必须在加热完成后立即开始（不允许提前），且不能超过 t_wait_heat 延迟
            model.Add(S_T >= E_H + t_heat)
            model.Add(S_T <= E_H + t_heat + t_wait_heat)

            # 3. 旋涂仪占用区间 (从 A 开始，直到 H 结束，玻璃才离开)
            spin_occ_size = model.NewIntVar(t_spin, horizon, f'spin_occ_size_{i}')
            model.Add(spin_occ_size == E_H - S_A)
            I_spin = model.NewIntervalVar(S_A, spin_occ_size, E_H, f'I_spin_{i}')
            spin_intervals.append(I_spin)

            # 4. 加热台占用区间 (从 S_H 开始算占用，物理上此时机械臂已开始把玻璃往加热台上放)
            heat_occ_size = model.NewIntVar(t_heat + threadController.t_H1, horizon, f'heat_occ_size_{i}')
            model.Add(heat_occ_size == S_T - S_H)  # 覆盖从放玻璃到取玻璃的全过程
            I_heat = model.NewIntervalVar(S_H, heat_occ_size, S_T, f'I_heat_{i}')
            heat_intervals.append(I_heat)
            heat_demands.append(1)

            # 保存关键时间戳
            jobs[i] = {'S_A': S_A, 'S_H': S_H, 'S_T': S_T, 'E_T': E_T, 'glass_id' : paramList[i]['glass_id']}

        # 5. 全局资源约束
        model.AddNoOverlap(arm_intervals)  # 机械臂一次只能做一个动作
        model.AddNoOverlap(spin_intervals)  # 旋涂仪一次只能处理一片玻璃
        model.AddCumulative(heat_intervals, heat_demands, threadController.cap_heater)  # 加热台容量限制

        # 6. 打破对称性：按上料时间顺序处理玻璃
        for i in range(num_glasses - 1):
            model.Add(jobs[i]['S_A'] < jobs[i + 1]['S_A'])

        # 7. 目标：最小化最大完工时间
        makespan = model.NewIntVar(0, horizon, 'makespan')
        model.AddMaxEquality(makespan, [jobs[i]['E_T'] for i in range(num_glasses)])
        model.Minimize(makespan)

        # 求解
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