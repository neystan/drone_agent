# drone_agent 架构规划文档

日期：2026-06-09

## 1. 项目目标

`drone_agent` 是一个使用自然语言控制无人机执行任务的 Agent。用户通过 CLI 输入中文或英文任务，Agent 通过 OpenAI 兼容的 Function Calling 选择工具，工具层再通过 ROS2 `rclpy` 和 `px4_msgs` DDS topic 控制 PX4 无人机。

这份文档以 `/download/takeoff.py` 的当前实现作为事实基线。下一阶段的重点不是继续堆新能力，而是把已经验证过的单文件原型整理成一个边界清晰、配置可切换、安全契约明确、后续可持续扩展的 Python 项目。

## 2. 当前实现基线

当前 `/download/takeoff.py` 已经实现了以下能力：

- 基于 `rclpy.node.Node` 的 ROS2 节点。
- PX4 DDS 发布：Offboard 心跳、轨迹 setpoint、VehicleCommand。
- PX4 DDS 订阅：本地位置、飞行状态、电池状态、相机图像。
- OpenAI 兼容 Chat Completion + Function Calling 循环。
- 飞行动作工具：`takeoff`、`land`、`disarm`、`hover`、`return_home`、`rotate`、`move`。
- 状态查询工具：`current_position_status`、`battery_status`、`flight_mode_status`、`timer`。
- 感知工具：`take_photo`、`analyze_view`。
- OpenAI 兼容视觉模型接口，用于图像理解和目标搜索建议。
- 超时后切换 hover，并通过 `requires_user_confirmation` 显式要求用户确认。

当前实现也存在需要工程化处理的问题：

- API key、模型名、base URL 直接硬编码在脚本里。
- ROS2 控制、工具 schema、工具执行、prompt、相机处理、VLM 调用、CLI runtime 混在一个文件中。
- 仿真和真机差异没有通过配置隔离。
- 工具分发是长串 `if call.function.name == ...`。
- 安全策略分散在具体工具函数里，没有统一的安全策略层。

## 3. 核心架构决策

### 3.1 主控技术路线

MVP 主控链路固定为：

```text
CLI -> Agent Loop -> Tools -> Px4Controller -> ROS2 rclpy + px4_msgs -> PX4 uXRCE-DDS
```

当前 MVP 不把 MAVSDK 作为主控路径。MAVSDK 可以作为未来适配器候选，但不进入当前主线实施计划。

### 3.2 仿真与真机

仿真和真机使用同一套核心控制代码。

`sim` 和 `real` 的差异通过 runtime profile 表达，包括：

- ROS 节点名。
- 相机 topic。
- 图片保存路径。
- 日志路径。
- 安全限制。
- 默认人工确认策略。
- 是否启用感知工具。
- LLM / VLM provider 配置。

项目提供两个快捷命令和一个通用命令：

```bash
drone_agent_sim
drone_agent_real
drone_agent --profile sim
drone_agent --profile real
```

`drone_agent_sim` 和 `drone_agent_real` 只是 profile 快捷入口，必须调用同一个 runtime，不允许复制一套仿真控制逻辑和一套真机控制逻辑。

### 3.3 工具层命名

暴露给 LLM Function Calling 的能力统一叫 `tools`，不叫 `skills`。

原因是后续可以把 `skills` 留给更高层的复合技能，例如：

- 搜索目标并靠近。
- 巡检指定区域并拍照。
- 按航线执行检查。
- 完成视觉任务后自动返航和降落。

因此，本项目中：

- `tools/` 表示 LLM 可以直接调用的原子工具。
- 未来的 `skills/` 可以表示由多个 tools 组合出来的高级任务能力。

## 4. 技术栈

