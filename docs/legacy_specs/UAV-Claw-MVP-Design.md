# UAV-Claw 最小 MVP 设计方案 v2.0

> **版本**: v2.0  
> **更新日期**: 2026-05-21  
> **变更**: 基于头脑风暴更新仿真架构、技能调用机制、异步执行模型、错误处理

---

## 一、核心架构决策

### 1.1 运行环境架构

```
┌─────────────────────────────────────────────────────────────────┐
│                        Windows 主机                              │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  AirSim + UE4                                              │  │
│  │  ├── 车辆仿真（物理引擎、飞行动力学）                       │  │
│  │  ├── 环境仿真（城市/室内/户外场景）                         │  │
│  │  ├── 传感器仿真（摄像头/LiDAR/深度图/IMU）                 │  │
│  │  └── 内置 PX4 飞控桥接（TCP 端口 4560）                    │  │
│  └───────────────────────────────────────────────────────────┘  │
├─────────────────────────────────────────────────────────────────┤
│                    WSL2 (Ubuntu 22.04+)                         │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │  UAV-Claw 控制代码                                         │  │
│  │  ├── Agent 决策循环（LLM 持续思考）                        │  │
│  │  ├── 技能库（Function Calling）                            │  │
│  │  ├── 适配器层（MAVSDK → PX4 SITL）                        │  │
│  │  └── 记忆系统                                              │  │
│  │                                                            │  │
│  │  PX4 SITL（飞控仿真）                                      │  │
│  │  ├── 通过 TCP 4560 连接 AirSim                             │  │
│  │  ├── 通过 MAVLink UDP 14540 暴露控制接口                   │  │
│  │  └── QGC 地面站（可选，调试用）                             │  │
│  └───────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2 仿真技术栈

**核心决策：PX4 SITL + AirSim（不用 Gazebo）**

| 组件 | 技术选择 | 运行位置 | 职责 |
|------|----------|----------|------|
| **飞控仿真** | PX4 SITL | WSL2 | 飞行控制逻辑、MAVLink 通信 |
| **车辆/环境仿真** | AirSim + UE4 | Windows | 物理引擎、环境渲染、传感器模拟 |
| **地面站** | QGroundControl | WSL2 | 调试监视（可选） |
| **控制代码** | UAV-Claw (Python) | WSL2 | Agent 决策、技能执行 |
| **LLM** | OpenAI 兼容 API | 云端 | GPT-4o / DeepSeek |

**为什么不用 Gazebo？**
- AirSim 已经内置了物理引擎，可以替代 Gazebo 的功能
- AirSim 提供 Gazebo 不具备的高质量传感器仿真（摄像头、LiDAR）
- 减少一个仿真环境 = 减少同步复杂度

### 1.3 PX4 SITL 与 AirSim 连接方式

```
控制链路（MAVLink）:
  UAV-Claw → MAVSDK → PX4 SITL → AirSim (TCP 4560)

数据流:
  AirSim 传感器数据 → AirSim RPC → UAV-Claw（后期扩展）
```

#### PX4 SITL 启动配置

```bash
# WSL2 中启动 PX4 SITL（AirSim 模式）
cd PX4-Autopilot
make px4_sitl airsim
```

#### AirSim settings.json（Windows 端）

```json
{
  "SettingsVersion": 1.2,
  "SimMode": "Multirotor",
  "ClockType": "SteppableClock",
  "Vehicles": {
    "Quadrotor": {
      "VehicleType": "Px4Multirotor",
      "UseSerial": false,
      "UdpIp": "127.0.0.1",
      "UdpPort": 14560,
      "ControlPort": 14580
    }
  }
}
```

#### 网络端口分配

| 端口 | 协议 | 方向 | 用途 |
|------|------|------|------|
| **4560** | TCP | PX4 SITL → AirSim | PX4 飞控数据转发 |
| **14540** | UDP | UAV-Claw → PX4 SITL | MAVSDK 控制命令 |
| **14560** | UDP | PX4 SITL → AirSim | MAVLink 遥测数据 |
| **14580** | UDP | AirSim → PX4 SITL | AirSim 控制输入 |

#### WSL2 网络注意事项

```
WSL2 使用 NAT 网络，默认无法直接访问 Windows 端口。

