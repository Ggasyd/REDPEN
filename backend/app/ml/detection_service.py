"""Detection service for MCQ and tables (deterministic, pixel-based)."""

import cv2
import numpy as np
from typing import List, Dict


class DetectionService:
    """Deterministic detection for MCQ marks and tables."""

    def detect_mcq_marks(
        self, image_bytes: bytes, options: List[str] = ["A", "B", "C", "D"]
    ) -> Dict:
        """Detect marked answer in MCQ using pixel density analysis.

        Args:
            image_bytes: Cropped image of MCQ options
            options: List of option labels

        Returns:
            {"detected_answer": str, "confidence": float}
        """
        # Convert bytes to numpy array
        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_GRAYSCALE)

        if img is None:
            return {"detected_answer": "UNKNOWN", "confidence": 0.0}

        # Threshold to binary
        _, binary = cv2.threshold(img, 127, 255, cv2.THRESH_BINARY_INV)

        # Divide image into regions for each option
        height, width = binary.shape
        region_height = height // len(options)

        densities = []
        for i in range(len(options)):
            y_start = i * region_height
            y_end = (i + 1) * region_height
            region = binary[y_start:y_end, :]

            # Calculate pixel density (percentage of black pixels)
            density = np.sum(region == 255) / region.size
            densities.append(density)

        # Find option with highest density (most marks)
        if not densities:
            return {"detected_answer": "UNKNOWN", "confidence": 0.0}

        max_density_idx = np.argmax(densities)
        max_density = densities[max_density_idx]

        # Confidence based on density difference
        confidence = min(max_density * 2, 1.0)  # Scale to 0-1

        return {
            "detected_answer": options[max_density_idx],
            "confidence": float(confidence),
        }

    def detect_table_cells(self, image_bytes: bytes) -> List[Dict]:
        """Detect table cells and extract content.

        Returns:
            List of {"row": int, "col": int, "bbox": [x,y,w,h], "content": str}
        """
        # Stub: In production, use Hough lines or contour detection
        # For MVP, return empty (requires proper table detection)
        return []

    def detect_checkboxes(self, image_bytes: bytes) -> List[Dict]:
        """Detect checkboxes and their states (checked/unchecked).

        Returns:
            List of {"bbox": [x,y,w,h], "is_checked": bool, "confidence": float}
        """
        # Similar to MCQ detection but for checkboxes
        # Stub for MVP
        return []


# Global detection service instance
detection_service = DetectionService()
