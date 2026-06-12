"""验证 agent 侧的安全判定逻辑。"""

import json

from drone_agent.config.loader import load_profile
from drone_agent.core.safety import (
    requires_real_flight_confirmation,
    should_stop_after_tool_result,
)


def _load_profile_pair(tmp_path):
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
    return (
        load_profile("real", settings_path=settings_path),
        load_profile("sim", settings_path=settings_path),
    )


def test_should_stop_after_tool_result_respects_profile_flag(tmp_path):
    _, profile = _load_profile_pair(tmp_path)

    result = should_stop_after_tool_result(
        profile,
        {"requires_user_confirmation": True},
    )

    assert result is True


def test_should_stop_after_tool_result_ignores_normal_success(tmp_path):
    _, profile = _load_profile_pair(tmp_path)

    result = should_stop_after_tool_result(profile, {"success": True})

    assert result is False


def test_requires_real_flight_confirmation_only_for_real_flight_tools(tmp_path):
    real_profile, sim_profile = _load_profile_pair(tmp_path)

    assert requires_real_flight_confirmation(real_profile, "takeoff") is True
    assert requires_real_flight_confirmation(real_profile, "battery_status") is False
    assert requires_real_flight_confirmation(sim_profile, "takeoff") is False
