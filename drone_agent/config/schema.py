"""定义 profile 的结构与校验规则。"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RosConfig:
    """ROS2 相关配置。"""

    node_name: str
    camera_scene_topic: str | None

    def __post_init__(self) -> None:
        """校验 ROS 配置中的必填字段。"""
        if not self.node_name:
            raise ValueError("ros.node_name is required")


@dataclass(frozen=True)
class StorageConfig:
    """图片和日志存储配置。"""

    photo_save_dir: str
    analysis_save_dir: str
    log_dir: str

    def __post_init__(self) -> None:
        """校验存储目录配置是否完整。"""
        if not self.photo_save_dir:
            raise ValueError("storage.photo_save_dir is required")
        if not self.analysis_save_dir:
            raise ValueError("storage.analysis_save_dir is required")
        if not self.log_dir:
            raise ValueError("storage.log_dir is required")


@dataclass(frozen=True)
class ProviderConfig:
    """文本模型提供方配置。"""

    base_url: str
    model: str
    api_key_env: str
    api_key: str

    def __post_init__(self) -> None:
        """校验文本模型配置与密钥是否可用。"""
        if not self.base_url:
            raise ValueError("provider base_url is required")
        if not self.model:
            raise ValueError("provider model is required")
        if not self.api_key_env:
            raise ValueError("provider api_key_env is required")
        if not self.api_key:
            raise ValueError(f"environment variable {self.api_key_env} is required")


@dataclass(frozen=True)
class VlmConfig:
    """视觉模型提供方配置。"""

    enabled: bool
    base_url: str | None
    model: str | None
    api_key_env: str | None
    api_key: str | None

    def __post_init__(self) -> None:
        """在启用视觉模型时校验相关字段。"""
        if not self.enabled:
            return
        if not self.base_url:
            raise ValueError("vlm.base_url is required when vlm.enabled=true")
        if not self.model:
            raise ValueError("vlm.model is required when vlm.enabled=true")
        if not self.api_key_env:
            raise ValueError("vlm.api_key_env is required when vlm.enabled=true")
        if not self.api_key:
            raise ValueError(f"environment variable {self.api_key_env} is required")


@dataclass(frozen=True)
class SafetyConfig:
    """飞行安全限制配置。"""

    require_confirmation_for_real_flight: bool
    max_takeoff_height_m: float
    max_relative_move_m: float
    max_vertical_move_m: float
    max_rotation_deg: float
    action_timeout_s: float
    hover_on_timeout: bool
    stop_after_requires_confirmation: bool

    def __post_init__(self) -> None:
        """校验安全阈值是否为正数。"""
        if self.max_takeoff_height_m <= 0:
            raise ValueError("max_takeoff_height_m must be positive")
        if self.max_relative_move_m <= 0:
            raise ValueError("max_relative_move_m must be positive")
        if self.max_vertical_move_m <= 0:
            raise ValueError("max_vertical_move_m must be positive")
        if self.max_rotation_deg <= 0:
            raise ValueError("max_rotation_deg must be positive")
        if self.action_timeout_s <= 0:
            raise ValueError("action_timeout_s must be positive")


@dataclass(frozen=True)
class RuntimeProfile:
    """完整的运行时 profile。"""

    name: str
    mode: str
    ros: RosConfig
    storage: StorageConfig
    llm: ProviderConfig
    vlm: VlmConfig
    safety: SafetyConfig

    def __post_init__(self) -> None:
        """校验 profile 名称和运行模式是否合法。"""
        if self.name not in {"sim", "real"}:
            raise ValueError("profile name must be 'sim' or 'real'")
        if self.mode not in {"simulation", "real"}:
            raise ValueError("profile mode must be 'simulation' or 'real'")