解决方案（二选一）:
1. PX4 SITL 运行在 WSL2 中，AirSim 通过 localhost 访问
   - 需要在 WSL2 中安装 PX4 SITL
   - AirSim settings.json 中 UdpIp 设为 WSL2 的 IP

2. 使用 netsh 端口转发（如果 PX4 在 Windows 侧运行）
   netsh interface portproxy add v4tov4 listenport=4560 listenaddress=0.0.0.0 connectport=4560 connectaddress=<WSL2_IP>
```

### 1.4 技术栈详细选择

| 组件 | 技术选择 | 版本要求 | 用途 |
|------|----------|----------|------|
| **语言** | Python | 3.10+ | 控制代码 |
| **飞控** | PX4 SITL | v1.14+ | 飞行控制仿真 |
| **仿真环境** | AirSim + UE4 | AirSim 1.8+ | 车辆/环境/传感器仿真 |
| **飞控通信** | MAVSDK | 2.0+ | PX4 控制命令 |
| **感知通信** | AirSim RPC | msgpack | 传感器数据（后期） |
| **LLM** | OpenAI 兼容 API | - | GPT-4o / DeepSeek |
| **技能调用** | Function Calling | - | LLM → 技能映射 |
| **记忆存储** | JSON 文件 | - | MVP 阶段简单存储 |

---

## 二、MVP 功能范围

### 2.1 核心功能（必须实现）

#### 技能库（8 个核心技能）

| 技能名 | 功能 | 输入参数 | 输出 |
|--------|------|----------|------|
| `arm` | 解锁电机 | — | success, armed |
| `disarm` | 上锁电机 | — | success, armed |
| `takeoff` | 起飞到指定高度 | altitude: float | actual_altitude, success |
| `land` | 降落到地面 | — | landed_position, success |
| `fly_to` | 飞到目的地 | target_position: [x,y,z], speed: float | arrived_position, success |
| `return_to_launch` | 返航到起飞点 | — | arrived_position, success |
| `get_position` | 获取当前位置 | — | position, altitude, success |
| `get_battery` | 获取电量信息 | — | voltage, percent, success |

#### LLM 驱动的 Agent 决策循环

```
目标输入 → [持续观察状态] → LLM 实时思考 → Function Calling 执行技能 → 反思结果 → 下一轮
                ↑                                                      │
                └──────────── 状态持续反馈 ────────────────────────────┘
```

#### 基础记忆系统

- 对话历史（最近 N 轮）
- 任务状态（当前位置、电量、执行阶段）
- 飞行日志（每次技能执行的结果）

### 2.2 可选功能（MVP 暂不实现）

- ROS2 通信封装
- 多传感器数据融合
- 多机协同
- Web UI
- 安全包络系统
- 被动感知（摄像头/LiDAR 分析）

---

## 三、LLM 集成与技能调用

### 3.1 技能调用机制：Function Calling

**核心决策：使用 OpenAI Function Calling，不使用 Prompt 驱动**

#### 为什么选择 Function Calling？

| 对比项 | Prompt 驱动 | Function Calling（本方案） |
|--------|------------|---------------------------|
| **参数校验** | 手动解析 JSON，易出错 | API 层面自动校验 |
| **类型安全** | 可能出现 `"speed": "很快"` | 强制数值类型 |
| **代码简洁** | 需要大量解析逻辑 | 几行代码即可 |
| **调试体验** | 需要解析原始文本 | API 返回结构化数据 |
| **LLM 兼容** | 所有 LLM | OpenAI / DeepSeek / 部分模型 |

#### Function Calling 工具定义

```python
# llm/function_tools.py

