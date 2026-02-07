"""Vision service using GPT-4o-mini and Gemini 1.5 Flash for semantic analysis."""

import base64
from typing import List, Dict
from openai import AsyncOpenAI
import google.generativeai as genai
from app.config import settings


class VisionService:
    """Vision service for semantic classification of answer blocks."""

    def __init__(self):
        # OpenAI (primary)
        self.openai_client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.openai_model = settings.openai_model

        # Gemini (fallback)
        genai.configure(api_key=settings.google_api_key)
        self.gemini_model = genai.GenerativeModel(settings.gemini_model)

    async def classify_answer_blocks(
        self, image_bytes: bytes, questions: List[Dict], use_gemini: bool = False
    ) -> List[Dict]:
        """Classify answer blocks by question using semantic analysis.

        Args:
            image_bytes: Image of the exam page
            questions: List of {"id": str, "number": str, "text": str}
            use_gemini: Use Gemini instead of GPT-4o-mini

        Returns:
            List of {"question_id": str, "bbox": [x,y,w,h], "confidence": float}
        """
        if use_gemini:
            return await self._classify_with_gemini(image_bytes, questions)
        else:
            return await self._classify_with_gpt(image_bytes, questions)

    async def _classify_with_gpt(
        self, image_bytes: bytes, questions: List[Dict]
    ) -> List[Dict]:
        """Classify using GPT-4o-mini (vision)."""
        # Encode image
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        # Build prompt
        questions_text = "\n".join(
            [f"Question {q['number']}: {q['text']}" for q in questions]
        )

        prompt = f"""Analyze this exam page and identify which answer corresponds to which question.

Questions:
{questions_text}

For each visible answer block, identify which question it answers based on semantic content.
Return a JSON list with: question_number, estimated_position (top/middle/bottom), confidence.

NEVER grade or correct, only classify!"""

        try:
            _ = await self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1000,
            )

            # Parse response (simplified for MVP)
            # content = response.choices[0].message.content

            # Stub: Return mock classifications
            return [
                {
                    "question_id": questions[0]["id"] if questions else None,
                    "bbox": [0, 0, 100, 100],
                    "confidence": 0.85,
                }
            ]

        except Exception as e:
            print(f"GPT-4o-mini classification error: {e}")
            # Fallback to Gemini
            return await self._classify_with_gemini(image_bytes, questions)

    async def _classify_with_gemini(
        self, image_bytes: bytes, questions: List[Dict]
    ) -> List[Dict]:
        """Classify using Gemini 1.5 Flash (fallback)."""
        # Stub: Similar to GPT but with Gemini API
        # For MVP, return mock data
        return [
            {
                "question_id": questions[0]["id"] if questions else None,
                "bbox": [0, 0, 100, 100],
                "confidence": 0.80,
            }
        ]

    async def suggest_student_name(
        self, image_bytes: bytes, student_list: List[str]
    ) -> Dict:
        """Suggest student name using vision + student list.

        Returns:
            {"suggested_name": str, "confidence": float}
        """
        image_base64 = base64.b64encode(image_bytes).decode("utf-8")

        students_text = ", ".join(student_list[:20])  # Limit to 20

        prompt = f"""Look at this exam page and identify the student name.
Possible students: {students_text}

Return ONLY the matching student name from the list, or 'UNKNOWN' if not found."""

        try:
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{image_base64}"
                                },
                            },
                        ],
                    }
                ],
                max_tokens=50,
            )

            suggested_name = response.choices[0].message.content.strip()

            return {
                "suggested_name": suggested_name,
                "confidence": 0.75,
            }

        except Exception as e:
            print(f"Vision student suggestion error: {e}")
            return {"suggested_name": "UNKNOWN", "confidence": 0.0}


# Global vision service instance
vision_service = VisionService()
