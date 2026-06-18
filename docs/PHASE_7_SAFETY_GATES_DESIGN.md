# Phase 7：安全门设计文档

日期：2026-06-18

## 1. 目标

Phase 7 的目标是在当前 `drone_agent` 已有安全能力基础上，补齐更细粒度、更适合真机试验的安全门。

Phase 7 不追求复杂自治能力，而是解决一个明确问题：

- LLM 可以调用飞行工具，但飞行工具执行前、中、后都需要有代码级硬限制。
- 仿真和真机可以共用安全门字段，但默认阈值不同。
- 安全门是否启用、阈值是多少，必须由 `config/profiles/*.yaml` 控制。
- 安全门失败时，代码必须直接阻断动作，不能把是否继续交给 LLM 自己判断。

## 2. 当前已经具备的安全能力

当前已经实现：

- `human_in_the_loop_for_flight_tools`：飞行工具执行前 Y/N 人工确认。
- `max_takeoff_height_m`：最大起飞高度限制。
- `max_relative_move_m`：单次水平移动距离限制。
- `max_vertical_move_m`：单次垂直移动距离限制。
- `max_rotation_deg`：单次旋转角度限制。
- `action_timeout_s`：飞行动作超时限制。
- `hover_on_timeout`：超时后进入 hover。
- `INTERRUPTED_BY_USER`：用户语言介入会结束当前轮。
- 飞行工具语言介入时会先发送 hover。
- `*_TIMEOUT` 会结束当前轮，不继续旧任务链路。
- `TaskState` 会记录等待确认、工具执行、工具完成、中断等状态。

这些能力保留，不在 Phase 7 中重写。

## 3. Phase 7 不做什么

Phase 7 不做：

- 不引入 multi-agent。
- 不引入 async runtime。
- 不重写 `Px4Controller`。
- 不把所有安全逻辑抽象成复杂策略引擎。
- 不把安全判断交给 LLM。
- 不引入 Web UI。
- 不做自动任务恢复。

Phase 7 只做“飞行动作前后可执行、可配置、可读的安全门”。

## 4. 设计原则

安全门设计原则：

- 代码硬限制优先于 LLM 决策。
- profile 配置优先于硬编码。
- 真机默认更保守，仿真默认更宽松。
- 安全失败应返回明确错误码。
- 安全失败后是否 hover，要由安全门类型和 profile 决定。
- 尽量复用当前 `runtime/safety.py`、`tools/flight.py`、`px4/status.py`，不新建过重架构。

## 5. 建议新增配置

建议在 `SafetyConfig` 和 `config/profiles/*.yaml` 中扩展：

```yaml
safety:
  human_in_the_loop_for_flight_tools: true
  max_takeoff_height_m: 3
  max_relative_move_m: 5
  max_vertical_move_m: 2
  max_rotation_deg: 180
  action_timeout_s: 20
  hover_on_timeout: true

  preflight_checks_enabled: true
  require_battery_check: true
  min_battery_percent: 30
  require_local_position_valid: true
  require_px4_ready_state: true

  require_camera_ready_before_vision: false
  min_vlm_confidence_for_motion: 0.6
  block_large_motion_on_low_vlm_confidence: true

  check_position_deviation_after_move: true
  max_position_deviation_m: 0.8
  check_yaw_deviation_after_rotate: true
  max_yaw_deviation_deg: 10

  hover_on_safety_violation: true
```

字段说明：

- `preflight_checks_enabled`：是否启用起飞/动作前基础安全检查。
- `require_battery_check`：是否要求电池状态可读。
- `min_battery_percent`：真机最低允许电量。
- `require_local_position_valid`：是否要求本地位置有效。
- `require_px4_ready_state`：是否要求 PX4 状态可读。
- `require_camera_ready_before_vision`：视觉工具前是否要求相机帧可用。
- `min_vlm_confidence_for_motion`：VLM 建议动作可触发移动的最低置信度。
- `block_large_motion_on_low_vlm_confidence`：低置信度时是否禁止大幅移动。
- `check_position_deviation_after_move`：移动后是否检查实际位置偏差。
- `max_position_deviation_m`：允许的最大位置偏差。
- `check_yaw_deviation_after_rotate`：旋转后是否检查 yaw 偏差。
- `max_yaw_deviation_deg`：允许的最大 yaw 偏差。
- `hover_on_safety_violation`：飞行安全门失败时是否进入 hover。

