"""管理大模型与工具调用循环。"""

from __future__ import annotations

import json
from typing import Any

try:
    import readline

    readline.parse_and_bind("set bind-tty-special-chars off")
    readline.parse_and_bind("set input-meta on")
    readline.parse_and_bind("set output-meta on")
    readline.parse_and_bind("set convert-meta off")
except ImportError:
    readline = None

from drone_agent.core.safety import should_stop_after_tool_result
from drone_agent.core.tool_dispatcher import dispatch_tool_call
from drone_agent.logging.task_log import log_agent_message
from drone_agent.llm.prompts import SYSTEM_PROMPT
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


def run_interactive_agent(client: Any, model: str, context: ToolContext) -> None:
    """启动交互式命令行对话循环。"""
    messages: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    print("输入自然语言与 agent 对话，输入 exit 退出。")

    while True:
        user_input = input("you> ").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break
        messages.append({"role": "user", "content": user_input})
        log_agent_message(context.profile, "user", user_input)
        agent_loop(client, model, messages, context)