UAV_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "arm",
            "description": "解锁无人机电机。起飞前必须先调用此技能。",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "takeoff",
            "description": "从当前高度往上飞指定米数（相对上升）。起飞前必须先 arm。",
            "parameters": {
                "type": "object",
                "properties": {
                    "altitude": {
                        "type": "number",
                        "description": "目标高度（米），从当前位置往上飞。例如 altitude=3 表示再往上飞3米。"
                    }
                },
                "required": ["altitude"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "fly_to",
            "description": "飞到指定的世界坐标位置。NED 坐标系：x=北(正), y=东(正), z=向下(负值=高空)。",
            "parameters": {
                "type": "object",
                "properties": {
                    "target_position": {
                        "type": "array",
                        "items": {"type": "number"},
                        "description": "[x, y, z] NED 世界坐标(米)。z 越负越高。例: [10, 5, -3] = 北10m东5m离地3m"
                    },
                    "speed": {
                        "type": "number",
                        "description": "飞行速度(m/s)，建议 5-15。默认 8.0"
                    }
                },
                "required": ["target_position"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "land",
            "description": "降落到地面。会在当前位置垂直下降直到落地。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "return_to_launch",
            "description": "返航到起飞点并降落。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_position",
            "description": "获取无人机当前位置坐标和离地高度。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_battery",
            "description": "获取无人机电池电压和剩余电量百分比。",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "task_complete",
            "description": "任务完成。当所有目标都已达成时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "任务完成的简要总结"
                    }
                },
                "required": ["summary"]
            }
        }
    },
]
```

#### Function Calling 调用流程

```
┌──────────────────────────────────────────────────────────────┐
│                   Function Calling 完整流程                    │
│                                                              │
│  1. 构建 messages（system + user + 历史）                      │
│     ↓                                                        │
│  2. 调用 LLM API（附带 tools 定义）                            │
│     client.chat.completions.create(                          │
│       model="gpt-4o",                                        │
│       messages=messages,                                     │
│       tools=UAV_TOOLS,                                       │
│       tool_choice="auto"                                     │
│     )                                                        │
│     ↓                                                        │
│  3. LLM 返回 tool_calls 或文本                                │
│     ├── 返回 tool_calls → 执行对应技能 → 结果反馈给 LLM        │
│     └── 返回文本 → 可能是"任务完成"或解释说明                   │
│     ↓                                                        │
│  4. 把执行结果作为 tool role 消息追加到 messages                 │
│     ↓                                                        │
│  5. 回到步骤 2，进入下一轮决策                                  │
└──────────────────────────────────────────────────────────────┘
```

### 3.2 System Prompt 设计

```python
SYSTEM_PROMPT = """\
你是一架智能无人机 (UAV-1) 的自主决策系统。你通过 Function Calling 控制无人机。

## 你的能力
你可以通过调用以下函数控制无人机：
- arm(): 解锁电机（飞行前必须先执行）
- takeoff(altitude): 从当前高度往上飞指定米数
- fly_to(target_position, speed): 飞到指定 NED 世界坐标
- land(): 降落到地面
- return_to_launch(): 返航到起飞点并降落
- get_position(): 获取当前位置
- get_battery(): 获取电量
- task_complete(summary): 标记任务完成

## 坐标系 (NED)
- x: 正北方向（米）
- y: 正东方向（米）
- z: 向下方向（米），z 越负越高！
- 地面 z ≈ 0
- 飞到离地 3 米：z = -3
- 飞到离地 10 米：z = -10

## 工作方式
你不需要一次规划所有步骤。每一轮只决定"下一步做什么"：
1. 观察当前状态（位置、电量、是否在空中）
2. 决定执行哪个技能
3. 等待技能执行完成
4. 观察结果，决定下一步

## 关键规则
- 每轮只调用一个技能（除了 task_complete）
- 飞行前必须先 arm → takeoff → fly_to
- 任务完成后必须调用 task_complete(summary)
- 不要编造传感器数据
- 如果技能执行失败，分析原因并换策略

## 安全规则
- 电量低于 20% 时应返航
- 电量低于 10% 时应立即降落
- 不要飞超过 120 米高度
- 不要飞超过 500 米距离
"""
```

### 3.3 LLM 调用客户端

```python
# llm/llm_client.py

from openai import OpenAI
import json

