"""验证工具分发器的参数解析和路由行为。"""

import json
from types import SimpleNamespace

from drone_agent.config.loader import load_profile
from drone_agent.core.tool_dispatcher import dispatch_tool_call
from drone_agent.tools.registry import ToolContext


def make_call(name: str, arguments: str):
    """构造一个最小可用的工具调用对象。"""
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=arguments),
    )


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


def test_dispatch_tool_call_rejects_invalid_json(tmp_path):
    profile = _load_test_profile(tmp_path)
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    result = dispatch_tool_call(context, make_call("move", "{bad json"))

    assert result["success"] is False
    assert result["error"] == "INVALID_TOOL_ARGUMENTS"


def test_dispatch_tool_call_rejects_unknown_tool(tmp_path):
    profile = _load_test_profile(tmp_path)
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    result = dispatch_tool_call(context, make_call("unknown_tool", "{}"))

    assert result["success"] is False
    assert result["error"] == "UNSUPPORTED_TOOL"


def test_dispatch_tool_call_runs_timer(tmp_path):
    profile = _load_test_profile(tmp_path)
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    result = dispatch_tool_call(context, make_call("timer", '{"seconds": 1}'))

    assert result["success"] is True
    assert result["waited_seconds"] == 1
