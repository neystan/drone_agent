"""验证视觉模型结果归一化逻辑。"""

from pathlib import Path

from drone_agent.vision.vlm import (
    build_analyze_view_prompt,
    derive_suggested_action,
    extract_json_object,
    normalize_vlm_result,
)


def test_extract_json_object_handles_wrapped_text():
    result = extract_json_object('answer: {"scene_description": "road"} end')

    assert result["scene_description"] == "road"


def test_derive_suggested_action_prefers_take_photo_when_centered():
    action = derive_suggested_action("car", True, "center", 0.05)

    assert action == "take_photo"


def test_normalize_vlm_result_clamps_offsets_and_confidence(tmp_path):
    image_path = tmp_path / "frame.png"
    image_path.write_bytes(b"png")

    result = normalize_vlm_result(
        {
            "scene_description": "road",
            "found_target": True,
            "target_position": "right",
            "center_offset_x": 2.0,
            "center_offset_y": -2.0,
            "confidence": 3.0,
        },
        "car",
        image_path,
    )

    assert result["center_offset_x"] == 1.0
    assert result["center_offset_y"] == -1.0
    assert result["confidence"] == 1.0
    assert result["suggested_action"] == "rotate_right_search"


def test_build_analyze_view_prompt_differs_with_target():
    no_target = build_analyze_view_prompt(None)
    with_target = build_analyze_view_prompt("red car")

    assert "target_description 返回 null" in no_target
    assert "目标是：red car" in with_target