class LLMClient:
    """LLM 调用客户端，支持 Function Calling"""

    def __init__(self, api_key: str, base_url: str, model: str):
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    def chat(self, user_message: str, tools: list = None) -> dict:
        """
        与 LLM 对话，支持 Function Calling。

        Returns:
            {"type": "text"|"tool_call", "content": str, "tool_calls": list}
        """
        self.messages.append({"role": "user", "content": user_message})

        response = self.client.chat.completions.create(
            model=self.model,
            messages=self.messages,
            tools=tools,
            tool_choice="auto",
        )

        choice = response.choices[0]

        if choice.message.tool_calls:
            tool_calls = choice.message.tool_calls
            self.messages.append(choice.message.model_dump())
            return {
                "type": "tool_call",
                "tool_calls": [
                    {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments),
                        "id": tc.id,
                    }
                    for tc in tool_calls
                ]
            }

        content = choice.message.content
        self.messages.append({"role": "assistant", "content": content})
        return {"type": "text", "content": content}

    def add_tool_result(self, tool_call_id: str, result: str):
        """将技能执行结果反馈给 LLM"""
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result,
        })
```

---

## 四、异步执行架构

### 4.1 核心问题

**同步设计存在严重问题：**

```
同步设计（有问题）:
  takeoff(altitude=3.0) → 阻塞 15-30 秒 → 下一轮 LLM

问题:
  ❌ LLM 在 15-30 秒内完全无法思考
  ❌ 如果无人机遇到问题（电量不足），无人知道
  ❌ 如果无人机偏离目标，无人纠正
```

### 4.2 正确的架构：LLM 持续思考 + 技能异步执行

```
┌─────────────────────────────────────────────────────────────┐
│                    异步执行架构                               │
│                                                             │
│  ┌───────────────────────────────────────────────────────┐  │
│  │                 主控制循环                              │  │
│  │                                                       │  │
│  │  while 任务未完成:                                     │  │
│  │    1. 获取最新状态（位置、电量、速度）                   │  │
│  │    2. 检查异常事件（低电量、偏离目标）                   │  │
│  │    3. LLM 决策（Function Calling）                     │  │
│  │    4. 执行技能（后台线程，不阻塞）                       │  │
│  │    5. 等待技能完成或超时                                │  │
│  │    6. 记录结果，进入下一轮                              │  │
│  └───────────────────────────────────────────────────────┘  │
│           ↑                    ↑                    ↑        │
│  ┌────────┴────────┐ ┌────────┴────────┐ ┌────────┴──────┐ │
│  │   LLM 决策      │ │   状态监控      │ │  技能执行     │ │
│  │   (每 1-2 秒)   │ │   (每 0.5 秒)  │ │  (后台线程)   │ │
│  └─────────────────┘ └─────────────────┘ └───────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 4.3 执行流程示例

以"起飞 3 米，向前飞 5 米，返航"为例：

```
═══════════════════════════════════════════════════════════════
时间线（异步架构）
═══════════════════════════════════════════════════════════════

T=0.0s  🔄 [第1轮] LLM 决策
        状态: 地面, 电量 100%, 电机未解锁
        LLM 输出: tool_call → arm()
        执行: ✅ 电机已解锁

T=1.0s  🔄 [第2轮] LLM 决策
        状态: 地面, 电机已解锁
        LLM 输出: tool_call → takeoff(altitude=3.0)
        执行: 后台线程启动 takeoff...

T=1.5s  🔄 [第3轮] LLM 决策
        状态: 正在起飞, 高度 0.8m, 电量 99%
        LLM 输出: "等待起飞完成..."

T=3.5s  ✅ takeoff 完成, 到达 3m 高度

T=4.0s  🔄 [第4轮] LLM 决策
        状态: 空中, 高度 3m, 电量 97%
        LLM 输出: tool_call → fly_to(target=[5, 0, -3], speed=5)
        执行: 后台线程启动 fly_to...

T=5.5s  ✅ fly_to 完成, 到达 [5, 0, -3]

T=6.0s  🔄 [第5轮] LLM 决策
        状态: 空中, 位置 [5, 0, -3], 电量 94%
        LLM 输出: tool_call → return_to_launch()
        执行: 后台线程启动返航...

T=10.0s ✅ 返航完成, 回到起飞点

T=10.5s 🔄 [第6轮] LLM 决策
        状态: 空中, 起飞点, 电量 90%
        LLM 输出: tool_call → task_complete(summary="起飞3m→前进5m→返航")

═══════════════════════════════════════════════════════════════
✅ 任务完成！共 6 轮决策，总耗时约 10.5 秒
═══════════════════════════════════════════════════════════════
```

