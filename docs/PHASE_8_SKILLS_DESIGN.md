# Phase 8：Skills 设计文档

日期：2026-06-21

## 1. 目标

Phase 8 的目标是引入 Claude/Codex 风格的 `skills`，让 `drone_agent` 可以复用用户确认过的任务经验和工作流程。

第一版只做一件事：

- 支持项目内置 `drone_agent/skills/` 中的手写 `SKILL.md`。
- runtime 根据用户输入选择 0 或 1 个 skill。
- 将选中的 skill 正文注入本轮 LLM 上下文。
- skill 只指导 Agent 如何调用现有 `tools`，不新增执行入口。

## 2. 核心原则

`drone_agent` 是飞控 agent，不是通用文件操作 agent，所以 skill 体系必须比 nanobot、Codex、Claude Code 更保守。

Phase 8 遵守以下原则：

- `tools/` 仍然是唯一动作执行入口。
- `skills/` 只提供任务方法论、流程、约束和示例。
- skill 不能绕过 `tool_dispatcher.py`。
- skill 不能绕过 HITL、语言介入、超时和起飞前安全门。
- 第一版不支持 skill 自带可执行脚本。
- 第一版不支持从日志自动生成并启用 skill。
- 第一版不支持 workspace skill 覆盖内置 skill。

## 3. Skill 与 Tool 的区别

`tool` 是 LLM 可以调用的原子动作。

例如：

- `takeoff`
- `move`
- `rotate`
- `analyze_view`
- `battery_status`

`skill` 是指导 LLM 如何完成某类任务的说明书。

例如：

- 视觉搜索目标时，先观察，再粗搜索，再精对准。
- 真机低高度试飞时，先查电池和飞行模式，再起飞到低高度。
- 工具失败或置信度低时，停止继续动作并向用户说明。

简单说：

```text
Skill 负责策略
Tool 负责动作
Safety 负责限制
Runtime 负责串联
```

## 4. 参考 nanobot 后的取舍

nanobot 的 skill 体系有几个值得借鉴的点：

- 每个 skill 是独立目录。
- 每个 skill 必须有 `SKILL.md`。
- `SKILL.md` 使用 YAML frontmatter 描述 `name` 和 `description`。
- 正文只在 skill 触发后注入上下文。
- 可以校验 skill 结构，避免 TODO、非法字段和目录名不一致。

但以下能力不适合 `drone_agent` Phase 8 直接照搬：

- 不使用 workspace skill 覆盖内置 skill。
- 不使用 `requires.env` 依赖环境变量。
- 不使用 `summary + path` 让 LLM 自己读取 skill 文件。
- 不启用 `scripts/`。
- 不打包 `.skill` 文件。

原因是 `drone_agent` 当前没有文件读取工具，LLM 不能靠路径自己打开 `SKILL.md`；同时飞控系统必须保持清晰的动作执行链路，不能让 skill 脚本成为第二条控制通道。

## 5. 推荐目录结构

Phase 8 建议增加：

```text
drone_agent/
  skills/
    __init__.py
    loader.py
    selector.py
    validator.py
    visual-search/
      SKILL.md
    real-low-altitude-test/
      SKILL.md
```

说明：

- `loader.py`：扫描和读取内置 skills。
- `selector.py`：根据用户输入和 profile 选择 skill。
- `validator.py`：校验 skill 结构和 frontmatter。
- `visual-search/`：内置视觉搜索流程 skill。
- `real-low-altitude-test/`：内置真机低高度试飞流程 skill。

第一版不增加：

```text
scripts/
assets/
package_skill.py
init_skill.py
```

## 6. SKILL.md 格式

第一版 `SKILL.md` 采用固定结构。

示例：

```yaml
---
name: visual-search
description: 当用户要求寻找、搜索、观察或对准目标时使用，指导 agent 通过 analyze_view、rotate、move 分步完成视觉搜索。
enabled: true
mode: ["sim", "real"]
trigger_keywords: ["寻找", "搜索", "目标", "看见", "对准"]
allowed_tools: ["analyze_view", "rotate", "move", "hover", "timer"]
forbidden_tools: ["disarm"]
requires_confirmation: true
---

# Visual Search

## 使用场景

## 工作流程

## 可调用工具

## 安全约束

## 失败处理

## 反例

## 示例
```

### 6.1 frontmatter 字段

`name`

- 必填。
- 必须和目录名一致。
- 只能使用小写字母、数字和连字符。

`description`

- 必填。
- 用于说明 skill 的作用和触发场景。
- 不允许保留 TODO 占位内容。

`enabled`

- 必填。
- `false` 时不参与选择。

`mode`

- 必填。
- 可选值：`sim`、`real`。
- 当前 profile 不匹配时不参与选择。

`trigger_keywords`

- 必填。
- 第一版 selector 用它做简单关键词匹配。

`allowed_tools`

- 必填。
- 说明该 skill 推荐使用哪些工具。
- 第一版只注入给 LLM 作为约束，不直接替代工具 schema。

`forbidden_tools`

- 可选。
- 说明该 skill 场景下不应主动调用哪些工具。

`requires_confirmation`

- 可选。
- 说明该 skill 涉及飞行动作时应更倾向等待确认。
- 实际 HITL 仍由现有 `human_in_the_loop_for_flight_tools` 控制。

## 7. Skill 选择流程

第一版采用简单、可解释的关键词选择。

流程：

```text
用户输入
  -> selector 读取已启用 skills
  -> 过滤 mode 不匹配的 skill
  -> 用 trigger_keywords 匹配用户输入
  -> 命中 0 个：不注入 skill
  -> 命中 1 个：注入该 skill
  -> 命中多个：选择关键词命中数最多的 skill
```

