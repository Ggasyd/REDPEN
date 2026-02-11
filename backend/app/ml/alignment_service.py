"""Image alignment service with ORB primary and AKAZE/ECC fallbacks."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import cv2
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class AlignmentResult:
    """Alignment output used by the pipeline."""

    aligned_image_bytes: bytes
    method: str
    score: float
    rotation: int
    homography_meta: dict
    success: bool
    debug_overlay_bytes: bytes | None = None


class AlignmentService:
    """Align a submission page against a template page."""

    MIN_FEATURE_MATCHES = 12
    MIN_INLIER_RATIO = 0.35
    ORB_FEATURES = 2000

    def align_to_template(
        self,
        submission_page_bytes: bytes,
        template_page_bytes: bytes,
    ) -> AlignmentResult:
        """Align page to template with rotation search and method fallback
        Tries rotations [0, 90, 180, 270].
        For each rotation, tries ORB then AKAZE then ECC.
        Returns best scoring result with score normalized in [0, 1].
        """
        submission_image = self._decode_image(submission_page_bytes)
        template_image = self._decode_image(template_page_bytes)

        if submission_image is None or template_image is None:
            return AlignmentResult(
                aligned_image_bytes=submission_page_bytes,
                method="none",
                score=0.0,
                rotation=0,
                homography_meta={"reason": "decode_failed"},
                success=False,
            )

        template_height, template_width = template_image.shape[:2]
        best: AlignmentResult | None = None

        for rotation in (0, 90, 180, 270):
            rotated = self._rotate_image(submission_image, rotation)

            orb_result = self._align_with_features(
                moving=rotated,
                fixed=template_image,
                method_name="orb",
                feature_extractor=cv2.ORB_create(nfeatures=self.ORB_FEATURES),
            )
            candidate = self._build_result(
                raw=orb_result,
                method="orb",
                rotation=rotation,
                fallback_image=rotated,
            )
            best = self._pick_better(best, candidate)
            if candidate.success and candidate.score >= 0.85:
                continue

            akaze_result = self._align_with_features(
                moving=rotated,
                fixed=template_image,
                method_name="akaze",
                feature_extractor=cv2.AKAZE_create(),
            )
            candidate = self._build_result(
                raw=akaze_result,
                method="akaze",
                rotation=rotation,
                fallback_image=rotated,
            )
            best = self._pick_better(best, candidate)
            if candidate.success and candidate.score >= 0.85:
                continue

            ecc_result = self._align_with_ecc(moving=rotated, fixed=template_image)
            candidate = self._build_result(
                raw=ecc_result,
                method="ecc",
                rotation=rotation,
                fallback_image=rotated,
            )
            best = self._pick_better(best, candidate)

        if best is None:
            return AlignmentResult(
                aligned_image_bytes=submission_page_bytes,
                method="none",
                score=0.0,
                rotation=0,
                homography_meta={"reason": "no_candidate"},
                success=False,
            )

        if best.aligned_image_bytes:
            return best

        resized = cv2.resize(submission_image, (template_width, template_height))
        return AlignmentResult(
            aligned_image_bytes=self._encode_png(resized),
            method=best.method,
            score=best.score,
            rotation=best.rotation,
            homography_meta=best.homography_meta,
            success=best.success,
        )

    def _align_with_features(
        self,
        *,
        moving: np.ndarray,
        fixed: np.ndarray,
        method_name: str,
        feature_extractor,
    ) -> dict:
        moving_gray = cv2.cvtColor(moving, cv2.COLOR_BGR2GRAY)
        fixed_gray = cv2.cvtColor(fixed, cv2.COLOR_BGR2GRAY)

        keypoints1, descriptors1 = feature_extractor.detectAndCompute(moving_gray, None)
        keypoints2, descriptors2 = feature_extractor.detectAndCompute(fixed_gray, None)

        if descriptors1 is None or descriptors2 is None:
            return {
                "success": False,
                "score": 0.0,
                "meta": {
                    "method": method_name,
                    "reason": "no_descriptors",
                    "moving_keypoints": len(keypoints1 or []),
                    "fixed_keypoints": len(keypoints2 or []),
                },
            }

        matcher = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
        knn_matches = matcher.knnMatch(descriptors1, descriptors2, k=2)

        good_matches = []
        for pair in knn_matches:
            if len(pair) < 2:
                continue
            m, n = pair
            if m.distance < 0.75 * n.distance:
                good_matches.append(m)

        if len(good_matches) < self.MIN_FEATURE_MATCHES:
            return {
                "success": False,
                "score": min(0.3, len(good_matches) / max(self.MIN_FEATURE_MATCHES, 1)),
                "meta": {
                    "method": method_name,
                    "reason": "insufficient_matches",
                    "good_matches": len(good_matches),
                    "moving_keypoints": len(keypoints1),
                    "fixed_keypoints": len(keypoints2),
                },
            }

        src_pts = np.float32([keypoints1[m.queryIdx].pt for m in good_matches]).reshape(
            -1, 1, 2
        )
        dst_pts = np.float32([keypoints2[m.trainIdx].pt for m in good_matches]).reshape(
            -1, 1, 2
        )

        homography, inlier_mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)
        if homography is None or inlier_mask is None:
            return {
                "success": False,
                "score": 0.0,
                "meta": {
                    "method": method_name,
                    "reason": "homography_failed",
                    "good_matches": len(good_matches),
                },
            }

        inliers = int(inlier_mask.sum())
        inlier_ratio = inliers / max(len(good_matches), 1)
        success = inlier_ratio >= self.MIN_INLIER_RATIO
        warped = cv2.warpPerspective(
            moving, homography, (fixed.shape[1], fixed.shape[0])
        )

        score = max(
            0.0,
            min(
                1.0,
                0.55 * inlier_ratio
                + 0.45 * min(1.0, len(good_matches) / (self.MIN_FEATURE_MATCHES * 2)),
            ),
        )

        return {
            "success": success,
            "score": score,
            "aligned": warped,
            "meta": {
                "method": method_name,
                "moving_keypoints": len(keypoints1),
                "fixed_keypoints": len(keypoints2),
                "good_matches": len(good_matches),
                "inliers": inliers,
                "inlier_ratio": inlier_ratio,
            },
        }

    def _align_with_ecc(self, *, moving: np.ndarray, fixed: np.ndarray) -> dict:
        moving_gray = cv2.cvtColor(moving, cv2.COLOR_BGR2GRAY)
        fixed_gray = cv2.cvtColor(fixed, cv2.COLOR_BGR2GRAY)

        warp_matrix = np.eye(2, 3, dtype=np.float32)
        criteria = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            250,
            1e-6,
        )

        try:
            cc, warp_matrix = cv2.findTransformECC(
                fixed_gray,
                moving_gray,
                warp_matrix,
                cv2.MOTION_AFFINE,
                criteria,
                None,
                1,
            )
            aligned = cv2.warpAffine(
                moving,
                warp_matrix,
                (fixed.shape[1], fixed.shape[0]),
                flags=cv2.INTER_LINEAR + cv2.WARP_INVERSE_MAP,
            )
            score = float(max(0.0, min(1.0, cc)))
            return {
                "success": score >= 0.45,
                "score": score,
                "aligned": aligned,
                "meta": {
                    "method": "ecc",
                    "correlation": score,
                },
            }
        except cv2.error as exc:
            return {
                "success": False,
                "score": 0.0,
                "meta": {
                    "method": "ecc",
                    "reason": f"ecc_failed:{exc.__class__.__name__}",
                },
            }

    def _decode_image(self, image_bytes: bytes) -> np.ndarray | None:
        arr = np.frombuffer(image_bytes, dtype=np.uint8)
        if arr.size == 0:
            return None
        return cv2.imdecode(arr, cv2.IMREAD_COLOR)

    def _encode_png(self, image: np.ndarray) -> bytes:
        ok, encoded = cv2.imencode(".png", image)
        return encoded.tobytes() if ok else b""

    def _rotate_image(self, image: np.ndarray, rotation: int) -> np.ndarray:
        if rotation == 90:
            return cv2.rotate(image, cv2.ROTATE_90_CLOCKWISE)
        if rotation == 180:
            return cv2.rotate(image, cv2.ROTATE_180)
        if rotation == 270:
            return cv2.rotate(image, cv2.ROTATE_90_COUNTERCLOCKWISE)
        return image

    def _build_result(
        self,
        *,
        raw: dict,
        method: str,
        rotation: int,
        fallback_image: np.ndarray,
    ) -> AlignmentResult:
        aligned = raw.get("aligned")
        aligned_bytes = self._encode_png(aligned) if aligned is not None else b""

        if not aligned_bytes:
            aligned_bytes = self._encode_png(fallback_image)

        return AlignmentResult(
            aligned_image_bytes=aligned_bytes,
            method=method,
            score=float(max(0.0, min(1.0, raw.get("score", 0.0)))),
            rotation=rotation,
            homography_meta=raw.get("meta", {}),
            success=bool(raw.get("success", False)),
        )

    def _pick_better(
        self, current: AlignmentResult | None, candidate: AlignmentResult
    ) -> AlignmentResult:
        if current is None:
            return candidate
        if candidate.success and not current.success:
            return candidate
        if candidate.success == current.success and candidate.score > current.score:
            return candidate
        return current


alignment_service = AlignmentService()
