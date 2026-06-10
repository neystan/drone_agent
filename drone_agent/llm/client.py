"""创建 OpenAI-compatible 文本模型客户端。"""

from __future__ import annotations

from typing import Any

from drone_agent.config.schema import RuntimeProfile


def create_llm_client(profile: RuntimeProfile) -> Any:
    """根据 profile 创建文本模型客户端。"""
    from openai import OpenAI

    return OpenAI(
        api_key=profile.llm.api_key,
        base_url=profile.llm.base_url,
    )
