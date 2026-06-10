"""验证工具 schema 列表的稳定顺序。"""

from drone_agent.tools.schemas import get_tool_schemas


def test_tool_schema_names_match_takeoff_order():
    tool_names = [schema["function"]["name"] for schema in get_tool_schemas()]

    assert tool_names == [
        "takeoff",
        "land",
        "disarm",
        "timer",
        "hover",
        "return_home",
        "current_position_status",
        "battery_status",
        "flight_mode_status",
        "rotate",
        "move",
        "take_photo",
        "analyze_view",
    ]
