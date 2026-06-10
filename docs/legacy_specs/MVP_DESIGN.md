# UAV-Claw 最小 MVP 设计文档（v3 — MAVSDK + DDS 版）

## 一、MVP 目标

构建一个**可独立运行的无人机自主飞行 CLI 系统**，实现：

> 用户输入自然语言指令 → LLM 自主规划技能序列 → 调用技能库执行 → 仿真/真机反馈

**核心验证点**：LLM 能否根据实时状态，正确规划并调度"起飞→飞到目的地→返航→降落"的完整流程。

**设计原则**：
- **MAVSDK + DDS**：使用原生 MAVSDK 实现基础技能库，DDS 作为高速数据通道
- **可充分扩展**：适配器模式 + 模块化技能 + 清晰分层，未来可无缝接入 ROS2、多传感器、多机协同
- **仿真真机一体**：同一套代码，通过适配器切换仿真和真机

---

## 二、MVP 功能清单

### 2.1 技能库（6 个核心技能）

| 技能名 | 功能 | 坐标系 | 输入参数 | 输出 |
|--------|------|--------|----------|------|
| `arm` | 解锁电机 | — | — | `success`, `armed` |
| `takeoff` | 起飞到指定高度 | 机体 | `altitude: float` (相对高度m) | `actual_altitude`, `success` |
| `land` | 降落到地面 | — | — | `landed_position`, `success` |
| `disarm` | 上锁电机 | — | — | `success`, `armed` |
| `fly_to` | 飞到目的地 | **机体坐标系** | `forward: float`, `right: float`, `down: float`, `speed: float` | `arrived_position`, `distance`, `success` |
| `return_to_launch` | 返航到起飞点 | — | — | `arrived_position`, `success` |

**fly_to 坐标系说明**（标准航空机体坐标系 NED）：
- 无人机自身永远是原点 `(0, 0, 0)`
- `forward`：飞控指向方向（机体 X 轴），正=前进，负=后退
- `right`：机体 Y 轴，正=右移，负=左移
- `down`：机体 Z 轴，正=下降，负=上升（NED 约定）
- **有头模式**：无人机保持当前航向飞行，不转向目的地
- 内部需将**机体位移**转换为**世界 NED 坐标**后调用适配器

### 2.2 Agent 自主规划

- LLM 每轮根据**当前状态 + 技能表 + 目标**自主决定下一步
- 支持简单指令（"飞到前面10米"）和复合任务（"起飞、飞到A点、观察、返航"）
- 失败自动重试/换策略，连续失败3次报告 stuck
- 任务完成后自动 report 总结
- **云端 LLM**：通过 OpenAI 兼容 API 调用（支持 GPT-4o、DeepSeek 等）

### 2.3 通信与仿真架构

- **核心通信**：MAVSDK + DDS（uXRCE-DDS）— PX4 原生支持
  - **命令控制**：MAVSDK API（takeoff, land, arm, disarm, goto_location）
  - **状态数据**：DDS topics（vehicle_local_position, battery_status, vehicle_attitude）
  - **备用通道**：MAVLink UDP（心跳, 遥测）
- **仿真模式**：PX4 SITL（通过 MAVSDK 连接）
- **真机模式**：同一套 MAVSDK 代码，改连接串即可
- **Mock 模式**：`MockAdapter` 纯内存模拟，无需任何硬件即可开发测试

**技术选型优势**：
- MAVSDK 是 PX4 官方推荐 SDK，API 最干净
- DDS 亚毫秒延迟，企业级可靠性，原生支持大数据流
- 仿真/真机代码完全一致，零迁移成本

### 2.4 CLI 入口

- **交互式 REPL**：`python -m aerialclaw` 启动，支持循环对话
- **单次执行**：`python -m aerialclaw --task "飞到坐标(5,3,-5)"`
- **模式切换**：`mode ai` / `mode manual` 切换 AI/手动模式
- **内置命令**：`status`、`position`、`battery`、`help`、`quit`
- **状态查看**：`status` / `position` / `battery` 等快捷命令

---

## 三、MVP 架构设计（可扩展）

