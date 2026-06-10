"""验证工具注册表的名称和处理函数映射。"""

from types import SimpleNamespace

from drone_agent.config.loader import load_profile
from drone_agent.tools.registry import ToolContext, get_tool_definition, get_tool_definitions


def test_tool_definitions_cover_all_schema_names(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")

    names = [definition.name for definition in get_tool_definitions()]

    assert names == [
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


def test_perception_tools_are_registered_and_return_image_not_ready(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    profile = load_profile("sim")
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    definition = get_tool_definition("take_photo")
    result = definition.handler(context, {})

    assert result["success"] is False
    assert result["error"] == "IMAGE_NOT_READY"
