# Integrated Control 3.0

集成式涂布工作站的 Python 上位机程序，包含设备接口、串口通信、平台回零、单片 `zksz` 工艺、批量在线调度，以及离线方案计算和文本甘特图。

当前批量实验采用“两步工艺 + 在线决策”：每片玻璃拆成 `step1`（制备并上加热台）和 `step2`（取片并放回原位）。每次完成一个任务后，Executer 根据最新任务和 View 状态重新选择下一步。离线 `dry` 用于查看预测方案，不派发硬件动作。

`old_code/` 保存历史实现，供协议和迁移对照；正式程序不导入该目录。本文描述当前代码，历史架构提案中与本文冲突的部分不代表现行实现。

## 运行环境与安装

- Windows 10/11，Python 3.10 或更高版本。
- 模拟和离线计算可安装基础包；真机串口模式需要 `pyserial>=3.5`。
- 以下命令均在 `integratedControl3.0` 根目录运行。

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
```

使用真机串口时安装硬件依赖：

```powershell
python -m pip install -e ".[hardware]"
```

当前 `config/system.yaml` 默认是 `native_hardware`。运行主程序会连接设备并可能执行回零和工艺动作。首次联调应核实串口、从站地址、运动方向、软限位及工位坐标；仅验证软件时显式使用 `--device-mode simulation` 或直接运行 `dry`。

## 项目结构

```text
integratedControl3.0/
├── config/                           系统、设备、坐标、调度及示例参数
├── src/integrated_control/
│   ├── app.py                        单片/批量主入口与设备生命周期
│   ├── bootstrap.py                  加载配置并组装应用
│   ├── diagnostics_cli.py            人工联调及 dry/gantt 命令入口
│   ├── logging_config.py             标准日志配置辅助函数
│   ├── application/
│   │   ├── scheduler/
│   │   │   ├── scheduler.py          组装调度角色，供 bootstrap 调用
│   │   │   ├── contracts.py          任务、算法输入输出及扩展接口
│   │   │   ├── experiment_manager.py 工艺参数编译为任务图
│   │   │   ├── task_manager.py       任务登记、状态、依赖和超时
│   │   │   ├── viewer.py             Task/Resource/Sample/Device 快照
│   │   │   ├── executer.py           候选预演、一次搜索和任务领取
│   │   │   ├── actor.py              资源占用、动作执行、结果及反馈
│   │   │   ├── algorithm.py          通用串行任务搜索算法
│   │   │   ├── decision_preview.py   FIFO 取片链预演与玻璃工艺建模
│   │   │   ├── feedback.py           通信容错与缓存有效期
│   │   │   └── cli.py                离线 dry 与文本 gantt
│   │   ├── workflows/
│   │   │   ├── zksz.py               完整单片工艺、两步动作与 checkpoint
│   │   │   └── batch_zksz.py         BatchParams 与批量实验运行循环
│   │   ├── calibration/              传感器回零服务
│   │   ├── controller.py             初始化、回零、就绪检查与关闭
│   │   ├── device_manager.py         设备注册与生命周期管理
│   │   ├── device_diagnostics.py     人工设备操作
│   │   ├── safety_supervisor.py      启动安全状态检查
│   │   └── state_store.py            系统状态
│   ├── devices/                      设备抽象接口，包含相机预留接口
│   ├── domain/                       设备状态、结果、枚举和异常
│   └── infrastructure/
│       ├── drivers/native/           真机运动、夹持、移液及工艺驱动
│       ├── transports/               Serial、Modbus RTU、ASCII 通信
│       ├── persistence/              平台校准状态保存
│       └── simulation.py             模拟设备实现
├── tests/                            单元、内存通信测试及独立枚举校验
├── tools/                            架构图生成工具
├── docs/architecture/                当前结构图与历史提案
├── old_code/                         历史代码及其检查点副本
├── pyproject.toml                    包配置和命令入口
└── README.md
```

`workflows` 保存可复用流程和运行循环，不提供独立命令行主入口。设备启动、模式选择和关闭统一由 `app.py` 管理。`scheduler.py` 是调度角色的组装模块，不是另一套主运行循环。

## 调度架构与调用关系

调度架构中的六个核心角色可以形象地理解为：

| 角色 | 形象定位 | 当前职责 |
| --- | --- | --- |
| ExperimentManager | 秘书一号 | 接收实验参数，把实验编译成参数明确、带依赖关系的 TaskSpec，并交给 TaskManager 登记。当前 zksz 将每片玻璃拆成 step1 → step2。 |
| TaskManager | 秘书二号 | 保存完整任务清单和状态，维护依赖解锁、领取记录、执行结果与超时；它是 Task View 的状态维护者。 |
| Viewer | 共享视野 | 汇总董事长决策时能看到的 Task、Resource、Sample、Device 四类快照。Viewer 负责存储和提供一致快照；Task 由 TaskManager 维护，资源主要由 Actor 维护，样品事实由批量工作流的 checkpoint 写入，设备状态由 Actor 或批量工作流采集后发布。 |
| Executer | 董事长 | 读取 Viewer，组织候选预演和搜索，决定下一步领取哪个任务。它只做调度决策，不直接操作硬件。 |
| Actor | CEO | 接收已领取任务，预留或释放资源，调用工艺处理器控制设备，并把执行结果交回 TaskManager。当前 Actor 不再进行派发前的二次可行性校验。 |
| Scheduler | 组织装配器 | 创建以上角色和共享锁，把同一个 TaskManager、Viewer、Actor、Executer、ExperimentManager 组装成可供 bootstrap 和工作流使用的系统对象；自身不做调度决策，也不操作硬件。 |

`FifoPreview` 和 `schedule()` 是 Executer 使用的两个决策工具，不是额外的管理角色。FifoPreview 的核心职责是预判断“某个 READY 任务现在作为下一步执行是否仍然可行”：它检查当前资源、FIFO 取片顺序、加热窗口，以及执行该候选后现有取片链是否还能按时完成。为了完成这项判断，它也负责把任务绑定到具体加热位，并提供玻璃工艺的时间和资源模型。`schedule()` 接收这些模型，在通过预演的首步方案中调用所选搜索方法。`algorithm.py` 是保存 `schedule()`、通用约束处理和各搜索方法的代码文件，不是一个独立决策角色。

扩展协议 `ExperimentCompiler`、`TaskHandler`、`DecisionPreview` 及 `TaskSpec`、`TaskRecord`、`TimeLink`、`SchedulingTask`、`ScheduledTask`、`TaskPlan` 定义在 `contracts.py`。`AlgorithmConfig` 定义在 `algorithm.py`。

### 每轮在线决策

1. 查看最新快照和 READY 任务；冷却期间不做决策。
2. `prepare()` 补齐加热位与资源需求；资源检查和工艺 preview 筛选当前可执行候选。
3. 将所有剩余 READY/BLOCKED 任务转换为通用模型，调用一次 `schedule()`。`first_candidates` 是所有通过 FifoPreview 检验的下一步候选。算法生成的任何方案都必须以 first_candidates 中的一个任务开头；确定第一步以后，再从全部尚未完成且依赖、时间和资源约束允许的任务中扩展后续步骤。默认 `lookahead_depth=None`，因此本轮会尝试把方案搜索到全部剩余任务完成；只有显式配置正整数时才限制搜索深度。
4. 在线方案的第一条命令必须在本轮决策时刻 `now` 开始。这项约束是为了保证 Executer 返回的任务能够立刻领取。差分约束在考虑后续任务的最大间隔时，原本可能把整段方案连同第一步一起推迟；例如算法返回“10 秒后先执行 A”也可能在数学上可行，但 Executer 会马上领取 A。把首步固定为 now 后，这类需要等待才能执行的方案会被排除；真正需要等待的任务应由 release_at 或 Preview 在当前轮拒绝，等待后重新决策。
5. `accept()` 在共享锁内完成 Actor 资源预留和 TaskManager 的 `READY → RUNNING` 登记。外部快照看到一致状态；登记失败释放本次预留。
6. Actor 直接执行已领取任务；成功后更新结果、释放非保留资源并解锁后续任务。step1 的加热位保留到实际取片 checkpoint。
7. 本次动作完成后，从最新 View 开始下一轮决策。

### 算法与搜索边界

| 算法 | 搜索方式 | 特点 |
| --- | --- | --- |
| `fifo` | 每层选注册顺序中第一个合法子节点，不回溯。 | 开销小，可能走入后续死路。 |
| `greedy` | 按优先级、截止时间、起始时间、时长选子节点，不回溯。 | 局部决策快，不保证找到所有可行方案。 |
| `exact` | 带剪枝的精确搜索。 | 小实例可求最优，大实例可能超时。 |
| `beam` | 每层保留至多 beam_width 个较优状态。 | 限制规模，但可能剪掉可行分支。 |
| `auto` | 根据任务规模和 exact_task_limit 选择搜索方式。 | 简化选择，仍受时间预算限制。 |

`_solve_*()` 返回搜索节点；`schedule()` 校验输入、建立共享问题、选择求解器并包装 TaskPlan。Executer 直接使用 schedule，已删除逐候选反复搜索的 `rank_candidates()`。

`_children()` 每次尝试把一个任务接到当前搜索节点后面，都会调用 `_times()` 重新计算这个候选任务序列的起止时间。如果 `_times()` 返回 `None`，说明加入该任务后无法同时满足时间约束，这个 child 会被丢弃；如果返回时间表，child 才会进入下一层搜索。

在线路径现在默认完整搜索：Executer 仍调用 `schedule(..., horizon=config.lookahead_depth)`，但默认配置为 `None`，目标深度就是全部剩余任务数。求解器只有生成覆盖全部剩余任务的方案，才会向 Executer 返回可行结果。Executer 仍然只执行方案第一步；该任务完成后，再根据真实 View 对全部剩余任务重新规划。为了应对任务规模过大，用户仍可显式设置正整数 `lookahead_depth`，此时返回的才是指定深度的可行前缀。

FifoPreview 与完整搜索仍承担不同职责。FifoPreview 在 schedule 之前逐个检查“候选作为当前下一步”是否安全：对于 step1，它检查当前已在台玻璃加上这次新放入玻璃后的完整 FIFO 取片链；对于 step2，它检查是否轮到最早放入的玻璃，以及取完后剩余在台玻璃是否仍能按时取出。schedule 随后只考虑以这些候选开头的方案，并依据通用依赖、资源和时间约束搜索全部剩余任务。这样可以排除“眼前安全，但按照所选搜索策略继续安排后无法完成”的返回方案。

“搜索到底”不等于每种算法都具有完备性。FIFO 和 Greedy 只沿一条选择路径走到底，该路径失败时不会回溯寻找其他顺序；Beam 会剪掉束宽以外的状态；Exact 才会在时间预算内回溯比较所有合法顺序。Auto 根据任务数选择 Exact 或 Beam。完整搜索也仍受 `time_limit_s` 限制，超时不会返回违反硬约束的残缺方案。

离线 dry 是一次性的静态模拟规划。它根据用户输入在时间零点生成全部任务和初始资源状态，只调用一次 `schedule()`，得到一个完整的可行或较优方案后直接输出任务表和甘特图。dry 不执行设备动作，不接收真实设备反馈，也不会在每一步后更新 View 或重新决策。因为它不受“现在必须立刻派发第一步”的在线要求约束，所以不设置 first_candidates，也允许方案在第一项任务前安排必要等待。不同算法对“较优”的保证不同；完整任务集的 Exact 搜索只有在未超时且完成全部比较时，才会标记 `proven_optimal=True`。

## 工艺、资源与 checkpoint

`zksz.py` 提供完整单片 `run()` 和批量使用的 `step1(n, m)` / `step2(n, m)`；编号 n 从 0 开始，m 从 1 开始。

- step1：取玻璃、旋涂、真空闪蒸、上加热台，不在函数内等待退火完成。
- step2：从加热台取玻璃并放回对应原料槽位。
- 单片完整流程在两步之间自行等待；批量循环安排等待和其他玻璃的制备。

领取 step1 时预留加热位，是为了防止另一任务占用同一位置。`placed_at` 记录玻璃实际进入加热流程的时刻，用于计算加热时间，两者含义不同。

批量运行向 ZkszWorkflow 注入 checkpoint 回调，ZkszWorkflow 不导入 batch_zksz：

1. `_put_glass()` 在释放动作成功后调用 `_checkpoint_at("placed", pose)`；目标须是当前 step1 的加热位。
2. `_pick_glass()` 在夹持并抬起夹爪后调用 `_checkpoint_at("picked", pose)`；目标须是当前 step2 的加热位。
3. `_checkpoint_at()` 更新加热器接口占用记录，然后同步调用传入的回调。返回 None 不妨碍回调发布事件。
4. 批量回调更新 Sample View 的位置、placed_at、picked_at 等事实；离台时释放原 step1 请求持有的加热位，检查观察到的在台时长。

当前执行后的在台时长为：

```text
observed_heat_time = picked_at - placed_at
```

checkpoint 在工艺定义的实际放片和离台动作节点同步记录软件时钟，并作为后续决策采用的事实时间。OnlineTiming 中的 offset 不是对 checkpoint 时间的修正，也不表示 checkpoint 不准确；它表示在动作尚未执行时，从 step 开始到实际放片或离台事件之间预计经过的时间范围，用于提前判断方案能否满足加热窗口。

批量循环使用 `ThreadPoolExecutor(max_workers=1)` 执行动作，主线程每约 0.05 秒等待结果并检查任务超时。它用于维持超时监控，没有同时执行多片动作；等待当前动作结束期间不派发下一任务。超时登记不会自动取消硬件动作。

## 配置

扩展名为 `.yaml` 的配置目前按 JSON 语法读取；修改时应继续使用合法 JSON，不能加入普通 YAML 注释或语法。

| 文件 | 用途 |
| --- | --- |
| `system.yaml` | 默认设备模式与预留日志级别。 |
| `devices.yaml` | COM 口、协议、从站地址、运动参数、软限位、容量及设备通信失败宽限。 |
| `coordinates.yaml` | 平台偏移、原料槽位、加热工位及相机模拟目标。 |
| `safety_limits.yaml` | 回零步长、最大搜索步数等限制。 |
| `scheduler.yaml` | 组装时的算法与决策冷却配置。 |
| `recipes.yaml` | 配方配置预留，当前未驱动工艺步骤。 |
| `batch_online_example.json` | 批量工艺参数示例。 |
| `online_timing_example.json` | 在线动作时长上界、实际放片/离台事件相对 step 起始时刻的预计时间差，以及方案可行性判断使用的取片裕量示例。 |
| `batch_dry_example.json` | 离线完整方案计算示例；离台偏移仍须通过 dry 命令参数显式提供。 |

### BatchParams

统一校验 time_step1、time_step2、heat_time_min、heat_time_max、num_glass、num_heater 等参数。动作时长须为有限正数，加热窗满足 `0 <= min <= max`；玻璃数可为 0，加热位数量必须为正数或待推导的 None。离台偏移不属于批次工艺参数，由 OnlineTiming 或 dry 命令显式提供。

在线省略数量时，`resolve()` 从 coordinates.yaml 的 glass_platform.slots 和 stations.heater 推导数量，再次校验。dry 不加载设备坐标，需要 JSON 或命令行给出数量；不用配置文件时采用 CLI 自带的小型演示参数。

BatchParams 仍保留 method、beam_width、time_limit 兼容字段；`to_dict()` 只导出工艺字段。在线入口使用显式构造的 AlgorithmConfig，不依靠 BatchParams 的默认算法。

### 在线时间与算法参数

- `step1_bound_s` / `step2_bound_s`：预演采用的动作耗时上界。
- `heat_min_s` / `heat_max_s`：物理在台时间窗，须与 BatchParams 的窗口一致。
- `put_offset_min_s` / `put_offset_max_s`：从 step1 开始到实际放片事件发生的最短和最长时间。这是对尚未执行动作的时间范围预测，不是 checkpoint 的测量误差。两个值由用户根据台架动作耗时预先配置，程序当前不会根据历史动作自动估计、校准或更新。拟执行 step1 时，FifoPreview 将预计放片时刻表示为 `[now + put_offset_min_s, now + put_offset_max_s]`；实际 placed checkpoint 到达后，后续决策直接采用准确记录的 `placed_at`。dry 未显式设置这两个值时，默认二者都等于 `time_step1`，即假设放片发生在 step1 结束时。
- `pickup_offset_min_s` / `pickup_offset_max_s`：从 step2 开始到实际离台事件发生的最短和最长时间，同样是动作执行前的时间范围预测。在线运行从 timing 配置显式读取；dry 要求同时传入两个命令行参数，不再根据 step2 时长或旧的加热口径推导。两个值由用户根据台架动作耗时配置，程序当前不会自动估计。
- `pickup_margin_s`：主要服务于方案可行性判断。FifoPreview 在 `chain_ok()` 和 `planning_model()` 中把允许的最晚预计离台时间提前该数值，从而更早判定某条取片链或搜索方案不可行。程序按照 `latest_step2_start = placed_at + heat_max_s - pickup_offset_max_s - pickup_margin_s` 计算规划用的最晚 step2 开始时刻。例如 `heat_max_s=1200`、`pickup_offset_max_s=20`、`pickup_margin_s=3` 时，预演要求 step2 最晚在放片后 1177 秒开始，预计最晚在 1197 秒离台。该参数不会修改 checkpoint，不会改变实际在台时间的计算，也不会把事后硬上限从 `heat_max_s` 改成 `heat_max_s - pickup_margin_s`；它只收紧预演和调度模型中的可行窗口，设置过大可能使方案被判为不可行。

`app.py` 读取 `online_timing_example.json` 这类文件并构造 `OnlineTiming`，随后把对象传给批量工作流。其参数主要由 `decision_preview.py` 中的 FifoPreview 用于候选预演和调度建模；批量工作流还使用 step1/step2 上界配置任务运行超时，并使用 heat_min_s/heat_max_s 检查 checkpoint 记录的实际在台时间。因此该 JSON 不是由 decision_preview 直接导入，也不只在该文件内使用。
- `method`、`beam_width`、`time_limit_s`、`exact_task_limit`：算法及计算预算。
- `lookahead_depth`：默认为 None，搜索全部剩余任务；显式设置正整数时限制本轮搜索深度。
- `cooldown_s`：领取后暂停新决策，组装默认值为 0.1 秒；不暂停硬件动作。

time_limit_s 约束搜索过程的检查点，不是整个调用严格的墙钟时间上限。校验、快照复制、建模及一次约束求解也会耗时。示例数值用于说明格式，不能代替台架测量。

system.yaml 的 log_level 尚未在主入口接入标准日志；批量事件可用 `--log-path` 单独写入 JSONL。

## 运行方式

### 完整单片流程

```powershell
python -m integrated_control.app --device-mode simulation
```

默认 `--workflow single`，保留完整 zksz。省略 device-mode 会使用系统配置；`integrated-control` 是同一入口的安装命令。

### 批量在线实验

须手动选择算法并提供在线时间参数：

```powershell
python -m integrated_control.app --workflow batch --device-mode simulation --algorithm greedy --batch-config config/batch_online_example.json --timing-config config/online_timing_example.json --log-path runtime_data/batch_events.jsonl
```

也可使用 `integrated-control-batch`，无需再写 workflow batch。主入口在连接前校验必要参数，随后启动控制器、运行批量循环，并在退出时关闭设备。

`--log-path` 用于记录批量实验事件。给出 `runtime_data/batch_events.jsonl` 这类路径时，程序会在领取第一个任务之前自动创建缺失的父目录、创建或打开日志文件，并验证它可以写入；因此不需要手动建立 `runtime_data`。如果目录或文件无法创建，实验会在派发硬件任务之前失败。省略 `--log-path` 时不生成批量事件日志。

日志采用追加写入的 JSONL 格式，不会覆盖已有内容；每行是一个独立 JSON 对象，包含单调时钟时间 `at` 和事件 `event`。当前事件包括：

- `sent`：Executer 已领取任务，包含 `task_id` 和 `request_id`；
- `placed`：玻璃实际放片 checkpoint，包含玻璃编号 `n` 和加热位 `m`；
- `picked`：玻璃实际离台 checkpoint，包含玻璃编号 `n` 和加热位 `m`；
- `finished`：Actor 返回任务结果，包含 `task_id` 和最终 `status`。

`runtime_data/` 已列入 `.gitignore`，运行生成的事件日志和平台状态不会上传到 GitHub。若需要保留某次实验记录，应在清理工作区前另行归档；多次运行使用同一路径时，事件会继续追加到原文件。

搜索参数通过 `--beam-width`、`--search-time-limit`、`--lookahead-depth`、`--exact-task-limit` 调整。省略 `--lookahead-depth` 时搜索全部剩余任务；只有需要主动限制在线计算量时才传入正整数。在线入口的算法由命令显式指定；库调用可使用组装配置或传入 AlgorithmConfig。

### 离线 dry 与 gantt

直接调用诊断 CLI 的离线命令不会创建设备、连接串口或执行回零：

```powershell
python -m integrated_control.diagnostics_cli dry --algorithm exact --num-glass 3 --num-heater 2 --pickup-offset-min-s 0.2 --pickup-offset-max-s 0.8
python -m integrated_control.diagnostics_cli gantt --algorithm beam --num-glass 3 --num-heater 2 --pickup-offset-min-s 0.2 --pickup-offset-max-s 0.8 --time-limit-s 1
python -m integrated_control.diagnostics_cli dry --algorithm beam --batch-config config/batch_dry_example.json --put-offset-min-s 26 --put-offset-max-s 30 --pickup-offset-min-s 0 --pickup-offset-max-s 1 --pickup-margin-s 1 --gantt
python -m integrated_control.diagnostics_cli dry --help
```

dry 复用 ExperimentManager 任务生成、FifoPreview 工艺建模和通用 schedule，计算完整任务集。输出算法、可行性、最优性、超时、makespan 和任务起止时间，没有旧模拟器的动作重放。

gantt 每行表示一个任务，`#` 为执行，`.` 为空闲，不画具体加热位占用泳道。`--cols` 设置宽度（20～240），`dry --gantt` 附带甘特图。

