# 机械臂玻璃片加热调度器 使用说明

单机械臂 + N 片玻璃 + H 个加热器：程序自动规划 `step1(n, m)`（取第 n 片放上第 m 个
加热器）与 `step2(n, m)`（从第 m 个加热器取回第 n 片）的下发时刻，在满足全部工艺
约束的前提下让总完工时间（makespan）尽量短，并输出可直接执行的指令时间表。

## 快速开始

```bash
python glass_heat_scheduler.py          # 首次运行自动生成 params.json 并输出时间表
# 编辑 params.json 里的数值，再运行一次即可
python glass_heat_scheduler.py --demo   # 跑 4 个内置场景
```

运行后先以**文本时间表**形式输出到屏幕：指令表（每片玻璃的 step1/step2 时刻与
加热器编号）+ 文本甘特图。加 `--out schedule.txt` 可同时存一份到文件。

## 参数文件 params.json

```json
{
  "params": {
    "time_step1": 2.0,
    "time_step2": 1.0,
    "heat_time_min": 5.0,
    "heat_time_max": 12.0,
    "num_heater": 3,
    "num_glass": 8,
    "heat_measure": "until_pickup"
  },
  "solver": { "method": "auto", "beam_width": 800, "time_limit": 30.0 }
}
```

（JSON 不支持注释，上块仅作展示；请按下表理解字段。）

| 字段 | 含义 |
|---|---|
| `heat_time_min / heat_time_max` | 玻璃片在加热器上的停留时间必须落在此区间 |
| `heat_measure` | 在台时间口径：`until_pickup`＝夹起瞬间离台（默认）；`including_pickup`＝把 step2 整段计入在台时间 |
| `solver.method` | `auto`（默认：小规模精确、大规模束搜索）/ `exact` / `beam` / `greedy` |
| `solver.beam_width` | 束搜索宽度，越大越优越慢 |
| `solver.time_limit` | 搜索时间上限（秒） |

也可只写平铺的 params 字段（不带 `params`/`solver` 包一层）。**键名拼错会直接报错**
并列出合法键，不会静默用默认值。

## 命令行

```bash
python glass_heat_scheduler.py [-c 配置.json] [-o 输出.txt] [单项参数覆盖...]
```

- 单项参数（`--num-glass`、`--time-step1`、`--heat-time-max` 等）**优先级高于配置文件**；
  未给出的项依次取配置文件 → 内置默认。
- `--compare`：同一参数分别跑 greedy / beam / exact 并列表对比。
- `--json`：额外输出机器可读的完整计划（含每条指令的时刻）。
- `--demo`：内置 4 个典型场景（宽松加热窗 / 紧加热窗 / 中等规模 / 单加热器）。

## 输出怎么读

- **makespan**：全部玻璃片加热完并放回的时刻（越小越好）。
- **下界 / 相对差距**：理论下界与它的差距；下界偏松时差距不为 0 属正常。
- **已证明最优**：搜索穷尽后确认没有更快的调度（与"差距是否为 0"无关）。
- **校验行**：程序把生成的指令逐条喂给 `step1/step2` 物理校验——单机不重叠、
  加热器不超载、每片在台时间在区间内。`全部硬约束通过` 才可执行。
- 甘特图：`P`=step1 上片，`G`=step2 取片，数字=玻璃片编号，`.`=空闲。

## 作为库调用

```python
from glass_heat_scheduler import Params, solve

plan = solve(Params(time_step1=2.0, time_step2=1.0, heat_time_min=5.0,
                    heat_time_max=12.0, num_heater=3, num_glass=8))
for c in plan.commands:          # 按时间排好的指令流
    print(c.t, c.kind, c.n, c.m)
```

`plan.makespan` 总时长、`plan.feasible` 是否通过校验、`plan.proven_optimal` 是否
已证明最优、`plan.errors` 诊断信息。若参数本身无解（如 `heat_time_max` 过紧），
程序不会崩溃，而是返回带诊断的贪心参考解。

## 执行计划 run_plan.py

`run_plan.py` 调用本调度器算出计划，并按计划时刻逐条派发 `step1`/`step2`。
**这两个函数来自外部黑盒库**（本程序不管其内容，只负责导入与调用）：

```bash
# 1) 只打印将要执行的指令流，不调用任何函数（先目检一遍）
python run_plan.py --mode dry

# 2) 用调度器内置的原语离线重放整条计划，做全套约束校验（不碰真实机械臂）
python run_plan.py --mode simulate

# 3) 真实执行：倒计时 3 秒后按计划时刻调用外部库的 step1/step2
python run_plan.py --mode realtime
```

**对接外部库**：默认导入模块名 `robot_lib`，两种方式指定：

```bash
python run_plan.py --robot-lib my_robot_module          # 命令行指定模块名
export ROBOT_LIB=my_robot_module                        # 或环境变量
```

外部模块只需导出 `step1(n, m)` 与 `step2(n, m)` 两个函数（同步阻塞调用即可，
执行器按单调时钟在正确时刻调用它们）。找不到模块时会给出明确提示并退出。

**其他选项**：

- `-c/--config`：指定配置文件（同 `glass_heat_scheduler.py`）。
- `--log 文件`：把执行日志（每条指令的计划时刻/实际时刻/漂移/函数返回值）存成文本。

**安全机制**（realtime 模式）：执行器按"漂移预算"反向递推每条指令允许的最大滞后
（预算来自后续玻璃片的在台时间裕量）。执行中一旦滞后超过本条预算立即中止（exit 3），
防止玻璃片在台超时；达到一半预算会先告警。

**退出码**：`0` 成功；`1` 外部库缺失；`2` 参数/配置错误或计划不可行；`3` 执行中
漂移超预算安全中止（日志里会写明已执行到第几条，便于人工复位现场）。

## 正确性验证

`_crosscheck.py` 用一个完全独立的暴力求解器对拍 93 个随机+边界用例
（含不可行实例），并校验下界有效性：

```bash
python _crosscheck.py    # 输出 "总用例 93  失败 0" 即通过
```
