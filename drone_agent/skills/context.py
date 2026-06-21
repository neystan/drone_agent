"""构造 skills index 和 active skill 上下文。"""

from __future__ import annotations

from .loader import Skill


def build_skills_index(skills: list[Skill], profile_name: str) -> str:
    """生成只包含 name 和 description 的 skills index。"""
    enabled_skills = [
        skill for skill in skills if skill.enabled and profile_name in skill.modes
    ]
    if not enabled_skills:
        return ""

    lines = ["# Skills Index", "", "当前可用的 skills："]
    for skill in enabled_skills:
        lines.append(f"- {skill.name}: {skill.description}")
    return "\n".join(lines)


def build_active_skill_message(skill: Skill | None) -> dict[str, str] | None:
    """生成本轮 active skill 的临时 system 消息。"""
    if skill is None:
        return None

    content = "\n".join(
        [
            "# Active Skill",
            "",
            "当前用户请求匹配以下 skill。你必须遵守该 skill 的流程和安全约束。",
            "",
            f"Skill: {skill.name}",
            f"Allowed tools: {', '.join(skill.allowed_tools)}",
            f"Forbidden tools: {', '.join(skill.forbidden_tools) if skill.forbidden_tools else 'none'}",
            "",
            skill.body,
        ]
    )
    return {"role": "system", "content": content}
