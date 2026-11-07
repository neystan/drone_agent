import pytest

from drone_agent.vision.dinoxseek import save_detection_visualization


def test_save_detection_visualization_writes_red_bbox(tmp_path):
    cv2 = pytest.importorskip("cv2")
    np = pytest.importorskip("numpy")
    image_path = tmp_path / "analysis.png"
    source_image = np.full((80, 100, 3), 255, dtype=np.uint8)
    assert cv2.imwrite(str(image_path), source_image)

    annotated_image_path = save_detection_visualization(
        image_path,
        [
            {
                "index": 0,
                "label": "vehicle",
                "bbox_xyxy_px": [10, 20, 60, 70],
            }
        ],
    )

    annotated_image = cv2.imread(str(annotated_image_path))
    assert annotated_image_path == tmp_path / "analysis_dinoxseek.png"
    assert annotated_image is not None
    assert annotated_image[20, 10].tolist() == [0, 0, 255]