### 3.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                   CLI (REPL / 单次执行)                  │
│              python -m aerialclaw                       │
├─────────────────────────────────────────────────────────┤
│                  AgentLayer (决策层)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │  AgentLoop   │  │  LLMClient   │  │  ChatMode     │ │
│  │  自主决策循环  │  │  云端LLM调用  │  │  对话+任务解析 │ │
│  └──────────────┘  └──────────────┘  └───────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  SkillLayer (技能层)                     │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────┐ │
│  │ SkillRegistry│  │ FlightSkills │  │ (未来: 感知技能)│ │
│  │ 技能注册/查询  │  │ 6个飞行技能   │  │  软技能/认知技能│ │
│  └──────────────┘  └──────────────┘  └───────────────┘ │
├─────────────────────────────────────────────────────────┤
│                  RuntimeLayer (调度层)                   │
│  ┌──────────────────────────────────────────────────┐  │
│  │  SimpleRuntime — 单步技能调度 + 前置条件检查       │  │
│  └──────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│                  AdapterLayer (适配层 — 可扩展)          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │ MAVSDK   │ │ Mock     │ │ ROS2     │ │ AirSim   │  │
│  │ Adapter  │ │ Adapter  │ │ (预留)   │ │ (备用)   │  │
│  │ 命令+DDS │ │ 纯内存   │ │ +MAVROS  │ │ RPC      │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
├─────────────────────────────────────────────────────────┤
│              CommunicationLayer (通信层)                 │
│  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │    MAVSDK       │  │    DDS (uXRCE-DDS)          │  │
│  │  命令控制 API    │  │  高速状态数据流               │  │
│  │  takeoff/land   │  │  position/battery/attitude  │  │
│  └─────────────────┘  └─────────────────────────────┘  │
├─────────────────────────────────────────────────────────┤
│              HardwareLayer (硬件/仿真层)                 │
│  PX4 SITL (仿真)  │  PX4 飞控 (真机)  │  纯内存 (Mock) │
└─────────────────────────────────────────────────────────┘
```

### 3.2 核心设计模式：适配器解耦

**这是整个架构可扩展的关键**：

```python
# 技能层 — 只调用统一接口，不关心底层实现
adapter = get_adapter()
result = adapter.takeoff(5.0)      # 所有适配器都实现这个方法
result = adapter.fly_to_ned(n, e, d, speed)

# 适配器层 — 每种环境一个实现
class SimAdapter(ABC):             # 抽象基类（接口契约）
    def takeoff(alt) -> ActionResult
    def fly_to_ned(n, e, d, spd) -> ActionResult
    def get_state() -> VehicleState
    ...

class MavsdkAdapter(SimAdapter):   # MAVSDK + DDS（核心）
    def __init__(self):
        self._drone = System()     # MAVSDK System
    
    async def connect(self, connection_str="udp://:14540"):
        await self._drone.connect(system_address=connection_str)
    
    async def takeoff(self, alt):
        await self._drone.action.takeoff()
        await asyncio.sleep(3)
        return ActionResult(True, f"起飞到 {alt}m")
    
    async def fly_to_ned(self, n, e, d, speed):
        # NED → GPS 转换后调用 MAVSDK
        await self._drone.action.goto_location(lat, lon, alt, heading)
        ...

class MockAdapter(SimAdapter):     # 内存模拟（开发测试）
    def takeoff(self, alt):
        self._in_air = True
        ...

# 未来扩展 — 只需新增一个适配器文件
class ROS2Adapter(SimAdapter):     # ROS2 + MAVROS（预留）
    def takeoff(self, alt):
        # 通过 rclpy 发布到 /mavros/cmd/takeoff
        ...
```

**切换环境 = 只改一行配置，技能代码零修改**：

```yaml
# config/sim_config.yaml
simulation:
  adapter: mavsdk   # ← 改这一行即可
  # adapter: mock   # 开发测试
  # adapter: ros2   # 未来真机