### 4.4 LLM 持续思考 vs 同步等待对比

| 维度 | 同步等待（旧方案） | 持续思考（新方案） |
|------|-------------------|-------------------|
| **LLM 调用频率** | 每 15-30 秒一次 | 每 1-2 秒一次 |
| **状态感知** | 技能执行完才能看到 | 实时感知 |
| **异常响应** | 技能失败后才知道 | 事件驱动，立即响应 |
| **LLM 介入能力** | 无（被阻塞） | 随时可以介入 |
| **安全响应** | 延迟 15-30 秒 | 延迟 0.5-1 秒 |
| **代码复杂度** | 低 | 中 |

---

## 五、错误处理机制

### 5.1 错误分类与处理策略

| 错误类型 | 检测方式 | 处理策略 | 严重程度 |
|----------|----------|----------|----------|
| **JSON 解析失败** | LLM 输出无法解析 | 跳过本轮，LLM 重试 | 低 |
| **技能执行失败** | SkillResult.success=False | LLM 分析原因，换策略 | 中 |
| **同一技能连续失败 3 次** | 计数器检测 | 强制 LLM 换策略 | 高 |
| **电量不足** | get_battery() < 20% | 通知 LLM，建议返航 | 高 |
| **电量严重不足** | get_battery() < 10% | 强制降落 | 紧急 |
| **飞行超时** | 单技能执行 > 60s | 请求停止，返回失败 | 高 |
| **偏离目标** | 位置偏差 > 阈值 | LLM 重新规划路径 | 中 |
| **最大迭代次数** | iteration > max | 紧急返航 | 高 |
| **连接断开** | adapter 检查 | 尝试重连，失败则返航 | 紧急 |

### 5.2 错误处理实现

```python
class ErrorHandler:
    """错误处理器"""

    def __init__(self):
        self.consecutive_failures = {}  # {skill_name: count}
        self.max_consecutive_failures = 3
        self.parse_fail_count = 0
        self.max_parse_failures = 3

    def on_skill_result(self, skill_name: str, result: dict) -> dict:
        """处理技能执行结果，返回增强后的结果"""
        if result.get("success"):
            self.consecutive_failures[skill_name] = 0
            return result

        count = self.consecutive_failures.get(skill_name, 0) + 1
        self.consecutive_failures[skill_name] = count

        if count >= self.max_consecutive_failures:
            result["error_level"] = "critical"
            result["suggestion"] = (
                f"技能 {skill_name} 已连续失败 {count} 次。"
                f"必须换一种完全不同的方法，或者报告 stuck。"
            )
            self.consecutive_failures[skill_name] = 0
        else:
            result["error_level"] = "warning"
            result["suggestion"] = (
                f"技能 {skill_name} 失败 (第{count}次)。请分析原因并换策略。"
            )

        return result

    def on_parse_failure(self) -> bool:
        """处理 LLM 输出解析失败，返回是否应继续"""
        self.parse_fail_count += 1
        if self.parse_fail_count >= self.max_parse_failures:
            return False
        return True

    def on_parse_success(self):
        self.parse_fail_count = 0
```

### 5.3 安全包络（基础版）

```python
class SafetyEnvelope:
    """基础安全包络 — MVP 阶段"""

    MAX_ALTITUDE = 120.0     # 米
    MIN_ALTITUDE = 0.5       # 米
    MAX_DISTANCE = 500.0     # 米
    LOW_BATTERY = 20.0       # %
    CRITICAL_BATTERY = 10.0  # %
    MAX_SKILL_TIMEOUT = 60.0 # 秒

    def check(self, state) -> list:
        """检查安全限制，返回事件列表"""
        events = []
        if state.battery_percent < self.CRITICAL_BATTERY:
            events.append({"level": "emergency", "message": f"电量严重不足: {state.battery_percent}%", "action": "land"})
        elif state.battery_percent < self.LOW_BATTERY:
            events.append({"level": "warning", "message": f"电量偏低: {state.battery_percent}%", "action": "return_to_launch"})
        if state.altitude > self.MAX_ALTITUDE:
            events.append({"level": "warning", "message": f"高度超过限制: {state.altitude}m", "action": "descend"})
        return events
```

