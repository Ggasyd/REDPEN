"""Tests for alignment service (ORB + AKAZE/ECC fallback and rotation)."""

import cv2
import numpy as np

from app.ml.alignment_service import alignment_service


def _encode_png(image: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", image)
    assert ok
    return encoded.tobytes()


def _build_template_image() -> np.ndarray:
    image = np.full((500, 700, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (40, 40), (660, 460), (0, 0, 0), 3)
    cv2.line(image, (40, 140), (660, 140), (0, 0, 0), 2)
    cv2.line(image, (350, 40), (350, 460), (0, 0, 0), 2)
    cv2.putText(image, "Q1", (70, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    cv2.putText(image, "Q2", (390, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 3)
    cv2.circle(image, (200, 300), 40, (0, 0, 0), 3)
    cv2.circle(image, (500, 300), 40, (0, 0, 0), 3)
    return image


def test_align_to_template_orb_or_akaze_success() -> None:
    template = _build_template_image()
    moving = template.copy()

    result = alignment_service.align_to_template(
        submission_page_bytes=_encode_png(moving),
        template_page_bytes=_encode_png(template),
    )

    assert result.method in {"orb", "akaze", "ecc"}
    assert result.success is True
    assert 0.0 <= result.score <= 1.0
    assert isinstance(result.rotation, int)
    assert result.aligned_image_bytes


def test_align_to_template_detects_rotation() -> None:
    template = _build_template_image()
    moving = cv2.rotate(template, cv2.ROTATE_90_CLOCKWISE)

    result = alignment_service.align_to_template(
        submission_page_bytes=_encode_png(moving),
        template_page_bytes=_encode_png(template),
    )

    assert result.success is True
    assert result.rotation in {0, 90, 180, 270}
    assert 0.0 <= result.score <= 1.0


def test_align_to_template_handles_invalid_inputs() -> None:
    result = alignment_service.align_to_template(
        submission_page_bytes=b"", template_page_bytes=b"not-an-image"
    )

    assert result.success is False
    assert result.score == 0.0
    assert result.method == "none"
