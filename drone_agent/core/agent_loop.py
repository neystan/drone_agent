"""管理大模型与工具调用循环。"""

from __future__ import annotations

import json
from typing import Any

from drone_agent.core.safety import should_stop_after_tool_result
from drone_agent.core.tool_dispatcher import dispatch_tool_call
from drone_agent.logging.task_log import log_agent_message
from drone_agent.tools.registry import ToolContext, get_tool_schemas


MAX_TOOL_CALLS_PER_TURN = 50


def agent_loop(
    client: Any,
    model: str,
    messages: list[dict[str, Any]],
    context: ToolContext,
) -> str:
    """执行一轮模型对话，直到得到最终回复或中断。"""
    for _ in range(MAX_TOOL_CALLS_PER_TURN):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=get_tool_schemas(),
            tool_choice="auto",
            temperature=0.0,
        )

        message = response.choices[0].message
        tool_calls = message.tool_calls or []

        if not tool_calls:
            assistant_text = message.content or ""
            print(f"agent> {assistant_text}")
            messages.append({"role": "assistant", "content": assistant_text})
            log_agent_message(context.profile, "assistant", assistant_text)
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
            tool_result = dispatch_tool_call(context, call)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.id,
                    "content": json.dumps(tool_result, ensure_ascii=False),
                }
            )
            if should_stop_after_tool_result(context.profile, tool_result):
                assistant_text = tool_result.get("message", "工具返回需要用户确认。")
                print(f"agent> {assistant_text}")
                log_agent_message(context.profile, "assistant", assistant_text)
                return assistant_text

    assistant_text = "本轮工具调用次数过多，已停止。"
    print(f"agent> {assistant_text}")
    log_agent_message(context.profile, "assistant", assistant_text)
    return assistant_text
