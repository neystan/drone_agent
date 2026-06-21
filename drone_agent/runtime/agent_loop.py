"""管理大模型与工具调用循环。"""

from __future__ import annotations

import json
from typing import Any

from drone_agent.logging.task_log import log_agent_message, log_task_state
from drone_agent.runtime.safety import EndCurrentTurn
from drone_agent.runtime.task_state import format_task_state_line
from drone_agent.runtime.tool_dispatcher import dispatch_tool_call
from drone_agent.skills.context import build_active_skill_message
from drone_agent.skills.loader import Skill
from drone_agent.tools.registry import ToolContext, get_tool_schemas


MAX_TOOL_CALLS_PER_TURN = 50


def agent_loop(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    context: ToolContext,
    active_skill: Skill | None = None,
) -> str:
    """执行一轮模型对话，直到得到最终回复或中断。"""
    for _ in range(MAX_TOOL_CALLS_PER_TURN):
        _record_task_state(context, "thinking")
        response = client.chat.completions.create(
            model=model,
            messages=_messages_for_request(messages, active_skill),
            tools=get_tool_schemas(),
            tool_choice="auto",
            temperature=0.0,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            _record_task_state(context, "idle")
            assistant_text = message.content or ""
            print(f"agent> {assistant_text}")
            messages.append({"role": "assistant", "content": assistant_text})
            log_agent_message(context.profile, context.session_id, "assistant", assistant_text)
            return assistant_text

        messages.append(
            {
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": call.id,
                        "type": "function",
                        "function": {
                            "name": call.function.name,
                            "arguments": call.function.arguments,
                        },
                    }
                    for call in tool_calls
                ],
            }
        )

        for call in tool_calls:
            try:
                tool_result = dispatch_tool_call(context, call)
            except EndCurrentTurn as exc:
                if exc.tool_result is not None:
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call.id,
                            "content": json.dumps(exc.tool_result, ensure_ascii=False),
                        }
                    )
                assistant_text = str(exc)
                print(f"agent> {assistant_text}")
                log_agent_message(context.profile, context.session_id, "assistant", assistant_text)
                return assistant_text
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )

    assistant_text = "本轮工具调用次数过多，已停止。"
    print(f"agent> {assistant_text}")
    log_agent_message(context.profile, context.session_id, "assistant", assistant_text)
    return assistant_text


def _messages_for_request(
    messages: list[dict[str, Any]],
    active_skill: Skill | None,
) -> list[dict[str, Any]]:
    """给本轮请求临时追加 active skill，不污染长期消息历史。"""
    skill_message = build_active_skill_message(active_skill)
    if skill_message is None:
        return messages
    return [*messages, skill_message]


def _record_task_state(context: ToolContext, phase: str) -> None:
    """更新当前阶段，并同步打印和落盘。"""
    if context.task_state is None:
        return
    if phase == "thinking":
        context.task_state.set_thinking()
    elif phase == "idle":
        context.task_state.set_idle()
    print(format_task_state_line(context.task_state))
    log_task_state(context.profile, context.session_id, context.task_state)
