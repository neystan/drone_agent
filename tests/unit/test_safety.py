"""验证 agent 侧的安全判定逻辑。"""

from drone_agent.config.loader import load_profile
from drone_agent.core.safety import (
    requires_real_flight_confirmation,
    should_stop_after_tool_result,
)


def test_should_stop_after_tool_result_respects_profile_flag(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    profile = load_profile("sim")

    result = should_stop_after_tool_result(
        profile,
        {"requires_user_confirmation": True},
    )

    assert result is True


def test_should_stop_after_tool_result_ignores_normal_success(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    profile = load_profile("sim")

    result = should_stop_after_tool_result(profile, {"success": True})

    assert result is False


def test_requires_real_flight_confirmation_only_for_real_flight_tools(monkeypatch):
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")
    real_profile = load_profile("real")
    sim_profile = load_profile("sim")

    assert requires_real_flight_confirmation(real_profile, "takeoff") is True
    assert requires_real_flight_confirmation(real_profile, "battery_status") is False
    assert requires_real_flight_confirmation(sim_profile, "takeoff") is False
