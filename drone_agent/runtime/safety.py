"""集中处理 agent 侧的安全判定。"""

from __future__ import annotations

from typing import Any

from drone_agent.config.schema import RuntimeProfile


FLIGHT_TOOL_NAMES = {
    "takeoff",
    "land",
    "disarm",
    "hover",
    "return_home",
    "rotate",
    "move",
}


class EndCurrentTurn(RuntimeError):
    """用于立即结束当前 agent 执行轮次。"""

    def __init__(self, message: str, tool_result: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.tool_result = tool_result


def requires_human_in_the_loop(profile: RuntimeProfile, tool_name: str) -> bool:
    """判断当前工具和模式是否需要人工确认后才能执行。"""
    if not profile.safety.human_in_the_loop_for_flight_tools:
        return False
    return tool_name in FLIGHT_TOOL_NAMES


def should_end_turn_after_tool_result(result: dict[str, Any]) -> bool:
    """判断工具结果是否应直接结束当前轮。"""
    error = str(result.get("error", "")).strip()
    return error.endswith("_TIMEOUT") or error == "INTERRUPTED_BY_USER"