```

### 3.3 文件结构（新增 + 复用）

```
AerialClaw-main/
├── __init__.py                     # [新增] 包标识
├── __main__.py                     # [新增] CLI 入口
├── cli.py                          # [新增] CLI 交互逻辑
│
├── mvp/                            # [新增] MVP 核心模块
│   ├── __init__.py
│   ├── agent_loop.py               #   精简版 Agent Loop（自主决策）
│   ├── runtime.py                  #   精简版 Runtime（技能调度）
│   └── skills/
│       ├── __init__.py
│       ├── base_skill.py           #   技能基类（复用现有设计）
│       ├── flight_skills.py        #   6个核心飞行技能
│       └── registry.py             #   技能注册表
│
├── adapters/                       # [复用 + 重写]
│   ├── sim_adapter.py              #   抽象基类（接口契约）  ← 核心
│   ├── adapter_manager.py          #   适配器管理器（单例）
│   ├── mavsdk_adapter.py           #   [重写] MAVSDK + DDS 适配器（核心）
│   ├── mock_adapter.py             #   Mock 适配器（开发测试）
│   ├── px4_adapter.py              #   PX4 SITL 适配器（可选）
│   ├── airsim_adapter.py           #   AirSim 适配器（备用）
│   └── ros2_adapter.py             #   [预留] ROS2 适配器骨架
│
├── llm_client.py                   # [复用] 统一 LLM 调用（云端）
├── config.py                       # [复用] 全局配置
├── config/
│   ├── sim_config.yaml             #   仿真配置
│   └── safety_config.yaml          #   安全配置
│
└── requirements_mvp.txt            # [新增] MVP 最小依赖
```

---

## 四、MVP 需要新增的文件（详细设计）

### 4.1 `__main__.py` — CLI 入口

```python
"""
python -m aerialclaw                          # 交互式 REPL
python -m aerialclaw --task "起飞并飞到前方10米"  # 单次执行
python -m aerialclaw --adapter mock            # 使用 Mock 仿真
python -m aerialclaw --adapter mavsdk          # 使用 MAVSDK（PX4 SITL/真机）
python -m aerialclaw --connection udp://0.0.0.0:14540  # 指定连接串
"""
```

功能：
- argparse 参数解析：`--task`, `--adapter`, `--llm-provider`, `--verbose`
- 交互式 REPL 循环（`>>> ` 提示符）
- 内置命令：`help`, `status`, `position`, `battery`, `mode`, `quit`
- 优雅退出（Ctrl+C → 自动 land + disarm）

### 4.2 `cli.py` — CLI 交互逻辑

```python
class AerialClawCLI:
    def __init__(self, adapter_type, llm_provider, verbose)
    
    # 主入口
    def run_interactive(self)              # REPL 主循环
    def run_task(self, task: str)          # 单次任务执行
    
    # 模式处理
    def _handle_ai_mode(self, user_input)  # AI 模式：调用 AgentLoop
    def _handle_manual_mode(self, user_input)  # 手动模式：直接调用技能
    
    # 内置命令
    def _handle_command(self, cmd: str)    # 解析并执行内置命令
    def _print_status(self)                # 打印无人机状态
    def _print_position(self)              # 打印当前位置
    def _print_battery(self)               # 打印电量
    
    # 辅助
    def _print_result(self, result)        # 格式化输出技能执行结果
    def _print_thinking(self, text)        # 打印 LLM 思考过程
    def _cleanup(self)                     # 退出前安全停机
```

### 4.3 `mvp/agent_loop.py` — 精简版 Agent Loop

核心循环（复用现有 `brain/agent_loop.py` 的设计，去掉复杂依赖）：

```python
class SimpleAgentLoop:
    """
    精简版自主决策循环。
    
    每轮：
    1. 观察：从 adapter 获取当前状态（位置、电量、是否在空中等）
    2. 思考：构建 prompt → LLM 输出 JSON 决策
    3. 行动：调用 runtime 执行技能
    4. 反思：记录结果，更新上下文
    """
    
    def __init__(self, adapter, skill_registry, llm_client, max_iterations=20)
    def run(self, goal: str) -> TaskResult
    
    # 关键方法
    def _observe(self) -> dict              # 获取当前状态摘要
    def _think(self, state, history)        # LLM 决策
    def _act(self, decision)                # 执行技能
    def _reflect(self, action, result)      # 反思记录
    def _build_system_prompt(self)          # 构建系统提示词
    def _build_user_prompt(self, goal, state, history)  # 构建用户提示词
    def _safe_return(self)                  # 安全返航兜底
```

**LLM 输出格式**（JSON）：
```json
{
  "thinking": "我观察到当前位置在起飞点，电量95%，需要飞到目标位置",
  "decision": "act | done | stuck",
  "action": {
    "skill": "fly_to",
    "parameters": {"forward": 10.0, "right": 0.0, "down": 0.0, "speed": 2.0}
  },
  "reflection": null,
  "goal_progress": "刚开始执行，需要先起飞"
}
```

**System Prompt 关键设计**：
- 第一人称身份："你是一架智能无人机"
- 坐标系说明：机体坐标系 (forward=机身前方, right=右方, down=下方)
- 强制规则：每轮只执行一个技能，失败分析后换策略
- 简单指令 vs 复杂任务的区分策略
- 任务完成判定：report 汇报后 → done

### 4.4 `mvp/runtime.py` — 精简版 Runtime

```python
class SimpleRuntime:
    """
    精简版运行时调度器。
    职责：获取技能 → 检查前置条件 → 执行 → 返回结果
    """
    
    def __init__(self, skill_registry, adapter)
    def dispatch_skill(self, skill_name, parameters) -> ExecutionResult
    def _check_preconditions(self, skill) -> list[str]  # 返回失败原因列表
    def _update_world_model(self, result)                # 更新状态