命令行工艺参数覆盖 JSON：`--step1-s`、`--step2-s`、`--heat-min-s`、`--heat-max-s` 等。放片偏移未提供时仍默认发生在 step1 结束；离台偏移没有默认值，dry 必须提供两个 pickup 参数：

```text
--put-offset-min-s / --put-offset-max-s
--pickup-offset-min-s / --pickup-offset-max-s
--pickup-margin-s
```

退出码：0 找到完整方案；1 未找到完整可行方案；2 参数或配置错误。搜索失败可能源于算法剪枝或预算，不能直接视为数学上无解；大批次示例不保证在给定预算内求解成功。

### 人工设备联调

```powershell
integrated-control-debug --mode simulation
integrated-control-debug --mode native_hardware
```

真机诊断器在连接前要求输入 MOVE。进入后输入 help 查看平台移动、点动、回零、偏移、夹爪、移液器、旋涂、腔盖及阀门命令。交互会话也支持 dry/gantt；计算不新增硬件动作，但会话本身可能已连接设备。

## 反馈、扩展与持久化

DeviceState 保持精简：device_id 标识设备；lifecycle 和 activity 描述状态；measurements 保存设备相关数据；fault 保存明确错误；updated_at 表示采集时间；valid 表示整份观察是否可用于决策。目标、实测和软件估计尚未统一成独立、严格的数据模型。

