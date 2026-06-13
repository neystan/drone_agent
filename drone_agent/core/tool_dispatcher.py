"""解析并分发模型返回的工具调用。"""

from __future__ import annotations

import json
from typing import Any

from drone_agent.core.safety import (
    EndCurrentTurn,
    confirm_flight_tool,
    requires_human_in_the_loop,
    should_end_turn_after_tool_result,
)
from drone_agent.logging.task_log import log_tool_call
from drone_agent.tools.registry import ToolContext, get_tool_definition


def dispatch_tool_call(context: ToolContext, call: Any) -> dict:
    """解析并执行一次模型返回的工具调用。"""
    tool_name = call.function.name
    raw_arguments = call.function.arguments or "{}"
    print(f"tool> calling {tool_name} args={raw_arguments}")

    definition = get_tool_definition(tool_name)
    if definition is None:
        result = {
            "success": False,
            "error": "UNSUPPORTED_TOOL",
            "message": f"unsupported tool: {tool_name}",
        }
        log_tool_call(
            context.profile,
            tool_name,
            {"raw_arguments": raw_arguments},
            result,
        )
        return result

    try:
        arguments = json.loads(raw_arguments)
    except json.JSONDecodeError as exc:
        result = {
            "success": False,
            "error": "INVALID_TOOL_ARGUMENTS",
            "message": f"failed to parse tool arguments: {exc}",
        }
        log_tool_call(
            context.profile,
            tool_name,
            {"raw_arguments": raw_arguments},
            result,
        )
        return result

    if not isinstance(arguments, dict):
        result = {
            "success": False,
            "error": "INVALID_TOOL_ARGUMENTS",
            "message": "tool arguments must be a JSON object",
        }
        log_tool_call(context.profile, tool_name, arguments, result)
        return result

    if requires_human_in_the_loop(context.profile, tool_name):
        try:
            confirm_flight_tool(tool_name, arguments)
        except EndCurrentTurn as exc:
            result = exc.tool_result or {
                "success": False,
                "error": "HUMAN_IN_THE_LOOP_DECLINED",
                "message": str(exc),
            }
            log_tool_call(context.profile, tool_name, arguments, result)
            raise EndCurrentTurn(str(exc), result) from exc

    result = definition.handler(context, arguments)
    log_tool_call(context.profile, tool_name, arguments, result)
    if should_end_turn_after_tool_result(result):
        raise EndCurrentTurn(
            result.get("message", "当前工具执行超时，本轮已结束。"),
            result,
        )
    return result
