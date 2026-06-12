"""验证 profile 加载与配置校验。"""

import json
from pathlib import Path

import pytest

from drone_agent.config.loader import ConfigError, load_profile
from drone_agent.config.schema import (
    ProviderConfig,
    RosConfig,
    RuntimeProfile,
    SafetyConfig,
    StorageConfig,
    VlmConfig,
)


def test_runtime_profile_has_expected_nested_values():
    profile = RuntimeProfile(
        name="sim",
        mode="simulation",
        ros=RosConfig(
            node_name="drone_agent_sim",
            camera_scene_topic="/airsim_node/PX4/CameraDepth1/Scene",
        ),
        storage=StorageConfig(
            photo_save_dir="/home/hw/picture",
            analysis_save_dir="/home/hw/picture/analysis_frames",
            log_dir="/home/hw/drone_agent_logs/sim",
        ),
        llm=ProviderConfig(
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            api_key="llm-key",
        ),
        vlm=VlmConfig(
            enabled=True,
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            model="qwen3-vl-flash",
            api_key="vlm-key",
        ),
        safety=SafetyConfig(
            require_confirmation_for_real_flight=False,
            max_takeoff_height_m=10.0,
            max_relative_move_m=20.0,
            max_vertical_move_m=10.0,
            max_rotation_deg=360.0,
            action_timeout_s=30.0,
            hover_on_timeout=True,
            stop_after_requires_confirmation=True,
        ),
    )

    assert profile.name == "sim"
    assert profile.ros.node_name == "drone_agent_sim"
    assert profile.vlm.enabled is True
    assert profile.safety.max_takeoff_height_m == 10.0


def test_safety_config_rejects_non_positive_timeout():
    with pytest.raises(ValueError, match="action_timeout_s must be positive"):
        SafetyConfig(
            require_confirmation_for_real_flight=False,
            max_takeoff_height_m=10.0,
            max_relative_move_m=20.0,
            max_vertical_move_m=10.0,
            max_rotation_deg=360.0,
            action_timeout_s=0.0,
            hover_on_timeout=True,
            stop_after_requires_confirmation=True,
        )


def _write_settings(settings_path: Path, llm_key: str = "llm-secret", vlm_key: str = "vlm-secret"):
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": llm_key,
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-flash",
                },
                "vlm": {
                    "enabled": True,
                    "api_key": vlm_key,
                    "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                    "model": "qwen3-vl-flash",
                },
            }
        ),
        encoding="utf-8",
    )


def test_load_sim_profile_reads_yaml_and_settings(tmp_path):
    settings_path = tmp_path / "settings.json"
    _write_settings(settings_path)

    profile = load_profile("sim", settings_path=settings_path)

    assert profile.name == "sim"
    assert profile.mode == "simulation"
    assert profile.ros.node_name == "drone_agent_sim"
    assert profile.ros.camera_scene_topic == "/airsim_node/PX4/CameraDepth1/Scene"
    assert profile.llm.api_key == "llm-secret"
    assert profile.vlm.api_key == "vlm-secret"
    assert profile.safety.require_confirmation_for_real_flight is False


def test_load_real_profile_uses_stricter_confirmation(tmp_path):
    settings_path = tmp_path / "settings.json"
    _write_settings(settings_path)

    profile = load_profile("real", settings_path=settings_path)

    assert profile.name == "real"
    assert profile.mode == "real"
    assert profile.ros.node_name == "drone_agent_real"
    assert profile.safety.require_confirmation_for_real_flight is True
    assert profile.safety.max_takeoff_height_m <= 3.0


def test_load_profile_rejects_unknown_profile():
    with pytest.raises(ConfigError, match="unknown profile"):
        load_profile("lab")


def test_load_profile_requires_settings_file(tmp_path):
    settings_path = tmp_path / "missing-settings.json"

    with pytest.raises(ConfigError, match="copy settings.example.json to settings.json first"):
        load_profile("sim", settings_path=settings_path)


def test_load_profile_requires_llm_api_key_in_settings(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "",
                    "base_url": "https://api.deepseek.com",
                    "model": "deepseek-v4-flash",
                },
                "vlm": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="provider api_key is required"):
        load_profile("sim", settings_path=settings_path)


def test_load_profile_requires_llm_base_url_and_model_in_settings(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "llm-secret",
                    "base_url": "",
                    "model": "",
                },
                "vlm": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ConfigError, match="provider base_url is required"):
        load_profile("sim", settings_path=settings_path)


def test_load_profile_can_use_explicit_profile_dir(tmp_path):
    profile_dir = tmp_path / "profiles"
    profile_dir.mkdir()
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "custom-llm",
                    "base_url": "https://custom.example.com/v1",
                    "model": "custom-model",
                },
                "vlm": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )
    (profile_dir / "sim.yaml").write_text(
        """
name: sim
mode: simulation
ros:
  node_name: custom_sim
  camera_scene_topic: /camera
storage:
  photo_save_dir: /tmp/photos
  analysis_save_dir: /tmp/analysis
  log_dir: /tmp/logs
safety:
  require_confirmation_for_real_flight: false
  max_takeoff_height_m: 2
  max_relative_move_m: 3
  max_vertical_move_m: 1
  max_rotation_deg: 90
  action_timeout_s: 5
  hover_on_timeout: true
  stop_after_requires_confirmation: true
""".strip(),
        encoding="utf-8",
    )

    profile = load_profile("sim", profile_dir=Path(profile_dir), settings_path=settings_path)

    assert profile.ros.node_name == "custom_sim"
    assert profile.llm.base_url == "https://custom.example.com/v1"
    assert profile.llm.model == "custom-model"
    assert profile.vlm.enabled is False
    assert profile.vlm.api_key is None
