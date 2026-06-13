"""负责加载和组装 runtime profile。"""

from __future__ import annotations

import json
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
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SETTINGS_PATH = PACKAGE_ROOT / "settings.json"
DEFAULT_SETTINGS_EXAMPLE_PATH = PACKAGE_ROOT / "settings.example.json"
SETTINGS_ENV_VAR = "DRONE_AGENT_SETTINGS"


def load_profile(
    profile_name: str,
    profile_dir: Path | None = None,
    settings_path: Path | None = None,
) -> RuntimeProfile:
    """从 YAML 和本地 settings.json 中加载指定 profile。"""
    selected_dir = profile_dir or DEFAULT_PROFILE_DIR
    profile_path = selected_dir / f"{profile_name}.yaml"
    selected_settings_path = resolve_settings_path(settings_path)
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

    settings = _load_settings(selected_settings_path)

    try:
        return _build_profile(raw, settings)
    except (KeyError, TypeError, ValueError) as exc:
        raise ConfigError(str(exc)) from exc


def _load_settings(settings_path: Path) -> dict[str, Any]:
    """读取项目根目录的 settings.json。"""
    if not settings_path.exists():
        raise ConfigError(
            f"settings file not found: {settings_path}. "
            f"copy {DEFAULT_SETTINGS_EXAMPLE_PATH.name} to settings.json first"
        )

    try:
        raw = json.loads(settings_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"failed to parse settings {settings_path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ConfigError(f"settings must be a mapping: {settings_path}")

    return raw


def resolve_settings_path(settings_path: Path | None = None) -> Path:
    """Resolve the runtime settings file across source and installed layouts."""
    if settings_path is not None:
        return settings_path

    env_path = os.environ.get(SETTINGS_ENV_VAR, "").strip()
    if env_path:
        return Path(env_path).expanduser().resolve()

    candidates: list[Path] = []

    cwd = Path.cwd().resolve()
    for base in [cwd, *cwd.parents]:
        candidates.append(base / "settings.json")
        candidates.append(base / "src" / "drone_agent" / "settings.json")

    for base in [PACKAGE_ROOT, *PACKAGE_ROOT.parents]:
        candidates.append(base / "settings.json")
        candidates.append(base / "src" / "drone_agent" / "settings.json")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if candidate.exists():
            return candidate

    return DEFAULT_SETTINGS_PATH


def _build_profile(raw: dict[str, Any], settings: dict[str, Any]) -> RuntimeProfile:
    """把原始字典转换成经过校验的 RuntimeProfile。"""
    ros = raw["ros"]
    storage = raw["storage"]
    safety = raw["safety"]
    llm_settings = settings.get("llm", {})
    vlm_settings = settings.get("vlm", {})

    if not isinstance(llm_settings, dict):
        raise ValueError("settings.llm must be a mapping")
    if not isinstance(vlm_settings, dict):
        raise ValueError("settings.vlm must be a mapping")

    llm_api_key = str(llm_settings.get("api_key", "")).strip()
    llm_base_url = str(llm_settings.get("base_url", "")).strip()
    llm_model = str(llm_settings.get("model", "")).strip()

    vlm_enabled = bool(vlm_settings.get("enabled", False))
    vlm_base_url = str(vlm_settings.get("base_url", "")).strip() if vlm_enabled else None
    vlm_model = str(vlm_settings.get("model", "")).strip() if vlm_enabled else None
    vlm_api_key = str(vlm_settings.get("api_key", "")).strip() if vlm_enabled else None

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
            base_url=llm_base_url,
            model=llm_model,
            api_key=llm_api_key,
        ),
        vlm=VlmConfig(
            enabled=vlm_enabled,
            base_url=str(vlm_base_url) if vlm_base_url is not None else None,
            model=str(vlm_model) if vlm_model is not None else None,
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