第一版不做向量检索，也不让 LLM 自己决定读取哪个 skill 文件。

原因：

- 当前 skill 数量少。
- 关键词匹配更容易调试。
- 飞控任务需要可解释的触发路径。

## 8. Skill 注入方式

当前 `runtime.py` 会创建基础 system prompt：

```text
SYSTEM_PROMPT
```

Phase 8 建议新增一个轻量 prompt 构造函数：

```text
build_turn_messages(base_messages, selected_skill)
```

每轮调用 LLM 前，如果选中了 skill，就在本轮消息中注入：

```markdown
# Active Skill

当前用户请求匹配以下 skill。你必须遵守该 skill 的流程和安全约束。

<SKILL.md 正文>
```

注意：

- 不修改全局 `SYSTEM_PROMPT` 常量。
- 不把所有 skills 都长期塞进上下文。
- 每轮最多注入一个 skill。
- skill 注入只影响 LLM 规划，不改变 tool schema。

## 9. 与现有安全机制的关系

Phase 8 不改变安全机制。

现有机制继续生效：

- `human_in_the_loop_for_flight_tools`
- `INTERRUPTED_BY_USER`
- `*_TIMEOUT`
- 飞行工具介入时 hover
- `takeoff()` 内最小起飞前安全门

skill 只能告诉 LLM “应该怎么做”，不能决定“是否绕过安全检查”。

如果 skill 内容和现有安全机制冲突，以现有代码安全机制为准。

## 10. 日志记录

Phase 8 建议记录每轮选中的 skill。

可选方案：

1. 在 `agent_messages.jsonl` 的用户消息事件中增加 `selected_skill`。
2. 在 `task_state.jsonl` 中增加 `selected_skill`。

第一版建议优先记录到 `agent_messages.jsonl`，因为 skill 是本轮 LLM 上下文的一部分，和用户输入、assistant 输出关系更直接。

示例：

```json
{
  "timestamp": "2026-06-21 20:30:10",
  "role": "user",
  "content": "寻找红色椅子",
  "selected_skill": "visual-search"
}
```

## 11. 内置 Skill 建议

### 11.1 visual-search

适用场景：

- 用户要求寻找目标。
- 用户要求观察前方是否有某物。
- 用户要求对准某个目标。

核心流程：

```text
analyze_view
  -> 没看到目标：小步 rotate 粗搜索
  -> 看到目标但不居中：小角度 rotate 微调
  -> 需要靠近：小步 move
  -> 每次动作后重新 analyze_view
```

安全约束：

- 不允许一次性大幅移动。
- 每次移动或旋转后必须重新观察。
- 视觉置信度低时应停止并说明。

### 11.2 real-low-altitude-test

适用场景：

- 真机低高度试飞。
- 用户要求起飞测试、悬停测试、低高度移动测试。

核心流程：

```text
battery_status
  -> flight_mode_status
  -> current_position_status
  -> takeoff 低高度
  -> hover / timer
  -> land
```

安全约束：

- 真机优先低高度。
- 起飞前必须确认状态。
- 异常时优先 hover 或 land。

## 12. 第一版不做的内容

Phase 8 不做：

- 不做 skill creator 自动生成 skill。
- 不从日志自动提炼 skill。
- 不自动写入 `SKILL.md`。
- 不启用 skill 自带脚本。
- 不支持 skill 打包分发。
- 不支持 workspace 覆盖内置 skill。
- 不引入 multi-agent。
- 不引入 async runtime。

这些能力可以留到后续：

- Phase 8.2：skill creator 草稿生成。
- Phase 8.3：用户确认后写入 draft skill。
- Phase 9：multi-agent 与异步 bus。

## 13. 实施顺序

建议按下面顺序实现：

1. 新增 `drone_agent/skills/` 包。
2. 新增 `validator.py`，校验 `SKILL.md`。
3. 新增 `loader.py`，加载内置 skills。
4. 新增 `selector.py`，按关键词选择 skill。
5. 新增 `visual-search/SKILL.md`。
6. 新增 `real-low-altitude-test/SKILL.md`。
7. 修改 runtime/agent loop，在每轮 LLM 调用前注入选中的 skill。
8. 修改日志，记录本轮 `selected_skill`。
9. 更新 `PROJECT_ARCHITECTURE.md` 和 `DRONE_AGENT_SPEC.md`。

## 14. 验收标准

Phase 8 完成后应满足：

- 启动时能加载项目内置 skills。
- 无效 `SKILL.md` 会被清晰拒绝或跳过。
- 用户输入“寻找目标”时能选中 `visual-search`。
- 用户输入“真机低高度试飞”时能选中 `real-low-altitude-test`。
- 没有匹配 skill 的普通对话不注入 skill。
- 每轮最多注入一个 skill。
- tool schema 不因 skill 改变。
- 飞行工具仍然触发 HITL、语言介入和安全门。
- 日志能看到本轮使用了哪个 skill。

## 15. 后续扩展

Phase 8.2 可以再考虑 skill creator。

推荐流程：

```text
读取会话日志
  -> 发现重复任务模式
  -> 生成候选 SKILL.md
  -> 用户 review
  -> 用户确认
  -> 写入 draft skill
  -> 用户显式启用
```

关键限制：

- 自动提炼可以由 Agent 做。
- 正式启用必须由用户确认。
- 初期只生成说明型 `SKILL.md`。
- 如果后期支持脚本，脚本只能做离线分析，不能直接控制无人机。