## 6. 安全门分类

### 6.1 启动前安全门

触发时机：

- `drone_agent_sim` / `drone_agent_real` 启动后
- 创建 controller 后
- 第一次执行飞行工具前

检查内容：

- ROS2/PX4 DDS 链路是否可读。
- PX4 状态是否可读。
- 本地位置是否有效。
- 电池状态是否可读。
- 真机电量是否高于阈值。

失败行为：

- 返回 `PREFLIGHT_CHECK_FAILED`。
- 不执行飞行工具。
- 把控制权交还用户。

### 6.2 解锁前安全门

触发时机：

- `takeoff` 内部真正 arm 之前。

检查内容：

- 是否处于允许解锁的 profile。
- 本地位置是否有效。
- 电池电量是否满足阈值。
- 用户是否已通过 HITL 确认。

失败行为：

- 返回 `ARM_SAFETY_CHECK_FAILED`。
- 不发送 arm 命令。

### 6.3 起飞安全门

触发时机：

- `takeoff` 参数校验后。
- arm 前。
- 起飞完成后。

检查内容：

- 起飞高度是否超过 `max_takeoff_height_m`。
- 起飞前本地位置是否有效。
- 起飞后高度是否接近目标。
- 起飞超时是否需要 hover。

失败行为：

- 参数失败：返回 `TAKEOFF_HEIGHT_LIMIT_EXCEEDED`。
- 起飞后偏差过大：返回 `TAKEOFF_POSITION_DEVIATION`。
- 超时：返回 `TAKEOFF_TIMEOUT`，并按 `hover_on_timeout` 决定是否 hover。

### 6.4 移动安全门

触发时机：

- `move` 参数校验后。
- 移动完成后。

检查内容：

- 水平移动是否超过 `max_relative_move_m`。
- 垂直移动是否超过 `max_vertical_move_m`。
- 移动后当前位置与目标位置偏差是否超过 `max_position_deviation_m`。

失败行为：

- 参数失败：不发送 setpoint。
- 移动后偏差过大：返回 `MOVE_POSITION_DEVIATION`，并停止旧任务链路。

### 6.5 旋转安全门

触发时机：

- `rotate` 参数校验后。
- 旋转完成后。

检查内容：

- 单次旋转角度是否超过 `max_rotation_deg`。
- 旋转后 yaw 是否接近目标。

失败行为：

- 参数失败：返回 `ROTATION_LIMIT_EXCEEDED`。
- yaw 偏差过大：返回 `ROTATE_YAW_DEVIATION`，并停止旧任务链路。

### 6.6 感知安全门

触发时机：

- `take_photo` 前。
- `analyze_view` 前。
- 使用 VLM 结果触发移动前。

检查内容：

- 相机帧是否可用。
- VLM 是否启用。
- VLM 置信度是否满足移动阈值。
- 视觉建议动作是否仍满足飞行距离限制。

失败行为：

- 图像未就绪：返回 `IMAGE_NOT_READY`。
- VLM 低置信度：返回 `VLM_CONFIDENCE_TOO_LOW_FOR_MOTION`。
- 不直接触发大幅飞行动作。

### 6.7 运行中安全门

触发时机：

- 飞行动作循环内部。
- 工具执行完成后。

检查内容：

- 是否收到用户语言介入。
- 是否动作超时。
- 是否位置状态突然不可读。
- 是否出现明显偏差。

失败行为：

- 用户介入：返回 `INTERRUPTED_BY_USER`，飞行工具先 hover。
- 超时：返回 `*_TIMEOUT`，按 profile 决定 hover。
- 状态丢失：返回 `PX4_STATE_LOST`，并停止旧任务链路。

## 7. 建议文件改动

建议修改：