Actor 的反馈容错允许无明确错误的部分数据。短暂通信失败可用缓存，连续失败或缓存过旧才转为不可用；明确故障立即无效。反复发布缓存不能刷新真实采集时间，缺少可选字段也不会把失败动作改判为成功。各驱动接入该机制的覆盖仍需完善。

相机预留 Camera.capture、Camera.locate，并有模拟实现；批量流程提供可选 visual_check，尚未自动接入真实识别结果确认玻璃位置。

扩展实验通常需要新增 ExperimentCompiler、TaskHandler 和工艺 DecisionPreview/model builder。算法继续处理通用 SchedulingTask；设备通过 devices 接口及模拟/真机实现接入。

平台状态保存于 `runtime_data/stage_state.json`，包含 X/Y 偏移和是否位于原点。初始化据此决定是否传感器回零，移动后更新原点状态。文件缺失、损坏或字段无效时采用未确认原点的默认值。X 硬件清零与 Y 的 CiA402 回零模式 0，是传感器寻零以外的驱动操作。

任务图、资源占用和批量进度目前仅在内存中；平台状态文件不提供实验断点续跑。

## 测试与架构资料

```powershell
python -m unittest discover -s tests -v
python -m tests.support.scheduler_crosscheck
```

当前验证通过 108 项测试，另有 30 个确定性边界/随机小实例，每个实例比较五种算法与独立枚举结果。测试使用模拟设备或内存通信，未运行真实硬件。

