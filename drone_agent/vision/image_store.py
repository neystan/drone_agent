"""负责保存拍照和分析图像。"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def _write_image(image_path: Path, frame: Any) -> bool:
    """把图像帧写入指定路径。"""
    import cv2

    return bool(cv2.imwrite(str(image_path), frame))


def save_detection_boxed_image(image_path: Path, objects: list[dict[str, Any]]) -> Path:
    """保存一张带检测红框的结果图。"""
    import cv2

    frame = cv2.imread(str(image_path))
    if frame is None:
        raise OSError(f"failed to read detection image: {image_path}")

    for obj in objects:
        _draw_detection_box(frame, obj)

    boxed_path = image_path.with_name(f"{image_path.stem}_boxed{image_path.suffix}")
    if not _write_image(boxed_path, frame):
        raise OSError("failed to save boxed detection image")
    return boxed_path


def show_detection_preview(image_path: Path, duration_ms: int = 2000) -> bool:
    """弹窗预览检测红框图，窗口到时自动关闭。"""
    import cv2

    frame = cv2.imread(str(image_path))
    if frame is None:
        return False

    window_name = "DINO-XSEEK detection"
    try:
        cv2.imshow(window_name, frame)
        cv2.waitKey(duration_ms)
        cv2.destroyWindow(window_name)
    except cv2.error:
        return False
    return True


def _draw_detection_box(frame: Any, obj: dict[str, Any]) -> None:
    """在图像上绘制单个候选目标红框和编号。"""
    import cv2

    bbox = obj.get("bbox_xyxy_px")
    if not isinstance(bbox, list) or len(bbox) < 4:
        return

    x1, y1, x2, y2 = [int(round(float(value))) for value in bbox[:4]]
    red = (0, 0, 255)
    cv2.rectangle(frame, (x1, y1), (x2, y2), red, 2)

    label = _format_detection_label(obj)
    text_origin = (max(0, x1), max(18, y1 - 6))
    cv2.putText(
        frame,
        label,
        text_origin,
        cv2.FONT_HERSHEY_SIMPLEX,
        0.55,
        red,
        2,
        cv2.LINE_AA,
    )


def _format_detection_label(obj: dict[str, Any]) -> str:
    """生成红框旁边的短标签。"""
    return str(obj.get("index", "?"))


def save_photo(frame: Any, photo_save_dir: str) -> dict:
    """保存一张拍照图片并返回基础元数据。"""
    photo_dir = Path(photo_save_dir)
    try:
        photo_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"failed to create photo directory: {exc}") from exc

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_path = photo_dir / f"photo_{timestamp}.png"
    if not _write_image(image_path, frame):
        raise OSError("failed to save RGB photo to local file")

    return {
        "image_path": str(image_path),
        "image_width": int(frame.shape[1]),
        "image_height": int(frame.shape[0]),
    }


def save_analysis_frame(frame: Any, analysis_save_dir: str) -> Path:
    """保存一张用于视觉分析的临时图片。"""
    analysis_dir = Path(analysis_save_dir)
    try:
        analysis_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OSError(f"failed to create analysis directory: {exc}") from exc

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    image_path = analysis_dir / f"analysis_{timestamp}.png"
    if not _write_image(image_path, frame):
        raise OSError("failed to save analysis frame")
    return image_path
