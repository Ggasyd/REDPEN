"""OCR service using Mistral OCR (Pixtral)."""

import base64

import httpx

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
        # Encode image to base64
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Prepare request
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

        # Extract text from response
        text = data["choices"][0]["message"]["content"]

        return {
            "text": text.strip(),
            "confidence": 0.9,  # Mistral doesn't provide confidence, using default
            "blocks": [],  # Would need layout analysis
        }

    async def extract_layout(self, image_bytes: bytes) -> list[dict]:
        """Extract layout and text blocks (horizontal slices for geometric pillar).

        Returns:
            List of {"bbox": [x, y, w, h], "text": str}
        """
        # Stub: In production, use Mistral OCR with layout analysis prompt
        # For now, return mock layout
        prompt = """Analyze the layout of this exam page.
        Identify all text blocks with their positions (top, middle, bottom).
        Return each block with: position, text content."""

        result = await self.extract_text_from_image(image_bytes, prompt)

        # Parse response into blocks (simplified for MVP)
        return [
            {
                "bbox": [0, 0, 100, 100],  # Mock bbox
                "text": result["text"],
                "confidence": result["confidence"],
            }
        ]

    async def extract_student_name(
        self, image_bytes: bytes, name_zone_bbox: dict | None = None
    ) -> dict:
        """Extract student name from designated zone.

        Returns:
            {"name": str, "confidence": float}
        """
        prompt = """Extract ONLY the student name from this image.
        Look for fields labeled 'Nom' or 'Prénom' or 'Name'.
        Return just the name, nothing else."""

        result = await self.extract_text_from_image(image_bytes, prompt)

        return {
            "name": result["text"],
            "confidence": result["confidence"],
        }


# Global OCR service instance
ocr_service = OCRService()
