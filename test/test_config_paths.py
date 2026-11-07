"""Tests for profile-relative runtime paths and the real RGB topic."""

from __future__ import annotations

import json
import os
import runpy
import sys
import types
from pathlib import Path

import pytest

import drone_agent.config.loader as loader
from drone_agent.config.loader import DEFAULT_SETTINGS_PATH, load_profile


def test_real_profile_resolves_storage_paths_and_rgb_topic(tmp_path: Path) -> None:
    """真机 profile 应解析项目内相对路径并配置原始 RGB topic。"""
    settings_path = tmp_path / "settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "llm": {
                    "api_key": "llm-key",
                    "base_url": "http://llm.invalid",
                    "model": "llm-model",
                },
                "vlm": {"enabled": False},
                "detector": {"enabled": False},
                "tracker": {"enabled": False},
            }
        ),
        encoding="utf-8",
    )

    profile = load_profile("real", settings_path=settings_path)
    project_root = Path(__file__).resolve().parents[1]

    assert DEFAULT_SETTINGS_PATH == project_root / "settings.json"
    assert profile.ros.camera_scene_topic == "/camera/image_raw"
    assert Path(profile.storage.photo_save_dir) == project_root / "data/real/photos"
    assert Path(profile.storage.analysis_save_dir) == project_root / "data/real/analysis"
    assert Path(profile.storage.log_dir) == project_root / "data/real/logs"


def _mock_install_prefix(monkeypatch, prefix: Path) -> None:
    """提供离线安装前缀查询，避免测试依赖 ROS 环境。"""
    packages = types.ModuleType("ament_index_python.packages")
    packages.get_package_prefix = lambda _name: str(prefix)
    ament_index = types.ModuleType("ament_index_python")
    ament_index.packages = packages
    monkeypatch.setitem(sys.modules, "ament_index_python", ament_index)
    monkeypatch.setitem(sys.modules, "ament_index_python.packages", packages)


@pytest.mark.parametrize("merged", [False, True])
def test_installed_package_resolves_workspace_source_root(tmp_path, monkeypatch, merged):
    """普通和合并安装均将配置与数据定位到工作空间源码目录。"""
    workspace = tmp_path / "workspace"
    project = workspace / "src" / "drone_agent"
    project.mkdir(parents=True)
    (project / "package.xml").write_text("<package/>", encoding="utf-8")
    prefix = workspace / "install" if merged else workspace / "install" / "drone_agent"
    module_path = prefix / "lib/python3.10/site-packages/drone_agent/config/loader.py"
    monkeypatch.setattr(loader, "__file__", str(module_path))
    _mock_install_prefix(monkeypatch, prefix)

    assert loader._resolve_project_root() == project


def test_missing_installed_source_is_reported(tmp_path, monkeypatch):
    """源码目录缺失时明确报错，不把配置或数据写入安装目录。"""
    prefix = tmp_path / "workspace/install/drone_agent"
    module_path = prefix / "lib/python3.10/site-packages/drone_agent/config/loader.py"
    monkeypatch.setattr(loader, "__file__", str(module_path))
    _mock_install_prefix(monkeypatch, prefix)

    with pytest.raises(loader.ConfigError, match="project source not found"):
        loader._resolve_project_root()


def test_explicit_settings_path_takes_priority_over_environment(tmp_path, monkeypatch):
    """显式配置路径优先于环境变量。"""
    explicit = tmp_path / "explicit.json"
    monkeypatch.setenv("DRONE_AGENT_SETTINGS", str(tmp_path / "environment.json"))

    assert loader.resolve_settings_path(explicit) == explicit


def test_environment_settings_does_not_move_storage_root(tmp_path, monkeypatch):
    """配置覆盖只改变配置来源，不改变项目运行数据的位置。"""
    settings = tmp_path / "external-settings.json"
    settings.write_text(
        json.dumps({"llm": {"api_key": "test-key", "base_url": "http://llm.invalid", "model": "test-model"}}),
        encoding="utf-8",
    )
    monkeypatch.setenv("DRONE_AGENT_SETTINGS", str(settings))

    profile = loader.load_profile("real")

    assert loader.resolve_settings_path() == settings
    assert Path(profile.storage.log_dir) == loader.PROJECT_ROOT / "data/real/logs"


def test_absolute_storage_path_is_preserved(tmp_path):
    """绝对存储路径保持原位置，不拼接项目根目录。"""
    absolute = tmp_path / "external-data"

    assert loader._resolve_storage_path(str(absolute)) == str(absolute)


def test_real_wrapper_and_cli_resolve_same_paths_outside_project(tmp_path, monkeypatch):
    """任意工作目录下，两种入口使用同一配置和存储位置。"""
    from drone_agent import cli

    calls = []

    def capture_runtime(profile_name):
        """只记录入口路径，不启动 ROS、模型或设备。"""
        calls.append((profile_name, loader.resolve_settings_path(), loader._resolve_storage_path("data/real/logs")))

    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("DRONE_AGENT_SETTINGS", raising=False)
    monkeypatch.setattr(cli, "start_runtime", capture_runtime)
    monkeypatch.setattr(sys, "argv", ["drone_agent_real"])

    assert cli.main_real([]) == 0
    script = Path(__file__).resolve().parents[1] / "scripts/drone_agent_real"
    with pytest.raises(SystemExit) as stopped:
        runpy.run_path(str(script), run_name="__main__")

    assert stopped.value.code == 0
    assert calls == [("real", DEFAULT_SETTINGS_PATH, str(loader.PROJECT_ROOT / "data/real/logs"))] * 2
    assert "DRONE_AGENT_SETTINGS" not in os.environ