```

### 4.5 `mvp/skills/flight_skills.py` — 6 个核心技能

```python
class Arm(Skill):
    """解锁电机"""
    name = "arm"
    skill_type = "hard"
    preconditions = ["电机未解锁"]
    
    def execute(self, input_data):
        adapter = _get_adapter()
        if adapter.is_armed():
            return SkillResult(success=True, output={"armed": True, "note": "已解锁"})
        result = adapter.arm()
        return SkillResult(success=result.success, output={"armed": result.success})

class Takeoff(Skill):
    """起飞到指定相对高度"""
    name = "takeoff"
    skill_type = "hard"
    preconditions = ["电机已解锁", "在地面上"]
    input_schema = {"altitude": "float, 相对起飞点的高度(米), 默认5.0"}
    
    def execute(self, input_data):
        altitude = input_data.get("altitude", 5.0)
        adapter = _get_adapter()
        result = adapter.takeoff(altitude)
        return SkillResult(success=result.success, 
                          output={"actual_altitude": altitude})

class Land(Skill):
    """降落到地面"""
    name = "land"
    skill_type = "hard"
    preconditions = ["在空中"]
    
    def execute(self, input_data):
        adapter = _get_adapter()
        result = adapter.land()
        return SkillResult(success=result.success, 
                          output={"landed_position": adapter.get_position().to_list()})

class Disarm(Skill):
    """上锁电机"""
    name = "disarm"
    skill_type = "hard"
    preconditions = ["在地面上"]
    
    def execute(self, input_data):
        adapter = _get_adapter()
        result = adapter.disarm()
        return SkillResult(success=result.success, output={"armed": False})

class FlyTo(Skill):
    """飞到目的地（机体坐标系，有头模式）
    
    坐标系说明（标准航空 NED 机体坐标）：
    - 无人机自身永远是原点 (0, 0, 0)
    - forward: 机体 X 轴（飞控指向方向），正=前进，负=后退
    - right:   机体 Y 轴（右方），正=右移，负=左移
    - down:    机体 Z 轴（下方），正=下降，负=上升
    - 有头模式: 无人机保持当前航向，不转向目的地
    """
    name = "fly_to"
    skill_type = "hard"
    preconditions = ["在空中"]
    input_schema = {
        "forward": "float, 机体前方距离(米), 正=前进 负=后退",
        "right": "float, 机体右方距离(米), 正=右移 负=左移",
        "down": "float, 机体下方距离(米), 正=下降 负=上升",
        "speed": "float, 飞行速度(米/秒), 默认2.0"
    }
    
    def execute(self, input_data):
        forward = input_data.get("forward", 0.0)
        right = input_data.get("right", 0.0)
        down = input_data.get("down", 0.0)
        speed = input_data.get("speed", 2.0)
        
        adapter = _get_adapter()
        
        # 获取当前位置和航向
        state = adapter.get_state()
        pos = state.position_ned
        heading = state.heading_deg
        
        # 机体位移 → NED 世界坐标（有头模式：保持航向）
        import math
        heading_rad = math.radians(heading)
        # 旋转矩阵：机体 → 世界
        dn = forward * math.cos(heading_rad) - right * math.sin(heading_rad)
        de = forward * math.sin(heading_rad) + right * math.cos(heading_rad)
        dd = down  # NED: down 正 = 向下
        
        target_ned = [pos.north + dn, pos.east + de, pos.down + dd]
        
        result = adapter.fly_to_ned(target_ned[0], target_ned[1], target_ned[2], speed)
        return SkillResult(
            success=result.success,
            output={
                "arrived_position": adapter.get_position().to_list(),
                "distance_traveled": math.sqrt(dn**2 + de**2 + down**2)
            }
        )

class ReturnToLaunch(Skill):
    """返航到起飞点"""
    name = "return_to_launch"
    skill_type = "hard"
    
    def execute(self, input_data):
        adapter = _get_adapter()
        result = adapter.return_to_launch()
        return SkillResult(success=result.success,
                          output={"arrived_position": adapter.get_position().to_list()})
```

### 4.6 `adapters/mavsdk_adapter.py` — MAVSDK + DDS 适配器（核心）

```python
"""
MAVSDK + DDS 适配器 — MVP 核心。

通信架构：
- 命令控制: MAVSDK API (takeoff, land, arm, disarm, goto_location)
- 状态数据: DDS topics (vehicle_local_position, battery_status, vehicle_attitude)
- 备用通道: MAVLink UDP (心跳, 遥测)

优势：
- 仿真/真机代码完全一致
- PX4 官方推荐 SDK
- DDS 亚毫秒延迟，企业级可靠性
"""
import asyncio
import math
from mavsdk import System
from mavsdk.offboard import VelocityNedYaw
from adapters.sim_adapter import SimAdapter, Position, GPSPosition, VehicleState, ActionResult