覆盖入口生命周期、参数校验、通用搜索、首步限制、一次搜索、原子领取、资源释放、冷却、超时和迟到结果、反馈容错、checkpoint、回零持久化及通信寄存器命令。交叉校验只验证相应实例和时间模型，不能证明实际耗时或任意规模实例安全。

当前结构资料位于 `docs/architecture/current_code_structure_2026-10-07/`，包含模块思维导图、调用图、导入图和 XMind。修改模块结构后可运行：

```powershell
python tools/generate_current_code_maps.py
```

图生成工具依赖 Pillow；历史提案及其生成工具另行保留供设计对照。

## 本次 3.0 架构迭代的更新与不足（2026-10-07）

### 已完成的调整

以下记录本轮讨论形成的版本调整，大部分已在此前迭代中完成；本次收尾主要统一代码说明并重写本文。

1. **拆分调度角色。** scheduler 移入 application；ExperimentManager、TaskManager、Viewer、Executer、Actor 分文件实现，由 scheduler.py 组装并接入 bootstrap。工艺编译、状态管理、决策和执行有各自接口。
2. **统一两步工艺。** batch_zksz 使用 zksz 的 step1/step2，ExperimentManager 建立依赖；批量实验不再直接重放旧多段工艺计划。
3. **通用算法。** algorithm.py 保留 FIFO、Greedy、Exact、Beam、Auto；玻璃工艺转换放在实验编译和 preview 层，删除玻璃兼容求解接口。
4. **一次搜索并默认搜索到底。** 删除 rank_candidates；先由 FifoPreview 筛选当前作为下一步可行的候选，再调用一次 schedule。所有方案必须以其中一个候选开头；首步之后，算法按约束扩展其他剩余任务。`lookahead_depth` 默认由 4 改为 None，在线每轮尝试生成覆盖全部剩余任务的方案，同时仍只执行第一步并重新规划。首步必须能在当前时刻执行；正整数限深仍作为可选配置保留。
5. **记录物理动作节点并保守处理不确定结果。** checkpoint 记录实际放片和取片的软件时间，作为计算在台时间的依据。短暂设备通信失败可以在限定时间内使用未过期缓存，明确故障则立即视为无效。如果任务失败或超时后无法确认真实设备和资源状态，系统不会假定资源已经释放；任务已经进入 TIMED_OUT 后，随后到达的成功结果也不会自动把它改回成功，避免用迟到信息掩盖已经触发的超时处置。
6. **保留可视化并清理旧路径。** scheduler/cli.py 提供 dry/gantt，diagnostics_cli 接入；删除 run_plan.py、glass_model.py、旧 params 配置与 scheduler 内部 README，移除旧计划执行及漂移预算路径。BatchParams 同时删除 tail 和 heat_measure；dry 现在必须显式接收离台偏移范围。
7. **整理测试与架构资料。** 合并重复和旧接口测试，保留独立枚举交叉校验；更新模块图、调用图和导入关系图。
8. **统一英文代码说明。** 检查 126 个 Python 文件及 10 个历史 notebook，包括源码、测试、工具及历史检查点副本；Python 文件中的 1,080 个、notebook 中的 132 个类和函数均具备英文 docstring，代码注释统一为英文。保留中文操作提示、业务输出和 notebook 计算输出。注释修改通过去除 docstring 后的语法树比较，未改变执行逻辑。

