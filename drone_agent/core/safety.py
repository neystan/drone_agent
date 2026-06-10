"""集中处理 agent 侧的安全判定。"""

from __future__ import annotations

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


def should_stop_after_tool_result(profile: RuntimeProfile, result: dict) -> bool:
    """根据工具结果判断是否应当中断后续工具调用。"""
    if not result.get("requires_user_confirmation"):
        return False
    return profile.safety.stop_after_requires_confirmation


def requires_real_flight_confirmation(profile: RuntimeProfile, tool_name: str) -> bool:
    """判断真机模式下某个工具是否默认需要人工确认。"""
    if profile.mode != "real":
        return False
    if not profile.safety.require_confirmation_for_real_flight:
        return False
    return tool_name in FLIGHT_TOOL_NAMES
