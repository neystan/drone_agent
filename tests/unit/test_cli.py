"""验证 CLI 入口是否把 profile 正确传给运行时。"""

from drone_agent import cli
from drone_agent.config.loader import ConfigError


def test_main_sim_forces_sim_profile(monkeypatch):
    """验证仿真入口始终使用 sim profile。"""
    calls = []

    def fake_start_runtime(profile_name):
        """记录 sim 入口的 profile。"""
        calls.append(profile_name)

    monkeypatch.setattr(cli, "start_runtime", fake_start_runtime)

    exit_code = cli.main_sim([])

    assert exit_code == 0
    assert calls == ["sim"]


def test_main_real_forces_real_profile(monkeypatch):
    """验证真机入口始终使用 real profile。"""
    calls = []

    def fake_start_runtime(profile_name):
        """记录 real 入口的 profile。"""
        calls.append(profile_name)

    monkeypatch.setattr(cli, "start_runtime", fake_start_runtime)

    exit_code = cli.main_real([])

    assert exit_code == 0
    assert calls == ["real"]


def test_main_reports_config_error_without_traceback(monkeypatch, capsys):
    """验证配置错误会以干净的 stderr 形式返回。"""

    def fake_start_runtime(profile_name):
        """模拟运行时抛出配置错误。"""
        raise ConfigError("environment variable DRONE_AGENT_LLM_API_KEY is required")

    monkeypatch.setattr(cli, "start_runtime", fake_start_runtime)

    exit_code = cli.main_sim([])

    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert (
        "config error: environment variable DRONE_AGENT_LLM_API_KEY is required"
        in captured.err
    )
