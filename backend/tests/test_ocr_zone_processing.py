"""Unit tests for OCR zone extraction preprocessing."""

import cv2
import numpy as np
import pytest

from app.ml.ocr_service import OCRService


@pytest.mark.asyncio
async def test_extract_text_from_crop_blank_zone_skips_ocr(monkeypatch):
    service = OCRService()

    called = {"ocr": False}

    async def _fake_extract(*_args, **_kwargs):
        called["ocr"] = True
        return {"text": "x", "confidence": 1.0}

    monkeypatch.setattr(service, "extract_text_from_image", _fake_extract)

    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    result = await service.extract_text_from_crop(
        encoded.tobytes(),
        bbox={"x": 10, "y": 10, "width": 100, "height": 100},
        preprocessing=True,
        ink_threshold=0.2,
    )

    assert result["is_blank"] is True
    assert result["text"] == ""
    assert called["ocr"] is False


@pytest.mark.asyncio
async def test_extract_text_from_crop_runs_ocr_when_ink_present(monkeypatch):
    service = OCRService()

    async def _fake_extract(*_args, **_kwargs):
        return {"text": "Answer", "confidence": 0.9}

    monkeypatch.setattr(service, "extract_text_from_image", _fake_extract)

    image = np.full((200, 200, 3), 255, dtype=np.uint8)
    cv2.putText(image, "A", (40, 120), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
    ok, encoded = cv2.imencode(".png", image)
    assert ok

    result = await service.extract_text_from_crop(
        encoded.tobytes(),
        bbox={"x": 0, "y": 0, "width": 200, "height": 200},
        preprocessing=True,
        ink_threshold=0.001,
    )

    assert result["is_blank"] is False
    assert result["text"] == "Answer"
    assert result["confidence"] == 0.9