---

## 六、项目结构设计

```
uav-claw/
├── core/                          # 核心模块
│   ├── __init__.py
│   ├── agent_loop.py             # Agent 决策循环（异步）
│   ├── safety.py                 # 安全包络
│   └── memory/                   # 记忆系统
│       ├── __init__.py
│       ├── short_term.py         # 短期记忆（会话内）
│       └── flight_log.py         # 飞行日志
│
├── skills/                        # 技能库
│   ├── __init__.py
│   ├── base_skill.py             # 技能基类
│   ├── flight_skills.py          # 飞行技能（8 个核心）
│   └── registry.py               # 技能注册表
│
├── adapters/                      # 适配器层
│   ├── __init__.py
│   ├── sim_adapter.py            # 适配器基类
│   ├── px4_adapter.py            # PX4 SITL 适配器（MAVSDK）
│   ├── mock_adapter.py           # Mock 适配器（测试）
│   └── adapter_manager.py        # 适配器管理器
│
├── llm/                           # LLM 集成
│   ├── __init__.py
│   ├── llm_client.py             # LLM 调用客户端（Function Calling）
│   ├── function_tools.py         # Function Calling 工具定义
│   └── prompt_builder.py         # Prompt 构建器
│
├── config/                        # 配置文件
│   ├── sim_config.yaml           # 仿真配置
│   ├── safety_config.yaml        # 安全配置
│   └── .env.example              # 环境变量示例
│
├── cli.py                         # CLI 入口
├── __main__.py                    # 模块入口
├── requirements.txt               # 依赖
└── README.md                      # 项目说明
```

### 与 v1.0 结构对比

| 变更 | v1.0 | v2.0 | 原因 |
|------|------|------|------|
| `llm_client.py` | 纯文本调用 | Function Calling | 技能调用更可靠 |
| `function_tools.py` | 无 | 新增 | Function Calling 工具定义 |
| `agent_loop.py` | 同步循环 | 异步循环 | LLM 持续思考 |
| `safety.py` | 无 | 新增 | 基础安全检查 |
| `runtime.py` | 技能调度器 | 移除 | 功能合并到 agent_loop |
| `airsim_adapter.py` | 感知适配器 | 移除 | MVP 不需要感知 |

---

## 七、配置管理

### 7.1 仿真配置

```yaml
# config/sim_config.yaml
simulation:
  # 适配器选择
  adapter: px4  # px4 | mock
  
  # PX4 SITL 配置
  px4:
    connection: "udp://0.0.0.0:14540"
    timeout: 30  # 连接超时（秒）
  
  # AirSim 配置（车辆/环境仿真）
  airsim:
    ip: "127.0.0.1"
    udp_port: 4560  # PX4 SITL → AirSim
  
  # 安全参数
  safety:
    max_altitude: 120.0    # 米
    min_altitude: 0.5      # 米
    max_distance: 500.0    # 米（从起飞点）
    low_battery: 20.0      # %
    critical_battery: 10.0 # %
    max_skill_timeout: 60.0  # 秒
```

### 7.2 LLM 配置

```python
# config/llm_config.py
LLM_CONFIG = {
    "provider": "openai",  # openai | deepseek
    "model": "gpt-4o",
    "api_key": os.getenv("LLM_API_KEY"),
    "base_url": os.getenv("LLM_BASE_URL", "https://api.openai.com/v1"),
    "max_tokens": 1000,
    "temperature": 0.3,  # 低温度 = 更确定性的决策
}
```

### 7.3 环境变量

```bash
# .env
LLM_API_KEY=sk-xxx
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
SIM_ADAPTER=px4
PX4_CONNECTION=udp://0.0.0.0:14540
```

---

## 八、开发计划