### 当前不足与后续方向

1. **动作事件偏移仍需台架标定。** 事后检查使用准确 checkpoint 的 `picked_at - placed_at`；预演和 dry 使用动作开始到实际放片/离台事件的预计时间范围，并已删除 tail 与 heat_measure。当前 offset 仍由用户手动提供，软件不会从动作历史中自动估计或校准；dry 未指定放片 offset 时还会假设放片发生在 step1 结束时。后续应使用实测动作数据校准两个范围。
2. **checkpoint 的动作定义必须保持一致。** 当前 placed 定义为释放动作成功，picked 定义为夹持后完成抬升，记录时间作为实际工艺事实使用；offset 预测的是动作开始到这些确定节点的时间差。若以后改变实际放片或离台的动作定义，checkpoint 触发位置、offset 标定和加热统计口径必须同步修改。
3. **冷却和软件开销未完整建模。** preview 和算法未系统计入领取、线程唤醒、通信、状态发布等间隔；硬件超过配置上界会破坏预演结论。需按实测更新时长上界、偏移及裕量，并计入决策间隔。
4. **通用性仍有限。** algorithm 是串行模型，不支持多执行器并行排程；玻璃 preview 仍按 FIFO 取片。虽然现在默认搜索全部剩余任务，但 FIFO/Greedy 不回溯、Beam 会剪枝，搜索失败仍不一定代表数学上无解；完整搜索还可能因时间预算而失败。新工艺或非 FIFO 策略需要新的 preview。
5. **状态发布边界未完全收拢。** Actor 管理资源和执行结果，但 zksz 更新加热器接口，batch checkpoint 直接发布部分样品/设备 View。尚未强制实现“所有状态只能由 Actor 写入”，后续可统一事实发布接口。
6. **超时不等于停止。** 主线程只登记超时，仍等待工作线程返回；设备调用永久阻塞时无法及时退出。需要设备级取消、停止确认、故障处置与资源核实。取消 Actor double check 后，必要互锁依赖具体工作流和驱动，尚未形成完整统一接口。
7. **部分硬件闭环缺失。** 加热台仍是模拟实现，native 模式无真实温控器驱动。真空驱动主要控制腔盖，阀门控制管路，没有完整压力闭环；真实相机识别未接入。平台、夹爪、移液器缺少经设备手册和台架确认的软件急停能力。
8. **保留台架工艺设置。** 单片的部分坐标和参数仍写在 zksz，recipes.yaml 未接入；退火提示与内部测试等待未统一，瓶盖/液体检测存在测试放宽设置。正式工艺应配置化并明确验证条件。
9. **容错、日志和恢复未完成。** 反馈容错未覆盖所有真机采集路径；valid 对整份观察生效，目标/实测/估计未统一区分。标准日志级别未接入主入口，任务状态未持久化，暂不支持实验重启恢复。
10. **验证限于软件。** 现有测试不能替代真机耗时、温控、运动互锁和故障停机试验。以上不足本次未修改执行逻辑，需后续单独实施和验证。
