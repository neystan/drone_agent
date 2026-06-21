---
name: visual-search
description: 当用户要求寻找、搜索、观察或对准目标时使用，指导 agent 通过 analyze_view、rotate、move 分步完成视觉搜索。
enabled: true
mode: ["sim", "real"]
trigger_keywords: ["寻找", "搜索", "目标", "看见", "观察", "对准"]
allowed_tools: ["analyze_view", "rotate", "move", "hover", "timer"]
forbidden_tools: ["disarm"]
requires_confirmation: true
---

# Visual Search

## 使用场景

用户要求寻找某个目标、判断目标是否出现、观察环境、或让无人机对准目标时使用。

## 工作流程

1. 先调用 `analyze_view` 判断当前画面是否能看到目标。
2. 如果没有看到目标，优先用小步 `rotate` 执行粗搜索。
3. 如果看到目标但目标没有居中，使用小角度 `rotate` 微调方向。
4. 如果需要靠近目标，只允许用小步 `move`。
5. 每次 `rotate` 或 `move` 后必须重新调用 `analyze_view`。

## 可调用工具

推荐工具顺序：

```text
analyze_view -> rotate -> analyze_view -> move -> analyze_view
```

## 安全约束

- 不要一次性大幅移动。
- 不要在没有重新观察的情况下连续移动。
- 视觉结果不确定时，停止继续动作并说明原因。
- 飞行动作仍然必须遵守 HITL、语言介入和安全门。

## 失败处理

如果 `analyze_view` 失败，说明视觉分析失败，不继续飞行动作。

如果目标多次搜索仍未出现，向用户说明当前画面未发现目标，并等待下一步指令。

## 反例

用户只是询问电池、飞行模式、当前位置、起飞或降落时，不使用这个 skill。

## 示例

用户：

```text
寻找红色椅子，并让无人机对准它
```

推荐工具调用顺序：

```text
analyze_view(target_description="红色椅子")
rotate(direction="right", degrees=60)
analyze_view(target_description="红色椅子")
rotate(direction="left", degrees=15)
analyze_view(target_description="红色椅子")
```
