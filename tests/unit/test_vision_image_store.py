"""验证视觉图片保存逻辑。"""

from pathlib import Path

from drone_agent.vision import image_store


class FakeFrame:
    shape = (480, 640, 3)


def test_save_photo_creates_output(monkeypatch, tmp_path):
    monkeypatch.setattr(image_store, "_write_image", lambda path, frame: True)

    result = image_store.save_photo(FakeFrame(), str(tmp_path))

    assert Path(result["image_path"]).parent == tmp_path
    assert result["image_width"] == 640
    assert result["image_height"] == 480


def test_save_analysis_frame_raises_on_write_failure(monkeypatch, tmp_path):
    monkeypatch.setattr(image_store, "_write_image", lambda path, frame: False)

    try:
        image_store.save_analysis_frame(FakeFrame(), str(tmp_path))
    except OSError as exc:
        assert "failed to save analysis frame" in str(exc)
    else:
        raise AssertionError("expected OSError")
