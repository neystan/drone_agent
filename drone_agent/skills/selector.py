"""根据用户输入选择本轮 active skill。"""

from __future__ import annotations

from .loader import Skill


def select_skill(user_input: str, profile_name: str, skills: list[Skill]) -> Skill | None:
    """按 profile 和关键词选择一个 skill。"""
    text = user_input.strip().lower()
    candidates = [
        (skill, _keyword_score(text, skill))
        for skill in skills
        if skill.enabled and profile_name in skill.modes
    ]
    matches = [(skill, score) for skill, score in candidates if score > 0]
    if not matches:
        return None

    matches.sort(key=lambda item: (-item[1], item[0].name))
    return matches[0][0]


def _keyword_score(text: str, skill: Skill) -> int:
    """统计用户输入命中的触发关键词数量。"""
    return sum(1 for keyword in skill.trigger_keywords if keyword.lower() in text)