```text
drone_agent/config/schema.py
drone_agent/config/loader.py
drone_agent/config/profiles/sim.yaml
drone_agent/config/profiles/real.yaml
drone_agent/runtime/safety.py
drone_agent/runtime/tool_dispatcher.py
drone_agent/tools/flight.py
drone_agent/tools/perception.py
drone_agent/px4/status.py
docs/PROJECT_ARCHITECTURE.md
docs/legacy_specs/DRONE_AGENT_SPEC.md
```

建议新增：

```text
drone_agent/runtime/safety_gates.py
```

`safety_gates.py` 只负责安全门判断，不直接发送飞控命令。

飞控动作仍由 `tools/flight.py` 和 `Px4Controller` 执行。这样可以保持边界清楚：

- `safety_gates.py`：判断能不能做。
- `flight.py`：执行怎么做。
- `controller.py`：负责 ROS2/PX4 DDS 通信。

## 8. 错误码规范

建议 Phase 7 安全门错误码统一使用大写字符串：

```text
PREFLIGHT_CHECK_FAILED
ARM_SAFETY_CHECK_FAILED
TAKEOFF_HEIGHT_LIMIT_EXCEEDED
TAKEOFF_POSITION_DEVIATION
MOVE_DISTANCE_LIMIT_EXCEEDED
MOVE_POSITION_DEVIATION
ROTATION_LIMIT_EXCEEDED
ROTATE_YAW_DEVIATION
IMAGE_NOT_READY
VLM_CONFIDENCE_TOO_LOW_FOR_MOTION
PX4_STATE_LOST
SAFETY_GATE_FAILED
```

返回结构继续沿用当前工具结果格式：

```python
{
    "success": False,
    "error": "SAFETY_GATE_FAILED",
    "message": "reason visible to user",
}
```

如果安全门失败导致 hover，应额外返回：

```python
{
    "hover_command_sent": True,
}
```

## 9. 实施顺序

建议按下面顺序实施：

1. 扩展 `SafetyConfig` 和 profile yaml。
2. 新增 `runtime/safety_gates.py`，只放纯判断函数。
3. 在 `tool_dispatcher.py` 中增加工具执行前安全门检查。
4. 在 `flight.py` 的 `takeoff`、`move`、`rotate` 完成后增加偏差检查。
5. 在 `perception.py` 增加相机与 VLM 置信度安全门。
6. 补充日志字段，把安全门失败原因写入 `tool_calls.jsonl`。
7. 更新项目架构文档和规格文档。

Phase 7 不建议一次性做“所有可能的安全门”。应先落地最小真机关键路径：

- 电池检查。
- 本地位置有效检查。
- 起飞前检查。
- 移动后偏差检查。
- 旋转后偏差检查。

## 10. 验收标准

仿真验收：

- `human_in_the_loop_for_flight_tools=false` 时，仿真仍可直接执行飞行工具。
- 超过 `max_takeoff_height_m` 的起飞会被拒绝。
- 超过 `max_relative_move_m` 的移动会被拒绝。
- 超过 `max_rotation_deg` 的旋转会被拒绝。
- 位置偏差检查失败时，本轮工具链停止。

真机验收：

- `human_in_the_loop_for_flight_tools=true` 时，飞行工具执行前必须 Y/N。
- 电池低于阈值时，拒绝起飞和移动。
- 本地位置不可读时，拒绝 arm/takeoff/move。
- 飞行动作超时或用户介入时，按 profile 发送 hover。
- 安全门失败不会让 LLM 在同一轮继续串行执行后续飞行动作。

日志验收：

- `tool_calls.jsonl` 记录安全门失败的 `error` 和 `message`。
- `task_state.jsonl` 能看到 `interrupted` 或 `tool_failed` 状态。
- 日志不记录 API key。

## 11. 与后续阶段的关系

Phase 7 是后续 `skills` 和 `multi-agent` 的安全基础。

后续无论是单体 Agent、PlannerAgent、MotorAgent，还是由 Skill 生成任务建议，都必须通过同一套安全门：

```text
LLM / Skill / PlannerAgent
  -> tool_dispatcher
  -> safety_gates
  -> tools
  -> Px4Controller
```

这样可以保证后续架构变复杂时，飞控安全约束仍然集中、可配置、可审查。
