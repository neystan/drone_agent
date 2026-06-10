"""负责加载和组装 runtime profile。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from drone_agent.config.schema import (
    ProviderConfig,
    RosConfig,
    RuntimeProfile,
    SafetyConfig,
    StorageConfig,
    VlmConfig,
)


class ConfigError(RuntimeError):
    """Raised when runtime profile configuration is invalid."""


DEFAULT_PROFILE_DIR = Path(__file__).resolve().parent / "profiles"


def load_profile(profile_name: str, profile_dir: Path | None = None) -> RuntimeProfile:
    """从 YAML 和环境变量中加载指定 profile。"""
    selected_dir = profile_dir or DEFAULT_PROFILE_DIR
    profile_path = selected_dir / f"{profile_name}.yaml"
    if profile_name not in {"sim", "real"}:
        raise ConfigError(f"unknown profile: {profile_name}")
    if not profile_path.exists():
        raise ConfigError(f"profile file not found: {profile_path}")

    try:
        raw = yaml.safe_load(profile_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"failed to parse profile {profile_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"profile must be a mapping: {profile_path}")

    try:
        return _build_profile(raw)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def _build_profile(raw: dict[str, Any]) -> RuntimeProfile:
    """把原始字典转换成经过校验的 RuntimeProfile。"""
    ros = raw["ros"]
    storage = raw["storage"]
    llm = raw["llm"]
    vlm = raw["vlm"]
    safety = raw["safety"]

    llm_key_env = str(llm["api_key_env"])
    llm_api_key = os.getenv(llm_key_env, "")

    vlm_enabled = bool(vlm.get("enabled", False))
    vlm_key_env = vlm.get("api_key_env")
    vlm_api_key = os.getenv(str(vlm_key_env), "") if vlm_enabled and vlm_key_env else None

    return RuntimeProfile(
        name=str(raw["name"]),
        mode=str(raw["mode"]),
        ros=RosConfig(
            node_name=str(ros["node_name"]),
            camera_scene_topic=ros.get("camera_scene_topic"),
        ),
        storage=StorageConfig(
            photo_save_dir=str(storage["photo_save_dir"]),
            analysis_save_dir=str(storage["analysis_save_dir"]),
            log_dir=str(storage["log_dir"]),
        ),
        llm=ProviderConfig(
            base_url=str(llm["base_url"]),
            model=str(llm["model"]),
            api_key_env=llm_key_env,
            api_key=llm_api_key,
        ),
        vlm=VlmConfig(
            enabled=vlm_enabled,
            base_url=vlm.get("base_url"),
            model=vlm.get("model"),
            api_key_env=str(vlm_key_env) if vlm_key_env else None,
            api_key=vlm_api_key,
        ),
        safety=SafetyConfig(
            require_confirmation_for_real_flight=bool(
                safety["require_confirmation_for_real_flight"]
            ),
            max_takeoff_height_m=float(safety["max_takeoff_height_m"]),
            max_relative_move_m=float(safety["max_relative_move_m"]),
            max_vertical_move_m=float(safety["max_vertical_move_m"]),
            max_rotation_deg=float(safety["max_rotation_deg"]),
            action_timeout_s=float(safety["action_timeout_s"]),
            hover_on_timeout=bool(safety["hover_on_timeout"]),
            stop_after_requires_confirmation=bool(
                safety["stop_after_requires_confirmation"]
            ),
        ),
    )
