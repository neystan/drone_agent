"""验证运行时准备逻辑与返回摘要。"""

from drone_agent.core.runtime import RuntimeStartResult, prepare_runtime


def test_prepare_runtime_returns_profile_summary(monkeypatch):
    """验证准备阶段只返回 profile 摘要。"""
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")

    result = prepare_runtime(profile_name="sim")

    assert isinstance(result, RuntimeStartResult)
    assert result.profile_name == "sim"
    assert result.mode == "simulation"
    assert result.node_name == "drone_agent_sim"
    assert result.ros_started is False


def test_prepare_runtime_can_load_real_profile(monkeypatch):
    """验证准备阶段可以读取 real profile。"""
    monkeypatch.setenv("DRONE_AGENT_LLM_API_KEY", "llm-secret")
    monkeypatch.setenv("DRONE_AGENT_VLM_API_KEY", "vlm-secret")

    result = prepare_runtime(profile_name="real")

    assert result.profile_name == "real"
    assert result.mode == "real"