class MavsdkAdapter(SimAdapter):
    """MAVSDK + DDS 适配器。"""
    
    def __init__(self):
        self._drone = System()          # MAVSDK System
        self._connected = False
        self._armed = False
        self._in_air = False
        self._position = Position(0, 0, 0)
        self._gps = GPSPosition(0, 0, 0)
        self._heading = 0.0
        self._battery = (12.6, 1.0)
        self._mode = "UNKNOWN"
        self._home_position = None     # 起飞点 GPS
        self._loop = None              # asyncio 事件循环
    
    def connect(self, connection_str="udp://:14540", timeout=30.0):
        """连接 PX4 飞控（SITL 或真机）。"""
        # 在同步上下文中运行异步连接
        self._loop = asyncio.new_event_loop()
        asyncio.run_coroutine_threadsafe(
            self._async_connect(connection_str, timeout),
            self._loop
        ).result()
        return True
    
    async def _async_connect(self, connection_str, timeout):
        """异步连接。"""
        await self._drone.connect(system_address=connection_str)
        
        # 等待连接
        async for state in self._drone.core.connection_state():
            if state.is_connected:
                self._connected = True
                break
        
        # 启动状态监听
        self._start_telemetry()
    
    def _start_telemetry(self):
        """启动 DDS 状态数据监听。"""
        # 监听位置
        asyncio.run_coroutine_threadsafe(
            self._listen_position(), self._loop)
        # 监听电池
        asyncio.run_coroutine_threadsafe(
            self._listen_battery(), self._loop)
        # 监听航向
        asyncio.run_coroutine_threadsafe(
            self._listen_heading(), self._loop)
    
    async def _listen_position(self):
        """从 DDS 监听本地位置。"""
        async for position in self._drone.telemetry.position():
            self._gps = GPSPosition(
                position.latitude_deg,
                position.longitude_deg,
                position.relative_altitude_m
            )
            # 转换为 NED（相对起飞点）
            if self._home_position:
                self._position = self._gps_to_ned(self._gps)
    
    async def _listen_battery(self):
        """从 DDS 监听电池状态。"""
        async for battery in self._drone.telemetry.battery():
            self._battery = (
                battery.voltage_v,
                battery.remaining_percent
            )
    
    async def _listen_heading(self):
        """从 DDS 监听航向。"""
        async for heading in self._drone.telemetry.heading():
            self._heading = heading
    
    def arm(self):
        """解锁电机。"""
        self._run_async(self._drone.action.arm())
        self._armed = True
        return ActionResult(True, "解锁成功")
    
    def disarm(self):
        """上锁电机。"""
        self._run_async(self._drone.action.disarm())
        self._armed = False
        return ActionResult(True, "上锁成功")
    
    def takeoff(self, altitude=5.0):
        """起飞到指定高度。"""
        self._run_async(self._drone.action.takeoff())
        asyncio.sleep(3)  # 等待起飞稳定
        self._in_air = True
        return ActionResult(True, f"起飞到 {altitude}m")
    
    def land(self):
        """降落到地面。"""
        self._run_async(self._drone.action.land())
        self._in_air = False
        return ActionResult(True, "降落成功")
    
    def fly_to_ned(self, north, east, down, speed=2.0):
        """飞到 NED 坐标位置。"""
        # NED → GPS 转换
        target_gps = self._ned_to_gps(Position(north, east, down))
        
        # 调用 MAVSDK goto_location
        self._run_async(self._drone.action.goto_location(
            target_gps.lat,
            target_gps.lon,
            target_gps.alt,
            self._heading
        ))
        
        # 等待到达
        self._wait_arrival(Position(north, east, down), speed)
        
        return ActionResult(True, f"到达 NED({north},{east},{down})")
    
    def return_to_launch(self):
        """返航到起飞点。"""
        self._run_async(self._drone.action.return_to_launch())
        self._in_air = False
        return ActionResult(True, "返航成功")
    
    def hover(self, duration=5.0):
        """悬停。"""
        # 发送速度为 0 的指令
        self._run_async(self._drone.offboard.set_velocity_ned(
            VelocityNedYaw(0.0, 0.0, 0.0, self._heading)
        ))
        asyncio.sleep(duration)
        return ActionResult(True, f"悬停 {duration}s")
    
    def get_state(self) -> VehicleState:
        """获取飞行器状态。"""
        return VehicleState(
            armed=self._armed,
            in_air=self._in_air,
            mode=self._mode,
            position_ned=self._position,
            position_gps=self._gps,
            battery_voltage=self._battery[0],
            battery_percent=self._battery[1] * 100,
            heading_deg=self._heading,
        )
    
    def get_position(self) -> Position:
        return self._position
    
    def get_gps(self) -> GPSPosition:
        return self._gps
    
    def get_battery(self) -> tuple:
        return self._battery
    
    def is_armed(self) -> bool:
        return self._armed
    
    def is_in_air(self) -> bool:
        return self._in_air
    
    def _run_async(self, coro):
        """在事件循环中运行异步协程。"""
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()
    
    def _gps_to_ned(self, gps: GPSPosition) -> Position:
        """GPS → NED（相对起飞点）。"""
        if not self._home_position:
            return Position(0, 0, 0)
        # 简化的 GPS → NED 转换
        dn = (gps.lat - self._home_position.lat) * 111320
        de = (gps.lon - self._home_position.lon) * 111320 * math.cos(math.radians(gps.lat))
        dd = -(gps.alt - self._home_position.alt)
        return Position(dn, de, dd)
    
    def _ned_to_gps(self, pos: Position) -> GPSPosition:
        """NED → GPS（相对起飞点）。"""
        if not self._home_position:
            return GPSPosition(0, 0, 0)
        lat = self._home_position.lat + pos.north / 111320
        lon = self._home_position.lon + pos.east / (111320 * math.cos(math.radians(self._home_position.lat)))
        alt = self._home_position.alt - pos.down
        return GPSPosition(lat, lon, alt)
    
    def _wait_arrival(self, target: Position, speed: float):
        """等待到达目标位置。"""
        threshold = 2.0  # 到达判定距离（米）
        for _ in range(100):  # 最多等待 100 秒
            current = self.get_position()
            dist = math.sqrt(
                (current.north - target.north)**2 +
                (current.east - target.east)**2 +
                (current.down - target.down)**2
            )
            if dist < threshold:
                break
            asyncio.sleep(0.5)