- 语言：Python。
- ROS 运行时：ROS2 `rclpy`。
- PX4 消息包：`px4_msgs`。
- PX4 通信：uXRCE-DDS。
- 图像消息：ROS2 `sensor_msgs.msg.Image`。
- 图像转换：`cv_bridge` + OpenCV。
- LLM：OpenAI 兼容 Chat Completions API。
- 当前文本模型兼容方向：DeepSeek 兼容 endpoint。
- VLM：OpenAI 兼容视觉模型接口。
- 当前视觉模型兼容方向：Qwen VL 兼容 endpoint。
- 配置：YAML profiles + 环境变量保存密钥。
- 运行界面：CLI 优先。

MVP 阶段暂不优先做：

- Web UI。
- 多机协同。
- MAVSDK 主控。
- AirSim 相机发布逻辑。
- 复杂自主任务规划器。
- 完整插件市场或技能系统。

## 5. 目标项目结构

```text
drone_agent/
  pyproject.toml
  README.md
  DRONE_AGENT_SPEC.md

  drone_agent/
    __main__.py
    cli.py

    config/
      profiles/
        sim.yaml
        real.yaml
      loader.py
      schema.py

    core/
      runtime.py
      agent_loop.py
      tool_dispatcher.py
      safety.py
      types.py

    px4/
      controller.py
      topics.py
      frame.py
      status.py

    tools/
      flight.py
      perception.py
      status.py
      schemas.py
      registry.py

    llm/
      client.py
      prompts.py

    vision/
      camera.py
      vlm.py
      image_store.py

    logging/
      flight_log.py
      task_log.py

  tests/
    unit/
    integration/
```

## 6. 文件职责说明

### 6.1 项目根目录

`pyproject.toml`

定义项目包名、依赖、Python 版本要求、命令入口。后续应在这里注册 `drone_agent`、`drone_agent_sim`、`drone_agent_real`。

`README.md`

面向使用者的快速启动文档。应说明仿真启动、真机启动、环境变量配置、常见问题和安全提醒。

`DRONE_AGENT_SPEC.md`

本架构规划文档。后续拆分代码、确定阶段任务和验收标准时，以这份文档为主参考。

### 6.2 入口层

`drone_agent/__main__.py`

支持 `python -m drone_agent` 启动。它只负责调用 `cli.py`，不包含飞控逻辑、LLM 逻辑或工具逻辑。

`drone_agent/cli.py`

负责解析命令行参数并启动 runtime。至少支持：

- `--profile sim`
- `--profile real`
- `--task "<自然语言任务>"`
- 不传 `--task` 时进入交互模式

它不直接发布 ROS2 消息，也不直接调用 PX4。

### 6.3 配置层

`drone_agent/config/profiles/sim.yaml`

仿真 profile。配置仿真 ROS 节点名、AirSim 相机 topic、图片保存路径、日志路径、LLM/VLM provider、安全限制等。

`drone_agent/config/profiles/real.yaml`

真机 profile。结构与 `sim.yaml` 一致，但可以使用不同相机 topic、更严格的安全限制、真机日志路径和更严格的人工确认策略。

`drone_agent/config/loader.py`

负责读取 YAML profile、解析环境变量、合并默认值，并返回已经校验过的运行时配置对象。配置错误应该在启动阶段暴露，不能等到飞行过程中才报错。

`drone_agent/config/schema.py`

定义 profile 的数据结构和校验规则。必需字段包括 ROS 节点名、topic 配置、存储路径、LLM 配置、VLM 配置和安全限制。

### 6.4 核心运行层

`drone_agent/core/runtime.py`

运行总控。负责完整生命周期：

- 加载 profile。
- 初始化 ROS2。
- 创建 `Px4Controller`。
- 启动 ROS2 executor 线程。
- 创建 LLM client。
- 进入交互式 CLI 或执行单次任务。
- 退出时关闭 executor、销毁 controller、关闭 ROS2。

`drone_agent/core/agent_loop.py`

负责 OpenAI 兼容 Function Calling 循环。它把用户消息发送给模型，接收 tool calls，交给 dispatcher 执行，把工具结果追加回 messages，直到模型返回最终回复。

