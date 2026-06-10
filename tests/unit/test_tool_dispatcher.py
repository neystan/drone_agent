"""验证工具分发器的参数解析和路由行为。"""

from types import SimpleNamespace

from drone_agent.config.loader import load_profile
from drone_agent.core.tool_dispatcher import dispatch_tool_call
from drone_agent.tools.registry import ToolContext


def make_call(name: str, arguments: str):
    """构造一个最小可用的工具调用对象。"""
    return SimpleNamespace(
        function=SimpleNamespace(name=name, arguments=arguments),
    )


def test_dispatch_tool_call_rejects_invalid_json(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    profile = load_profile("sim")
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    result = dispatch_tool_call(context, make_call("move", "{bad json"))

    assert result["success"] is False
    assert result["error"] == "INVALID_TOOL_ARGUMENTS"


def test_dispatch_tool_call_rejects_unknown_tool(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    profile = load_profile("sim")
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    result = dispatch_tool_call(context, make_call("unknown_tool", "{}"))

    assert result["success"] is False
    assert result["error"] == "UNSUPPORTED_TOOL"


def test_dispatch_tool_call_runs_timer(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    profile = load_profile("sim")
    context = ToolContext(controller=SimpleNamespace(), profile=profile)

    result = dispatch_tool_call(context, make_call("timer", '{"seconds": 1}'))

    assert result["success"] is True
    assert result["waited_seconds"] == 1