```

### 4.7 `adapters/ros2_adapter.py` — ROS2 适配器骨架（预留）

```python
"""
ROS2 适配器骨架 — 为未来多传感器融合预留。

通信方式：rclpy → ROS2 topics
  - /mavros/state          → 飞行状态
  - /mavros/setpoint_position/local → 位置控制
  - /mavros/cmd/takeoff    → 起飞
  - /mavros/cmd/land       → 降落
  - /camera/image_raw      → 摄像头
  - /lidar/points          → 激光雷达
  - /imu/data              → IMU
"""
from adapters.sim_adapter import SimAdapter, Position, VehicleState, ActionResult

class ROS2Adapter(SimAdapter):
    """ROS2 适配器 — 待实现"""
    
    def __init__(self):
        self._node = None
    
    def connect(self, connection_str="", timeout=10.0):
        # import rclpy
        # rclpy.init()
        # self._node = rclpy.create_node('aerialclaw_bridge')
        raise NotImplementedError("ROS2 适配器待实现")
    
    def takeoff(self, altitude=5.0):
        # 发布到 /mavros/cmd/takeoff
        raise NotImplementedError("ROS2 适配器待实现")
    
    # ... 其他方法同理
```

### 4.8 `requirements_mvp.txt` — MVP 最小依赖

```
# 核心
numpy
pyyaml
python-dotenv

# LLM（云端）
openai

# 通信（MAVSDK + DDS）
mavsdk           # PX4 官方 SDK，支持 MAVLink + DDS

# 可选（Mock 模式不需要 mavsdk）
# flask          # Web UI（MVP 不需要）
# flask-socketio
```

---

## 五、MVP 需要修改的现有文件

### 5.1 `config.py` — 新增 MVP 配置段

```python
# ── MVP 配置 ────────────────────────────────────────────────
MVP_CONFIG = {
    "default_adapter": _env("MVP_ADAPTER", "mavsdk"),     # mavsdk | mock
    "default_llm": _env("MVP_LLM_PROVIDER", "openai"),    # 云端模型
    "llm_model": _env("MVP_LLM_MODEL", "gpt-4o"),         # 具体模型
    "max_iterations": int(_env("MVP_MAX_ITERATIONS", "20")),
    "verbose": _env("MVP_VERBOSE", "true").lower() == "true",
    "connection": _env("MAVSDK_CONNECTION", "udp://:14540"),  # MAVSDK 连接串
}
```

### 5.2 `config/sim_config.yaml` — 新增 MAVSDK 配置

```yaml
simulation:
  backend: px4
  adapter: mavsdk
  
  # MAVSDK 配置
  mavsdk:
    connection: "udp://:14540"        # SITL 默认
    # connection: "udp://0.0.0.0:14540"  # 真机 WiFi
    # connection: "serial:///dev/ttyACM0:57600"  # 真机串口
    vehicle_name: "UAV_1"
    
  # 安全参数（真机必须配置）
  safety:
    max_speed: 10.0          # m/s
    max_altitude: 120.0      # m (CAAC 限制)
    min_altitude: 0.5        # m (防撞地)
    max_distance: 500.0      # m (最远距离)
    min_battery: 15.0        # % → 强制返航
    critical_battery: 5.0    # % → 强制降落
