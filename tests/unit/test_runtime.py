"""验证运行时准备逻辑与返回摘要。"""

import json

from drone_agent.config import loader as config_loader
from drone_agent.core.runtime import RuntimeStartResult, prepare_runtime


def _write_settings(settings_path):
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


def test_prepare_runtime_returns_profile_summary(monkeypatch, tmp_path):
    """验证准备阶段只返回 profile 摘要。"""
    settings_path = tmp_path / "settings.json"
    _write_settings(settings_path)
    monkeypatch.setattr(config_loader, "DEFAULT_SETTINGS_PATH", settings_path)

    result = prepare_runtime(profile_name="sim")

    assert isinstance(result, RuntimeStartResult)
    assert result.profile_name == "sim"
    assert result.mode == "simulation"
    assert result.node_name == "drone_agent_sim"
    assert result.ros_started is False


def test_prepare_runtime_can_load_real_profile(monkeypatch, tmp_path):
    """验证准备阶段可以读取 real profile。"""
    settings_path = tmp_path / "settings.json"
    _write_settings(settings_path)
    monkeypatch.setattr(config_loader, "DEFAULT_SETTINGS_PATH", settings_path)

    result = prepare_runtime(profile_name="real")

    assert result.profile_name == "real"
    assert result.mode == "real"