### Phase 1: 基础框架（1 周）

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 创建项目结构 | 目录和基础文件 | P0 |
| 实现适配器基类 | `sim_adapter.py` | P0 |
| 实现 Mock 适配器 | `mock_adapter.py` | P0 |
| 实现技能基类 | `base_skill.py` | P0 |
| 实现 8 个飞行技能 | `flight_skills.py` | P0 |
| 实现技能注册表 | `registry.py` | P0 |

### Phase 2: Agent 核心（1 周）

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 实现 LLM 客户端 | `llm_client.py` | P0 |
| 定义 Function Calling 工具 | `function_tools.py` | P0 |
| 实现 Agent 循环 | `agent_loop.py` | P0 |
| 实现错误处理 | `error_handler.py` | P1 |
| 实现安全包络 | `safety.py` | P1 |

### Phase 3: 记忆与 CLI（3 天）

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 实现短期记忆 | `short_term.py` | P1 |
| 实现 CLI 界面 | `cli.py` | P1 |
| 实现配置管理 | `config/` | P1 |

### Phase 4: 仿真集成（1 周）

| 任务 | 产出 | 优先级 |
|------|------|--------|
| 实现 PX4 适配器 | `px4_adapter.py` | P0 |
| 配置 PX4 SITL | 仿真环境搭建 | P0 |
| 配置 AirSim | 仿真环境搭建 | P0 |
| 端到端测试 | Mock 模式测试 | P0 |
| 端到端测试 | PX4 SITL 测试 | P1 |

### 开发顺序

```
Phase 1 → Phase 2 → Phase 3 → Phase 4
  ↓           ↓           ↓           ↓
Mock 模式   Mock 模式   Mock 模式   PX4 SITL
  跑通        + LLM       + CLI       + AirSim
```

**关键原则：先用 Mock 模式跑通全流程，再接入真实仿真。**

---

## 九、依赖清单

```txt
# requirements.txt

# 核心依赖
numpy>=1.24.0
pyyaml>=6.0
python-dotenv>=1.0.0

# LLM
openai>=1.0.0

# 通信
mavsdk>=2.0.0

# 可选依赖（后期扩展）
# airsim>=1.8.1  # AirSim RPC（需要 Windows 端安装）
# rclpy          # ROS2（后期扩展）
```

---

## 十、启动流程

### 10.1 环境准备

```bash
# ═══ Windows 端 ═══
# 1. 安装 AirSim + UE4/UE5
# 2. 配置 AirSim settings.json（见 1.3 节）
# 3. 启动 AirSim

# ═══ WSL2 端 ═══
# 1. 安装 PX4 SITL
git clone https://github.com/PX4/PX4-Autopilot.git --recursive
cd PX4-Autopilot
make px4_sitl airsim   # ← 使用 airsim 而不是 gz_x500

# 2. 安装 UAV-Claw
cd /path/to/uav-claw
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 LLM API Key
```

### 10.2 启动 UAV-Claw

```bash
# 方式 1: Mock 模式（不需要仿真环境，推荐先用这个）
SIM_ADAPTER=mock python -m uav_claw

# 方式 2: PX4 SITL 模式
# 终端 1: 启动 PX4 SITL
cd PX4-Autopilot && make px4_sitl airsim

# 终端 2: 启动 UAV-Claw
python -m uav_claw
```

### 10.3 交互示例

```
$ python -m uav_claw

🚁 UAV-Claw v2.0 已启动
📡 适配器: PX4 SITL (MAVSDK)
🤖 LLM: GPT-4o (OpenAI)
🔧 技能调用: Function Calling

>>> 请输入任务目标: 起飞到3米高度，然后向前飞5米，然后返航

═══════════════════════════════════════════════════════════════
🚁 开始任务: 起飞到3米高度，然后向前飞5米，然后返航
═══════════════════════════════════════════════════════════════

🔄 [第1轮] LLM 决策
   📤 执行: arm()
   ✅ 电机已解锁

🔄 [第2轮] LLM 决策
   📤 执行: takeoff(altitude=3.0)
   ⏳ 起飞中... 高度: 0.8m → 1.5m → 2.3m → 3.0m
   ✅ 起飞完成: 高度 3.0m

🔄 [第3轮] LLM 决策
   📤 执行: fly_to(target=[5, 0, -3], speed=5)
   ⏳ 飞行中... 位置: [1.2, 0, -3] → [3.1, 0, -3] → [5.0, 0, -3]
   ✅ 到达目标: 位置 [5.0, 0, -3]

🔄 [第4轮] LLM 决策
   📤 执行: return_to_launch()
   ⏳ 返航中... 位置: [3.5, 0, -3] → [1.2, 0, -3] → [0, 0, 0]
   ✅ 返航完成: 位置 [0, 0, 0]

🔄 [第5轮] LLM 决策
   📤 执行: task_complete(summary="起飞3m→前进5m→返航，全部完成")
   
═══════════════════════════════════════════════════════════════
✅ 任务完成！共 5 轮决策
═══════════════════════════════════════════════════════════════
```

