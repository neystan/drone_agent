"""提供 JSONL 任务日志记录能力。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from drone_agent.config.schema import RuntimeProfile


def append_jsonl(log_dir: str, filename: str, event: dict[str, Any]) -> None:
    """向指定日志文件追加一条 JSONL 记录。"""
    path = Path(log_dir)
    path.mkdir(parents=True, exist_ok=True)
    logfile = path / filename
    with logfile.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False) + "\n")


def _timestamp() -> str:
    """生成 UTC ISO8601 时间戳。"""
    return datetime.now(timezone.utc).isoformat()


def log_tool_call(
    profile: RuntimeProfile,
    tool_name: str,
    arguments: Any,
    result: dict[str, Any],
) -> None:
    """记录一次工具调用及其结果。"""
    event = {
        "timestamp": _timestamp(),
        "profile_name": profile.name,
        "event_type": "tool_call",
        "tool_name": tool_name,
        "arguments": arguments,
        "result": result,
    }
    try:
        append_jsonl(profile.storage.log_dir, "tool_calls.jsonl", event)
    except OSError:
        pass


def log_agent_message(profile: RuntimeProfile, role: str, content: str) -> None:
    """记录一次 agent 消息。"""
    event = {
        "timestamp": _timestamp(),
        "profile_name": profile.name,
        "event_type": "agent_message",
        "role": role,
        "content": content,
    }
    try:
        append_jsonl(profile.storage.log_dir, "agent_messages.jsonl", event)
    except OSError:
        pass