```

---

## 六、MVP 使用流程

### 6.1 启动流程

```bash
# 1. 安装依赖
pip install -r requirements_mvp.txt

# 2. 配置 .env
#    MVP_LLM_PROVIDER=openai
#    LLM_API_KEY=your-api-key
#    LLM_BASE_URL=https://api.openai.com/v1
#    MVP_LLM_MODEL=gpt-4o
#    MVP_ADAPTER=mavsdk    # 或 mock
#    MAVSDK_CONNECTION=udp://:14540  # SITL 默认

# 3. 启动 CLI
python -m aerialclaw
```

### 6.2 交互示例（Mock 模式）

```
╔══════════════════════════════════════════════════════╗
║       🦅 AerialClaw MVP — CLI 控制台                ║
║       Adapter: Mock | LLM: gpt-4o (云端)            ║
╚══════════════════════════════════════════════════════╝

aerialclaw> status
  无人机: UAV_1 | 状态: 地面 | 电量: 100% | 位置: (0, 0, 0) | 航向: 0°

aerialclaw> mode ai

aerialclaw> 起飞并飞到前方10米

🤖 [思考] 当前在地面，需要先解锁、起飞、然后飞到目标位置
📤 [执行] arm → ✅ 解锁成功
📤 [执行] takeoff(altitude=5.0) → ✅ 起飞成功，当前高度5.0m
📤 [执行] fly_to(forward=10.0, right=0.0, down=0.0) → ✅ 到达目标
📤 [执行] land → ✅ 降落成功
📤 [执行] disarm → ✅ 上锁成功

✅ 任务完成！

aerialclaw> position
  位置: NED(10.0, 0.0, -5.0) | 高度: 5.0m | 航向: 0°

aerialclaw> quit
```

### 6.3 交互示例（MAVSDK 模式 — PX4 SITL）

```bash
# 1. 启动 PX4 SITL
cd PX4-Autopilot && make px4_sitl gz_classic

# 2. 启动 MAVSDK Server
mavsdk_server -p 14540 udp://:14540

# 3. 启动 AerialClaw
python -m aerialclaw --adapter mavsdk --verbose

aerialclaw> 飞到右前方5米，上升3米

🤖 [思考] 使用机体坐标系: forward=5.0, right=5.0, down=-3.0(上升=负)
📤 [执行] arm → ✅
📤 [执行] takeoff(altitude=5.0) → ✅
📤 [执行] fly_to(forward=5.0, right=5.0, down=-3.0) → ✅ 到达
📤 [执行] land → ✅
📤 [执行] disarm → ✅

✅ 任务完成！最终位置: NED(x, y, z)
```

### 6.4 交互示例（真机模式）

```bash
# 1. 连接真机（WiFi/串口/数传）
#    修改 .env: MAVSDK_CONNECTION=udp://0.0.0.0:14540

# 2. 启动 AerialClaw
python -m aerialclaw --adapter mavsdk --verbose

# ⚠️ 真机安全提醒：
# - 首次使用请在安全区域测试
# - 确保电池电量 > 50%
# - 保持遥控器开机，随时可以手动接管
```

---

## 七、MVP 依赖关系图

```
__main__.py (CLI 入口)
  └── cli.py (交互逻辑)
        ├── mvp/agent_loop.py (Agent 决策)
        │     ├── llm_client.py (云端 LLM 调用)
        │     ├── mvp/runtime.py (技能调度)
        │     │     └── mvp/skills/registry.py (技能注册)
        │     │           └── mvp/skills/flight_skills.py (6个技能)
        │     └── adapters/ (适配层 — 可扩展)
        │           ├── adapter_manager.py (适配器管理)
        │           ├── mavsdk_adapter.py (MAVSDK + DDS)
        │           └── mock_adapter.py (开发测试)
        └── config.py + .env (配置)

通信层：
  MAVSDK (命令控制) + DDS (状态数据) → PX4 飞控