`drone_agent/core/tool_dispatcher.py`

工具分发器。负责把模型返回的 tool call 路由到注册过的 Python 函数，替代当前 `execute_tool_call()` 中的长 `if` 分支。它也负责 JSON 参数解析和统一的非法参数错误返回。

`drone_agent/core/safety.py`

统一安全策略层。负责根据 profile 限制校验工具参数，处理超时恢复策略，判断是否需要人工确认，并在某个工具返回 `requires_user_confirmation=true` 后阻止后续飞行动作。

`drone_agent/core/types.py`

公共数据类型。建议包含：

- `RuntimeProfile`
- `SafetyLimits`
- `PositionNED`
- `ToolResult`
- `FlightModeStatus`

### 6.5 PX4 层

`drone_agent/px4/controller.py`

当前 `Px4Controller` 的目标归宿。它只负责 DDS publisher、DDS subscriber、PX4 command、setpoint 发布和飞控状态缓存。

它不应该包含：

- 自然语言逻辑。
- prompt 文本。
- OpenAI client 创建。
- tool schemas。
- VLM 调用。
- CLI 循环。

`drone_agent/px4/topics.py`

集中定义 PX4 topic 名称，例如：

- `/fmu/in/offboard_control_mode`
- `/fmu/in/trajectory_setpoint`
- `/fmu/in/vehicle_command`
- `/fmu/out/vehicle_local_position`
- `/fmu/out/vehicle_status`
- `/fmu/out/battery_status`

相机 topic 不应写死在这里，因为仿真和真机的相机 topic 由 profile 决定。

`drone_agent/px4/frame.py`

坐标系工具。负责 body FRD 到 world NED 的转换，主要服务于相对移动工具。这样可以避免把坐标数学逻辑混在 `move()` 工具里。

`drone_agent/px4/status.py`

PX4 状态解释工具。负责把 `nav_state`、`arming_state` 等 enum 值转换成人能读懂的名称。

### 6.6 Tools 层

`drone_agent/tools/flight.py`

暴露给 LLM 的飞行动作工具：

- `takeoff`
- `land`
- `disarm`
- `hover`
- `return_home`
- `rotate`
- `move`

这些工具依赖 `Px4Controller` 和 `core/safety.py`。它们返回结构化 dict，并保留当前已经确认过的安全字段。

`drone_agent/tools/perception.py`

暴露给 LLM 的感知工具：

- `take_photo`
- `analyze_view`

该模块使用 `vision/camera.py`、`vision/image_store.py` 和 `vision/vlm.py`。它不关心相机帧来自 AirSim 还是真机硬件；这个差异由 profile 决定。

`drone_agent/tools/status.py`

暴露给 LLM 的状态查询和轻量辅助工具：

- `current_position_status`
- `battery_status`
- `flight_mode_status`
- `timer`

这个文件叫 `status.py`，不叫 `system.py`，因为它的职责是状态查询和轻量工具，不是系统控制。

`drone_agent/tools/schemas.py`

集中存放 OpenAI 兼容 function tool schemas。当前 `TAKEOFF_TOOL_SCHEMA`、`MOVE_TOOL_SCHEMA`、`ANALYZE_VIEW_TOOL_SCHEMA` 等常量后续应迁移到这里。

`drone_agent/tools/registry.py`

工具注册表。负责建立 tool name、schema 和 Python 函数之间的映射，也可以根据 profile 禁用某些工具。例如没有配置相机 topic 时，可以禁用感知工具。

### 6.7 LLM 层

`drone_agent/llm/client.py`

根据 profile 创建 OpenAI 兼容 client。API key 必须来自环境变量或本地未提交配置，不能写在源码里。

`drone_agent/llm/prompts.py`

存放 system prompt。当前硬编码在 `takeoff.py` 中的 prompt 后续应迁移到这里，并补充 profile-aware 的安全规则。

### 6.8 Vision 层

