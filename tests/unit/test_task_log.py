"""验证 JSONL 任务日志输出。"""

import json

from drone_agent.config.loader import load_profile
from drone_agent.logging.task_log import append_jsonl, log_agent_message, log_tool_call


def test_append_jsonl_creates_log_file(tmp_path):
    append_jsonl(str(tmp_path), "events.jsonl", {"event_type": "demo"})

    content = (tmp_path / "events.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(content)["event_type"] == "demo"


def _load_test_profile(tmp_path):
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
    return load_profile("sim", settings_path=settings_path)


def test_log_tool_call_writes_jsonl(tmp_path):
    profile = _load_test_profile(tmp_path)
    profile = profile.__class__(
        name=profile.name,
        mode=profile.mode,
        ros=profile.ros,
        storage=profile.storage.__class__(
            photo_save_dir=profile.storage.photo_save_dir,
            analysis_save_dir=profile.storage.analysis_save_dir,
            log_dir=str(tmp_path),
        ),
        llm=profile.llm,
        vlm=profile.vlm,
        safety=profile.safety,
    )

    log_tool_call(profile, "move", {"x": 1}, {"success": True})

    line = (tmp_path / "tool_calls.jsonl").read_text(encoding="utf-8").strip()
    event = json.loads(line)
    assert event["tool_name"] == "move"
    assert event["arguments"] == {"x": 1}


def test_log_agent_message_writes_jsonl(tmp_path):
    profile = _load_test_profile(tmp_path)
    profile = profile.__class__(
        name=profile.name,
        mode=profile.mode,
        ros=profile.ros,
        storage=profile.storage.__class__(
            photo_save_dir=profile.storage.photo_save_dir,
            analysis_save_dir=profile.storage.analysis_save_dir,
            log_dir=str(tmp_path),
        ),
        llm=profile.llm,
        vlm=profile.vlm,
        safety=profile.safety,
    )

    log_agent_message(profile, "user", "查询状态")

    line = (tmp_path / "agent_messages.jsonl").read_text(encoding="utf-8").strip()
    event = json.loads(line)
    assert event["role"] == "user"
    assert event["content"] == "查询状态"
