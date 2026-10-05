# Integrated Control 3.0

集成式涂布工作站的 Windows 上位机控制程序。项目使用 Python 实现设备抽象、串口通信、运动控制、回零、状态持久化、人工调试和 `zksz` 工艺工作流。

当前仓库同时保留 `old_code/` 历史源码作为迁移依据。正式程序不会导入或执行该目录中的代码。

## 安全提示

当前 `config/system.yaml` 默认配置为 `native_hardware`。运行主程序会连接真实设备，并可能驱动平台、夹爪、移液器、旋涂仪、真空腔盖和电磁阀。

首次运行前应确认：

- COM 口、波特率和从站地址与现场设备一致；
- 运动方向、软限位和工位坐标已经校验；
- 设备运动范围内没有人员或障碍物；
- 硬件急停可用，并有操作人员现场值守。

## 已实现功能

- X/Y 平台绝对移动、相对点动和双轴移动；
- X/Y 传感器回零及回零状态持久化；
- X 轴通过位置清零寄存器设置当前位置为零点；
- Y 轴通过 CiA402 回零模式 0 设置当前位置为零点；
- 夹爪 Z 轴、开合、夹持和旋转控制；
- 移液器 Z 轴、吸液、排液、吸头登记和退吸头；
- 旋涂仪回零和配方执行；
- 真空腔盖与独立电磁阀控制；
- `zksz` 完整工艺工作流；
- 模拟设备模式；
- 面向单设备联调的交互式命令行。

加热台目前只有模拟实现。历史源码没有提供可用的温控器通信协议、寄存器和物理端口定义。

## 项目结构

```text
integratedControl3.0/
├── config/                         # 系统、设备、坐标和安全配置
├── old_code/                       # 历史源码，仅用于查阅和迁移对照
├── src/integrated_control/
│   ├── app.py                      # 主程序入口，只负责启动并调用 zksz
│   ├── bootstrap.py                # 读取配置并组装模拟或真机设备
│   ├── diagnostics_cli.py          # 人工设备调试命令行入口
│   ├── logging_config.py           # 标准日志配置预留
│   ├── application/
│   │   ├── calibration/            # 平台传感器回零服务
│   │   ├── workflows/zksz.py       # zksz 工艺流程和当前工艺坐标
│   │   ├── controller.py           # 系统启动、回零和关闭
│   │   ├── device_diagnostics.py   # 人工调试用设备控制
│   │   ├── device_manager.py       # 设备注册和生命周期管理
│   │   ├── safety_supervisor.py    # 启动安全状态检查
│   │   └── state_store.py          # 系统运行状态
│   ├── devices/                    # Stage、Gripper 等设备接口
│   ├── domain/                     # 状态、结果、枚举和异常
│   ├── infrastructure/
│   │   ├── drivers/native/         # 当前真机驱动
│   │   ├── persistence/            # 平台状态 JSON 存储
│   │   ├── transports/             # 串口、Modbus RTU 和 ASCII 通信
│   │   └── simulation.py           # 模拟设备实现
├── tests/                           # 单元测试和通信集成测试
├── pyproject.toml                   # Python 包、依赖和命令入口
└── README.md
```

### 各层职责

- `application` 负责设备编排、回零服务和工艺工作流；
- `devices` 定义业务代码依赖的设备接口；
- `domain` 保存与具体硬件无关的数据模型和错误类型；
- `infrastructure` 实现真机驱动、模拟设备、通信和状态文件；
- `diagnostics_cli.py` 提供操作人员使用的命令行界面；
- `app.py` 是最外层入口，不包含具体工艺步骤。

## 运行环境

- Windows 10 或 Windows 11；
- Python 3.10 或更高版本；
- 真机模式需要 `pyserial>=3.5`。

## 安装

在项目根目录执行：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[hardware]"
```

如果只使用模拟设备，可以安装基础包：

```powershell
python -m pip install -e .
```

## 配置

配置文件扩展名为 `.yaml`，当前内容使用 JSON 语法读取。JSON 是 YAML 的子集，因此项目不依赖额外的 YAML 解析库。

| 文件 | 当前用途 |
| --- | --- |
| `config/system.yaml` | 选择 `simulation`、`native_hardware` 或 `hardware` 模式 |
| `config/devices.yaml` | 串口、波特率、运动参数、软限位和设备容量 |
| `config/coordinates.yaml` | 平台原点偏移、工位参考坐标和模拟相机目标 |
| `config/safety_limits.yaml` | 传感器回零步长和最大步数 |
| `config/recipes.yaml` | 配方配置预留，当前为空且尚未接入工作流 |

`system.yaml` 中还保留了 `log_level` 字段，但当前主程序尚未调用 `logging_config.py`，因此该字段暂时不会改变程序输出。

当前 `zksz` 工作流使用 [zksz.py](src/integrated_control/application/workflows/zksz.py) 内的工艺坐标和参数。这些值来自 `old_code/brain.py`，尚未改为从 `coordinates.yaml` 动态加载。

## 运行主程序

安装后执行：

```powershell
integrated-control
```

也可以直接运行：

```powershell
python -m integrated_control.app
```

主程序依次执行：

1. 读取配置并创建设备；
2. 初始化全部设备；
3. 根据保存的状态决定是否执行平台传感器回零；
4. 执行 `application/workflows/zksz.py` 中的工作流；
5. 关闭全部设备连接。

## 人工设备调试

模拟模式：

```powershell
integrated-control-debug --mode simulation
```

真机模式：

```powershell
integrated-control-debug --mode native_hardware
```

真机模式会在连接前要求输入 `MOVE`。进入调试器后输入 `help` 可以查看平台、夹爪、移液器、旋涂仪、真空腔盖和电磁阀命令。

## 平台回零与状态文件

平台有两类回零操作：

- 传感器回零：移动 X/Y 轴寻找原点传感器，然后释放传感器并保存原点状态；
- 驱动器当前位置清零：X 轴写入清零寄存器，Y 轴执行 CiA402 回零模式 0。

运行状态保存在：

```text
runtime_data/stage_state.json
```

文件保存 X/Y 软件偏移和平台是否位于原点。平台发生有效移动后，程序会重新计算并更新原点状态。`runtime_data/` 已加入 `.gitignore`，不会作为源码提交。

状态文件不存在、损坏或字段无效时，程序采用安全默认值，将平台视为尚未回零。

## 测试

测试显式使用模拟设备或内存通信，不会读取当前真机模式来启动硬件：

```powershell
python -m unittest discover -s tests -v
```

当前共有 47 项测试，覆盖：

- 应用启动和设备生命周期；
- X/Y 回零与状态持久化；
- Modbus RTU 通信；
- 真机驱动寄存器命令；
- 人工诊断控制；
- `zksz` 完整工作流。

## 已知限制

- 加热台没有真机驱动；
- 真空腔驱动只控制腔盖，抽气由独立电磁阀控制；
- 平台、夹爪和移液器没有经设备手册确认的软件急停寄存器；
- `logging_config.py` 尚未接入主入口，也没有文件日志和日志轮转；
- `zksz` 工艺参数仍写在工作流模块内；
- 更换设备或调整机械结构后，需要重新校验串口、方向、软限位和坐标。
