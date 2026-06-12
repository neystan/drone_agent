"""验证工具注册表的名称和处理函数映射。"""

import json
from types import SimpleNamespace

from drone_agent.config.loader import load_profile
from drone_agent.tools.registry import ToolContext, get_tool_definition, get_tool_definitions


def _load_test_profile(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "llm-secret",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-flash",
                },
                "vlm": {
                    "enabled": True,
                    "api_key": "vlm-secret",
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen3-vl-flash",
                },
            }
        ),
        encoding="utf-8",
    )
    return load_profile("sim", settings_path=settings_path)


def test_tool_definitions_cover_all_schema_names(tmp_path):
    _load_test_profile(tmp_path)

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


def test_perception_tools_are_registered_and_return_image_not_ready(tmp_path):
    profile = _load_test_profile(tmp_path)
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    definition = get_tool_definition("take_photo")
    result = definition.handler(context, {})

    assert result["success"] is False
    assert result["error"] == "IMAGE_NOT_READY"
