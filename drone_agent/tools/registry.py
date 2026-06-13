"""工具注册表与工具上下文。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from drone_agent.config.schema import RuntimeProfile
from . import flight, perception, status
from .schemas import (
    ANALYZE_VIEW_TOOL_SCHEMA,
    BATTERY_STATUS_TOOL_SCHEMA,
    CURRENT_POSITION_TOOL_SCHEMA,
    DISARM_TOOL_SCHEMA,
    FLIGHT_MODE_STATUS_TOOL_SCHEMA,
    HOVER_TOOL_SCHEMA,
    LAND_TOOL_SCHEMA,
    MOVE_TOOL_SCHEMA,
    RETURN_HOME_TOOL_SCHEMA,
    ROTATE_TOOL_SCHEMA,
    TAKEOFF_TOOL_SCHEMA,
    TAKE_PHOTO_TOOL_SCHEMA,
    TIMER_TOOL_SCHEMA,
    get_tool_schemas,
)

ToolHandler = Callable[["ToolContext", dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class ToolContext:
    """将执行一次工具所需的一切环境（控制器、配置、会话ID）打包在一起"""

    controller: Any
    profile: RuntimeProfile
    session_id: str = "adhoc"


@dataclass(frozen=True)
class ToolDefinition:
    """描述一个工具的名称、schema 和处理函数。"""

    name: str
    schema: dict[str, Any]
    handler: ToolHandler


def _takeoff_handler(context: ToolContext, arguments: dict[str, Any]) -> dict:
    """转发起飞工具调用。"""
    return flight.takeoff(context.controller, arguments.get("height"), context.profile)


def _land_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发降落工具调用。"""
    return flight.land(context.controller, context.profile)


def _disarm_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发上锁工具调用。"""
    return flight.disarm(context.controller)


def _timer_handler(_context: ToolContext, arguments: dict[str, Any]) -> dict:
    """转发计时工具调用。"""
    return flight.timer(arguments.get("seconds"))


def _hover_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发悬停工具调用。"""
    return flight.hover(context.controller)


def _return_home_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发返航工具调用。"""
    return flight.return_home(context.controller)


def _current_position_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发位置查询工具调用。"""
    return status.current_position_status(context.controller)


def _battery_status_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发电池查询工具调用。"""
    return status.battery_status(context.controller)


def _flight_mode_status_handler(context: ToolContext, _arguments: dict[str, Any]) -> dict:
    """转发飞行模式查询工具调用。"""
    return status.flight_mode_status(context.controller)


def _rotate_handler(context: ToolContext, arguments: dict[str, Any]) -> dict:
    """转发旋转工具调用。"""
    return flight.rotate(
        context.controller,
        arguments.get("direction"),
        arguments.get("degrees"),
        context.profile,
    )


def _move_handler(context: ToolContext, arguments: dict[str, Any]) -> dict:
    """转发相对移动工具调用。"""
    return flight.move(
        context.controller,
        arguments.get("x"),
        arguments.get("y"),
        arguments.get("z"),
        context.profile,
    )


def _take_photo_handler(context: ToolContext, arguments: dict[str, Any]) -> dict:
    """转发拍照工具调用。"""
    return perception.take_photo(context, arguments)


def _analyze_view_handler(context: ToolContext, arguments: dict[str, Any]) -> dict:
    """转发画面分析工具调用。"""
    return perception.analyze_view(context, arguments)


TOOL_DEFINITIONS = [
    ToolDefinition("takeoff", TAKEOFF_TOOL_SCHEMA, _takeoff_handler),
    ToolDefinition("land", LAND_TOOL_SCHEMA, _land_handler),
    ToolDefinition("disarm", DISARM_TOOL_SCHEMA, _disarm_handler),
    ToolDefinition("timer", TIMER_TOOL_SCHEMA, _timer_handler),
    ToolDefinition("hover", HOVER_TOOL_SCHEMA, _hover_handler),
    ToolDefinition("return_home", RETURN_HOME_TOOL_SCHEMA, _return_home_handler),
    ToolDefinition("current_position_status", CURRENT_POSITION_TOOL_SCHEMA, _current_position_handler),
    ToolDefinition("battery_status", BATTERY_STATUS_TOOL_SCHEMA, _battery_status_handler),
    ToolDefinition("flight_mode_status", FLIGHT_MODE_STATUS_TOOL_SCHEMA, _flight_mode_status_handler),
    ToolDefinition("rotate", ROTATE_TOOL_SCHEMA, _rotate_handler),
    ToolDefinition("move", MOVE_TOOL_SCHEMA, _move_handler),
    ToolDefinition("take_photo", TAKE_PHOTO_TOOL_SCHEMA, _take_photo_handler),
    ToolDefinition("analyze_view", ANALYZE_VIEW_TOOL_SCHEMA, _analyze_view_handler),
]

TOOL_DEFINITION_BY_NAME = {definition.name: definition for definition in TOOL_DEFINITIONS}


def get_tool_definitions() -> list[ToolDefinition]:
    """返回全部工具定义。"""
    return list(TOOL_DEFINITIONS)


def get_tool_definition(name: str) -> ToolDefinition | None:
    """按名称查找工具定义。"""
    return TOOL_DEFINITION_BY_NAME.get(name)


#界定工具注册表的“公开接口
__all__ = [
    "ToolContext",
    "ToolDefinition",
    "get_tool_definition",
    "get_tool_definitions",
    "get_tool_schemas",
]
