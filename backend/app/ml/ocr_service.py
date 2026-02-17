"""OCR service using Mistral OCR (Pixtral)."""

import base64

import cv2
import httpx
import numpy as np

from app.config import settings


class OCRService:
    """OCR service using Mistral Pixtral model."""

    def __init__(self):
        self.api_key = settings.mistral_api_key
        self.model = settings.mistral_ocr_model
        self.base_url = "https://api.mistral.ai/v1/chat/completions"

    async def extract_text_from_image(
        self,
        image_bytes: bytes,
        prompt: str = "Extract all text from this image verbatim.",
    ) -> dict:
        """Extract text from image using Mistral OCR.

        Returns:
            {"text": str, "confidence": float, "blocks": List[Dict]}
        """
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": f"data:image/png;base64,{image_base64}",
                        },
                    ],
                }
            ],
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(self.base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        text = data["choices"][0]["message"]["content"]

        return {
            "text": text.strip(),
            "confidence": 0.9,
            "blocks": [],
        }

    async def extract_layout(self, image_bytes: bytes) -> list[dict]:
        """Extract layout and text blocks (horizontal slices for geometric pillar)."""
        prompt = """Analyze the layout of this exam page.
        Identify all text blocks with their positions (top, middle, bottom).
        Return each block with: position, text content."""

        result = await self.extract_text_from_image(image_bytes, prompt)

        return [
            {
                "bbox": [0, 0, 100, 100],
                "text": result["text"],
                "confidence": result["confidence"],
            }
        ]

    async def extract_text_from_crop(
        self,
        image_bytes: bytes,
        bbox: dict,
        preprocessing: bool = True,
        ink_threshold: float = 0.01,
    ) -> dict:
        """Extract text from a cropped zone with lightweight preprocessing.

        Returns:
            {
              "text": str,
              "confidence": float,
              "is_blank": bool,
              "ink_ratio": float,
              "processed_image_bytes": bytes,
            }
        """
        arr = np.frombuffer(image_bytes, np.uint8)
        image = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if image is None:
            return {
                "text": "",
                "confidence": 0.0,
                "is_blank": True,
                "ink_ratio": 0.0,
                "processed_image_bytes": b"",
            }

        h, w = image.shape[:2]
        x = max(0, int(bbox.get("x", 0)))
        y = max(0, int(bbox.get("y", 0)))
        bw = max(1, int(bbox.get("width", w)))
        bh = max(1, int(bbox.get("height", h)))
        x2 = min(w, x + bw)
        y2 = min(h, y + bh)

        crop = image[y:y2, x:x2]
        if crop.size == 0:
            return {
                "text": "",
                "confidence": 0.0,
                "is_blank": True,
                "ink_ratio": 0.0,
                "processed_image_bytes": b"",
            }

        gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
        processed = gray
        if preprocessing:
            processed = cv2.adaptiveThreshold(
                gray,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                31,
                11,
            )

        ink_ratio = float(np.mean(processed < 200))
        is_blank = ink_ratio < ink_threshold

        ok, encoded = cv2.imencode(".png", processed)
        processed_bytes = encoded.tobytes() if ok else b""

        if is_blank:
            return {
                "text": "",
                "confidence": 0.0,
                "is_blank": True,
                "ink_ratio": ink_ratio,
                "processed_image_bytes": processed_bytes,
            }

        ocr_result = await self.extract_text_from_image(
            processed_bytes,
            prompt="Extract only the handwritten/student answer in this cropped response zone.",
        )
        return {
            "text": ocr_result.get("text", "").strip(),
            "confidence": ocr_result.get("confidence", 0.0),
            "is_blank": False,
            "ink_ratio": ink_ratio,
            "processed_image_bytes": processed_bytes,
        }

    async def extract_student_name(
        self, image_bytes: bytes, name_zone_bbox: dict | None = None
    ) -> dict:
        """Extract student name from designated zone."""
        prompt = """Extract ONLY the student name from this image.
        Look for fields labeled 'Nom' or 'Prénom' or 'Name'.
        Return just the name, nothing else."""

        result = await self.extract_text_from_image(image_bytes, prompt)

        return {
            "name": result["text"],
            "confidence": result["confidence"],
        }


ocr_service = OCRService()