`drone_agent/vision/camera.py`

负责相机帧处理。它把 ROS `Image` 消息转换为 OpenCV frame，并缓存最新帧。相机 topic 从 profile 读取。

`drone_agent/vision/vlm.py`

负责 VLM 调用，包括图片编码、视觉 prompt 构造、JSON 提取、结果归一化、置信度归一化、视觉搜索建议动作推导。

`drone_agent/vision/image_store.py`

负责图片和分析帧保存。它生成文件名，确保目录存在，并返回保存路径。

### 6.9 日志层

`drone_agent/logging/flight_log.py`

记录飞行工具调用日志，包括时间、工具名、参数、目标位置、最终位置、安全标记和错误信息。

`drone_agent/logging/task_log.py`

记录 Agent 任务级日志，包括用户输入、模型回复、工具调用序列、工具结果和最终回答。

### 6.10 测试目录

`tests/unit/`

单元测试目录。优先覆盖：

- profile 加载。
- 配置缺失错误。
- body FRD 到 world NED 的坐标转换。
- PX4 enum 名称转换。
- tool dispatcher 路由。
- 安全限制校验。
- 工具返回结构。

`tests/integration/`

集成测试目录。初期应优先使用 mock controller，验证完整任务流程，不强依赖真实 PX4。后续再补充 PX4 SITL 手动验收。

## 7. Runtime Profile 设计

仿真和真机使用同一个 profile schema。

`sim.yaml` 示例：

```yaml
name: sim
mode: simulation

ros:
  node_name: drone_agent_sim
  camera_scene_topic: /airsim_node/PX4/CameraDepth1/Scene

storage:
  photo_save_dir: /home/hw/picture
  analysis_save_dir: /home/hw/picture/analysis_frames
  log_dir: /home/hw/drone_agent_logs/sim

llm:
  base_url: https://api.deepseek.com
  model: deepseek-v4-flash
  api_key_env: DRONE_AGENT_LLM_API_KEY

vlm:
  enabled: true
  base_url: https://dashscope.aliyuncs.com/compatible-mode/v1
  model: qwen3-vl-flash
  api_key_env: DRONE_AGENT_VLM_API_KEY

safety:
  require_confirmation_for_real_flight: false
  max_takeoff_height_m: 10
  max_relative_move_m: 20
  max_vertical_move_m: 10
  max_rotation_deg: 360
  action_timeout_s: 30
  hover_on_timeout: true
  stop_after_requires_confirmation: true
```

`real.yaml` 保持相同结构，但可以更严格：

- 降低最大起飞高度。
- 降低最大相对移动距离。
- 飞行动作默认要求人工确认。
- 使用真机相机 topic。
- 使用真机日志目录。

## 8. 安全契约

每个工具应返回结构化 dict。通用字段包括：

- `success`
- `error`
- `message`
- `requires_user_confirmation`
- `target_position_ned`
- `final_position_ned`
- `flight_mode_status`

不是每个工具都必须包含所有字段。例如 `battery_status` 不需要 `target_position_ned`。但所有飞行动作工具都应保留当前已经确认的目标位置和最终位置契约。

规则：

- Tool schema 负责校验基础输入结构。
- `core/safety.py` 负责校验运行时安全限制。
- `target_position_ned` 只表示预期目标，不代表任务已经完成。
- `final_position_ned` 表示工具结束时实际采样到的位置。
- 如果 `hover_on_timeout=true`，超时恢复应切换 hover。
- 超时或不安全状态下，工具应返回 `requires_user_confirmation=true`。
- 任意工具返回 `requires_user_confirmation=true` 后，`agent_loop.py` 不能继续执行飞行动作，必须等待用户确认。
- 仿真和真机使用同一套安全逻辑，只通过 profile 调整阈值和默认确认策略。
- API key 不能提交到源码中。

## 9. 开发阶段计划

### Phase 0：Spec 对齐

目标：新增本 spec，并把它作为下一阶段主规划依据。