---

## 十一、扩展性设计

### 11.1 后期扩展点

| 扩展方向 | 扩展方式 | 复杂度 | 优先级 |
|----------|----------|--------|--------|
| 新增适配器 | 继承 `SimAdapter` | 低 | — |
| 新增技能 | 继承 `Skill` + 添加 Tool 定义 | 低 | — |
| 感知能力 | AirSim RPC + VLM 分析 | 中 | Phase 2 |
| ROS2 集成 | 实现 `ROS2Adapter` | 中 | Phase 3 |
| 多机协同 | 扩展 AgentLoop 支持多 robot_id | 高 | Phase 4 |
| Web UI | Flask + WebSocket | 中 | Phase 3 |
| 长期记忆 | 接入向量数据库 | 中 | Phase 2 |

### 11.2 技术演进路线

```
Phase 1 (MVP):  PX4 SITL + AirSim + Function Calling
                ├── 飞行控制: MAVSDK → PX4 SITL
                ├── 车辆/环境: AirSim + UE4
                ├── 技能调用: Function Calling
                ├── Agent 循环: 异步持续思考
                └── 记忆系统: JSON 文件
                    ↓
Phase 2:        感知能力
                ├── AirSim RPC 接入传感器数据
                ├── VLM 图像分析（GPT-4o Vision）
                ├── 被动感知（后台持续分析）
                └── 主动感知（LLM 按需触发）
                    ↓
Phase 3:        ROS2 + 多传感器融合
                ├── ROS2Adapter + MAVROS
                ├── 多传感器接入
                ├── DDS 通信
                └── Web UI 控制台
                    ↓
Phase 4:        多机协同
                ├── Commander 架构
                ├── 编队指令
                ├── 状态汇聚
                └── 任务分解
```

---

## 十二、总结

### 核心决策（v2.0）

| 决策项 | 选择 | 原因 |
|--------|------|------|
| **运行环境** | WSL2 + Windows | PX4 在 WSL2，AirSim 在 Windows |
| **仿真方案** | PX4 SITL + AirSim | AirSim 替代 Gazebo，提供传感器仿真 |
| **连接方式** | TCP 4560 (PX4↔AirSim) + UDP 14540 (MAVSDK↔PX4) | 标准连接方式 |
| **技能调用** | Function Calling | 参数校验、类型安全、代码简洁 |
| **执行模型** | 异步持续思考 | LLM 实时监控状态，安全响应快 |
| **架构模式** | 适配器模式 + 模块化技能 | 可扩展、可测试 |

### MVP 范围

- ✅ 8 个核心飞行技能
- ✅ Function Calling 技能调用
- ✅ LLM 异步持续思考
- ✅ 基础错误处理和安全检查
- ✅ 基础上下文记忆
- ✅ CLI 交互界面
- ✅ Mock 模式测试
- ✅ PX4 SITL + AirSim 集成

### 预计工时

| Phase | 内容 | 工时 |
|-------|------|------|
| Phase 1 | 基础框架（Mock 模式跑通） | 1 周 |
| Phase 2 | Agent 核心（LLM + Function Calling） | 1 周 |
| Phase 3 | 记忆与 CLI | 3 天 |
| Phase 4 | 仿真集成（PX4 SITL + AirSim） | 1 周 |
| **总计** | | **约 3.5 周** |

---

*文档版本: v2.0*  
*更新日期: 2026-05-21*  
*变更: 仿真架构、技能调用机制、异步执行模型、错误处理*