```

---

## 八、可扩展性设计

### 8.1 扩展点一览

| 扩展方向 | 如何扩展 | 复杂度 |
|----------|----------|--------|
| **新增适配器** | 继承 `SimAdapter`，实现所有方法，注册到 `AdapterManager` | 低 |
| **新增技能** | 继承 `Skill`，实现 `execute()`，注册到 `SkillRegistry` | 低 |
| **接入 ROS2** | 实现 `ROS2Adapter`，通过 rclpy 桥接 PX4 | 中 |
| **多传感器** | 在 `ROS2Adapter` 中订阅 camera/lidar/imu topics | 中 |
| **多机协同** | 扩展 `AgentLoop` 支持多 robot_id，每个机器人独立适配器 | 高 |
| **软技能** | 添加 `SoftSkill` 子类，LLM 动态生成组合策略 | 中 |
| **Web UI** | 在 CLI 基础上添加 Flask + WebSocket 层 | 中 |
| **记忆系统** | 接入 `VectorStore` + `ReflectionEngine` | 中 |
| **DDS 数据流** | 直接订阅 PX4 DDS topics 获取传感器数据 | 中 |

### 8.2 技术演进路线

```
Phase 1 (MVP):  MAVSDK + DDS（当前）
                ├── 命令控制: MAVSDK API
                ├── 状态数据: DDS topics
                └── Mock 模式: 开发测试
                ↓
Phase 2:        ROS2 集成
                ├── ROS2Adapter + MAVROS
                ├── DDS 原生支持（无需 MAVROS）
                └── 多传感器接入
                ↓
Phase 3:        多传感器融合
                ├── /camera/image_raw → VLM 分析
                ├── /lidar/points → 避障
                ├── /imu/data → 姿态估计
                └── /tf → 坐标变换
                ↓
Phase 4:        多机协同
                ├── DDS Discovery → 自动发现
                ├── /fleet/commander → 编队指令
                └── /fleet/telemetry → 状态汇聚
```

### 8.3 适配器注册机制

```python
# adapters/adapter_manager.py
_ADAPTER_REGISTRY = {
    "mock": MockAdapter,
    "mavsdk": MavsdkAdapter,       # 核心: MAVSDK + DDS
    "px4": PX4Adapter,             # 备用: 纯 PX4
    "airsim": AirSimAdapter,       # 备用: AirSim RPC
    "ros2": ROS2Adapter,           # 未来: ROS2 + MAVROS
    "gazebo_direct": GazeboDirectAdapter,  # 未来: Gazebo 直连
}

def init_adapter(adapter_type: str, **kwargs) -> SimAdapter:
    adapter_class = _ADAPTER_REGISTRY.get(adapter_type)
    if not adapter_class:
        raise ValueError(f"未知适配器: {adapter_type}")
    adapter = adapter_class()
    adapter.connect(**kwargs)
    return adapter
```

---

## 九、MVP 开发计划

| 阶段 | 任务 | 预计工时 | 产出 |
|------|------|----------|------|
| **P0** | 创建 `__main__.py` + `cli.py` 框架 | 1天 | CLI 可启动，REPL 可交互 |
| **P0** | 创建 `mvp/skills/flight_skills.py` | 1天 | 6个技能可注册可执行 |
| **P0** | 创建 `mvp/agent_loop.py` | 2天 | Agent 可自主决策 |
| **P0** | 创建 `mvp/runtime.py` | 0.5天 | 技能调度可工作 |
| **P1** | 重写 `mavsdk_adapter.py`（MAVSDK + DDS） | 1.5天 | 核心适配器完成 |
| **P1** | 集成 Mock 模式测试 | 0.5天 | Mock 模式端到端通过 |
| **P1** | 集成 PX4 SITL 测试 | 1天 | SITL 模式端到端通过 |
| **P1** | LLM Prompt 调优 | 1天 | 决策质量达标 |
| **P2** | 错误处理和边界情况 | 1天 | 鲁棒性提升 |
| **P2** | 文档和使用说明 | 0.5天 | README 更新 |
| **总计** | | **~9天** | MVP 可交付 |

---

## 十、MVP 与完整系统的边界

### MVP 包含 ✅
- 6 个核心飞行技能（arm, takeoff, land, disarm, fly_to, return_to_launch）
- 机体坐标系 (forward/right/down) + 有头模式的 fly_to
- LLM 自主规划和决策循环（云端模型）
- CLI 交互界面（REPL + 单次执行）
- **MAVSDK + DDS 通信**（PX4 SITL/真机通用）
- Mock 模式（开发测试）
- 基础状态查询和错误处理
- 适配器模式（可扩展到 ROS2）

### MVP 不包含 ❌（留给后续迭代）
- 感知系统（VLM、LiDAR、摄像头）
- 四层记忆系统（向量存储、反思引擎）
- 软技能进化和自动生成
- Web UI
- 多无人机协调
- 安全包络和审批系统
- 任务日志持久化
- ROS2 适配器实现（仅预留骨架）
- DDS 传感器数据流（仅状态数据）