验收标准：

- spec 明确使用 ROS2 `rclpy` + `px4_msgs` DDS 作为主控路径。
- spec 明确 `/download/takeoff.py` 是当前事实基线。
- spec 明确 function-calling 工具目录叫 `tools/`，不叫 `skills/`。
- spec 明确仿真和真机是同一控制链路上的不同 profile。
- spec 明确在架构和配置对齐前，不优先新增能力。

### Phase 1：项目骨架与配置

目标：创建 Python 包骨架、CLI 入口、profile 加载和环境变量密钥读取。

验收标准：

- `drone_agent --profile sim` 能加载 `sim.yaml`。
- `drone_agent --profile real` 能加载 `real.yaml`。
- `drone_agent_sim` 能映射到仿真 profile。
- `drone_agent_real` 能映射到真机 profile。
- 缺失必要配置时，启动阶段给出清晰错误。
- LLM/VLM API key 不再硬编码。

### Phase 2：PX4 控制层迁移

目标：把当前 `Px4Controller`、topic 名称、状态解释、坐标转换迁移到 `px4/`。

验收标准：

- DDS publisher/subscriber 行为与当前原型等价。
- PX4 QoS profile 保持与当前可工作的 DDS 配置兼容。
- body-frame 移动转换逻辑独立并有单元测试。
- controller 初始化可以脱离完整 agent loop 单独检查。

### Phase 3：Tools 与 Agent Loop 迁移

目标：把 tools、tool schemas、dispatcher、prompts、agent loop 迁移到目标模块。

验收标准：

- 当前工具集合保持可用：
  - `takeoff`
  - `land`
  - `disarm`
  - `timer`
  - `hover`
  - `return_home`
  - `current_position_status`
  - `battery_status`
  - `flight_mode_status`
  - `rotate`
  - `move`
  - `take_photo`
  - `analyze_view`
- 工具分发不再使用长串硬编码 `if`。
- 工具返回结构保留 `requires_user_confirmation`、`target_position_ned`、`final_position_ned`。
- system prompt 迁移到 `llm/prompts.py`。

### Phase 4：安全、日志与运行验收

目标：集中安全策略，加入最小日志，并准备仿真和真机入口。

验收标准：

- 超时后按配置触发 hover。
- `requires_user_confirmation=true` 后停止继续执行飞行动作。
- 工具调用写入日志。
- Agent 任务流程写入日志。
- `drone_agent_sim` 可以运行当前仿真控制链路。
- `drone_agent_real` 使用同一代码链路，只通过 profile 区分。

## 10. 测试策略

单元测试优先覆盖：

- 配置加载。
- 环境变量缺失。
- topic 配置校验。
- body FRD 到 world NED 的坐标转换。
- PX4 状态 enum 转换。
- tool dispatcher 路由。
- 安全限制检查。
- 工具返回结构。

集成测试初期使用 mock controller，验证：

- 用户消息到模型回复的流程。
- tool call 分发和结果回填流程。
- 人工确认阻断行为。
- 按 profile 启用或禁用工具。

仿真手动验收覆盖：

- 自然语言起飞。
- 相对移动。
- 旋转。
- 拍照。
- 画面分析。
- 返航。
- 降落。

真机验收必须保守推进：

- 只查询状态。
- 检查位置有效性。
- 检查电池状态。
- 人工确认后低高度起飞。
- hover 和 land。

## 11. 立即下一步

1. 保留当前 `/download/takeoff.py` 作为工作原型，直到新包能运行等价行为。
2. 创建 Python 包骨架和 profile 文件。
3. 把硬编码 API key、模型名、base URL 移入 profile/env 加载。
4. 先迁移 PX4 controller，不改变行为。
5. controller 边界稳定后，再迁移 tools 和 schemas。
6. 补充坐标转换、配置加载、dispatcher 路由、安全决策相关测试。
7. 行为等价后，再考虑更高层复合 skills。
