"""验证系统提示词中的关键安全语义。"""

from drone_agent.llm.prompts import SYSTEM_PROMPT


def test_system_prompt_contains_confirmation_stop_rule():
    assert "requires_user_confirmation=true" in SYSTEM_PROMPT
    assert "停止后续飞行动作" in SYSTEM_PROMPT


def test_system_prompt_explains_target_and_final_position():
    assert "target_position_ned" in SYSTEM_PROMPT
    assert "final_position_ned" in SYSTEM_PROMPT
