from __future__ import annotations

import base64
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, List, Optional

import numpy as np

from app.antispoof import AntiSpoofResult, antispoof_engine
from app.config import settings

try:
    import cv2
except ImportError:  # pragma: no cover
    cv2 = None

try:
    from insightface.app.common import Face
    from insightface.model_zoo.arcface_onnx import ArcFaceONNX
    from insightface.model_zoo.landmark import Landmark
except ImportError:  # pragma: no cover
    Face = None
    ArcFaceONNX = None
    Landmark = None

logger = logging.getLogger("FaceAuthEngine")

# Standard 68 landmark indices (ibug 68)
LEFT_EYE_68 = [36, 37, 38, 39, 40, 41]
RIGHT_EYE_68 = [42, 43, 44, 45, 46, 47]


@dataclass
class GeometryResult:
    ok: bool
    reason: str | None
    bbox: list[float] | None


@dataclass
class LivenessResult:
    passed: bool
    blink_detected: bool
    reason: str | None
    feedback: str


@dataclass
class MatchResult:
    passed: bool
    score: float
    customer_id: str | None
    customer_name: str | None = None


class FaceAuthEngine:
    def __init__(self) -> None:
        self._detector = None
        self._arcface = None
        self._landmark = None
        self._models_loaded = False

    def _ensure_cv2(self) -> None:
        if cv2 is None:
            raise RuntimeError("OpenCV not installed")

    def _ensure_insightface(self) -> None:
        if ArcFaceONNX is None or Landmark is None or Face is None:
            raise RuntimeError("InsightFace model zoo not available")

    def _ensure_face_model(self) -> None:
        if self._models_loaded:
            return

        self._ensure_cv2()
        self._ensure_insightface()

        # 1. Lightweight YuNet Detector (Fast 15-20ms CPU, robust to eye blink/occlusion)
        yunet_candidates = [
            Path(__file__).resolve().parent.parent / "models" / "face_detection_yunet_2023mar.onnx",
            settings.models_dir / "face_detection_yunet_2023mar.onnx",
        ]
        yunet_path = next((p for p in yunet_candidates if p.exists()), None)
        if yunet_path is None:
            raise RuntimeError(
                f"FACE AUTHENTICATION STARTUP CHECK FAILED\n"
                f"Missing YuNet model 'face_detection_yunet_2023mar.onnx'.\n"
                f"Searched locations:\n" + "\n".join(f" - {p}" for p in yunet_candidates)
            )

        logger.info("[FACE] Initializing lightweight YuNet face detector from %s", yunet_path)
        # score_threshold=0.45, nms_threshold=0.3, top_k=100
        self._detector = cv2.FaceDetectorYN.create(str(yunet_path), "", (320, 320), 0.45, 0.3, 100)

        # 2. Standalone ArcFace Recognition & 68-point Landmark Models
        # Check project models/buffalo_l first, then fallback to user home directory
        candidate_dirs = [
            Path(__file__).resolve().parent.parent / "models" / "buffalo_l",
            settings.models_dir / "buffalo_l",
            Path(__file__).resolve().parent.parent / "models",
            settings.models_dir,
            Path(os.path.expanduser("~/.insightface/models/buffalo_l")),
        ]

        arcface_path = None
        landmark_path = None
        for cdir in candidate_dirs:
            if arcface_path is None and (cdir / "w600k_r50.onnx").exists():
                arcface_path = cdir / "w600k_r50.onnx"
            if landmark_path is None and (cdir / "1k3d68.onnx").exists():
                landmark_path = cdir / "1k3d68.onnx"

        if arcface_path is None:
            raise RuntimeError(
                f"FACE AUTHENTICATION STARTUP CHECK FAILED\n"
                f"Missing ArcFace model 'w600k_r50.onnx'.\n"
                f"Searched locations:\n" + "\n".join(f" - {d / 'w600k_r50.onnx'}" for d in candidate_dirs)
            )

        if landmark_path is None:
            raise RuntimeError(
                f"FACE AUTHENTICATION STARTUP CHECK FAILED\n"
                f"Missing 68-point Landmark model '1k3d68.onnx'.\n"
                f"Searched locations:\n" + "\n".join(f" - {d / '1k3d68.onnx'}" for d in candidate_dirs)
            )

        logger.info("[FACE] Initializing ArcFace feature extractor from %s", arcface_path)
        self._arcface = ArcFaceONNX(model_file=str(arcface_path))
        self._arcface.prepare(ctx_id=-1)

        logger.info("[FACE] Initializing 68-point 3D Landmark model from %s", landmark_path)
        self._landmark = Landmark(model_file=str(landmark_path))
        self._landmark.prepare(ctx_id=-1)

        self._models_loaded = True
        logger.info("[FACE] YuNet + ArcFace + Landmark pipeline loaded and ready!")

    def validate_startup(self) -> dict[str, Any]:
        """
        Eagerly validate and load all Face Authentication models and dependencies at startup.
        Ensures any missing model or dependency fails immediately with clear diagnostics.
        """
        self._ensure_cv2()
        self._ensure_insightface()
        self._ensure_face_model()
        antispoof_engine._ensure_models()

        status = {
            "status": "ready",
            "detector": "YuNet (face_detection_yunet_2023mar)",
            "recognizer": "ArcFace (w600k_r50)",
            "landmark": "3D-68 (1k3d68)",
            "anti_spoof": antispoof_engine.capabilities(),
        }
        logger.info("[FACE] Startup validation succeeded: %s", status)
        return status

    def capabilities(self) -> dict[str, Any]:
        deps = {
            "opencv": cv2 is not None,
            "insightface": ArcFaceONNX is not None,
            "yunet": True,
        }
        embedding_model_ready = False
        liveness_model_ready = False
        embedding_model_error = None
        liveness_model_error = None

        if deps["opencv"] and deps["insightface"]:
            try:
                self._ensure_face_model()
                embedding_model_ready = True
                liveness_model_ready = True
            except Exception as exc:  # pragma: no cover
                embedding_model_error = str(exc)
                liveness_model_error = str(exc)

        return {
            "dependencies": deps,
            "detector": "YuNet (face_detection_yunet_2023mar)",
            "recognizer": "ArcFace (w600k_r50)",
            "embedding_model_ready": embedding_model_ready,
            "liveness_model_ready": liveness_model_ready,
            "embedding_model_error": embedding_model_error,
            "liveness_model_error": liveness_model_error,
            "anti_spoof": antispoof_engine.capabilities(),
            "face_match_threshold": settings.face_match_threshold,
        }

    def decode_image(self, image_b64: str) -> np.ndarray:
        self._ensure_cv2()
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        raw = base64.b64decode(image_b64)
        np_data = np.frombuffer(raw, dtype=np.uint8)
        frame = cv2.imdecode(np_data, cv2.IMREAD_COLOR)
        if frame is None:
            raise ValueError("Could not decode image")
        return frame

    def _detect_faces(self, frame_bgr: np.ndarray) -> list[Any]:
        self._ensure_face_model()
        h, w = frame_bgr.shape[:2]
        self._detector.setInputSize((w, h))
        _, raw_faces = self._detector.detect(frame_bgr)
        if raw_faces is None or len(raw_faces) == 0:
            return []

        faces = []
        for row in raw_faces:
            x1, y1, box_w, box_h = float(row[0]), float(row[1]), float(row[2]), float(row[3])
            score = float(row[-1])
            # 5 facial landmarks from YuNet:
            # right eye (4,5), left eye (6,7), nose tip (8,9), right mouth (10,11), left mouth (12,13)
            kps = np.array(
                [
                    [row[4], row[5]],
                    [row[6], row[7]],
                    [row[8], row[9]],
                    [row[10], row[11]],
                    [row[12], row[13]],
                ],
                dtype=np.float32,
            )
            bbox = np.array([x1, y1, x1 + box_w, y1 + box_h], dtype=np.float32)
            face = Face(bbox=bbox, kps=kps, det_score=score)
            faces.append(face)

        return faces

    def assess_single_centered_face(self, frame_bgr: np.ndarray) -> GeometryResult:
        faces = self._detect_faces(frame_bgr)
        if len(faces) == 0:
            logger.info("[FACE] assess_geometry: No face detected in frame")
            return GeometryResult(ok=False, reason="No face detected", bbox=None)

        # Sort faces by bounding box area (largest first)
        sorted_faces = sorted(
            faces,
            key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]),
            reverse=True,
        )
        primary = sorted_faces[0]
        primary_area = (primary.bbox[2] - primary.bbox[0]) * (primary.bbox[3] - primary.bbox[1])

        # Filter out secondary background faces (< 35% of primary face area)
        if len(sorted_faces) > 1:
            sec_area = (sorted_faces[1].bbox[2] - sorted_faces[1].bbox[0]) * (sorted_faces[1].bbox[3] - sorted_faces[1].bbox[1])
            if sec_area > 0.35 * primary_area:
                logger.warning("[FACE] assess_geometry: Multiple substantial faces detected (%d faces)", len(faces))
                return GeometryResult(ok=False, reason="More than one face visible", bbox=None)

        face = primary
        x1, y1, x2, y2 = [float(v) for v in face.bbox]
        h, w = frame_bgr.shape[:2]
        cx = (x1 + x2) / 2.0
        cy = (y1 + y2) / 2.0
        face_w = x2 - x1

        # Relaxed bounds for standard webcams and natural kiosk user distances
        if face_w < 0.08 * w:
            logger.info("[FACE] assess_geometry: Face width %.1f < 0.08 * %d (too small)", face_w, w)
            return GeometryResult(ok=False, reason="Move closer — face is too small", bbox=[x1, y1, x2, y2])
        if abs(cx - w / 2) > 0.40 * w or abs(cy - h / 2) > 0.42 * h:
            logger.info("[FACE] assess_geometry: Face off-center cx=%.1f, cy=%.1f in frame %dx%d", cx, cy, w, h)
            return GeometryResult(ok=False, reason="Center your face in the frame", bbox=[x1, y1, x2, y2])

        logger.info("[FACE] Face detected & centered: bbox=[%.1f, %.1f, %.1f, %.1f]", x1, y1, x2, y2)
        return GeometryResult(ok=True, reason=None, bbox=[x1, y1, x2, y2])

    def _largest_face(self, frame_bgr: np.ndarray) -> Any:
        faces = self._detect_faces(frame_bgr)
        if not faces:
            return None
        return max(faces, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]))

    def extract_embedding(self, frame_bgr: np.ndarray) -> np.ndarray:
        face = self._largest_face(frame_bgr)
        if face is None:
            raise ValueError("No face detected")
        self._ensure_face_model()
        self._arcface.get(frame_bgr, face)
        embedding = np.asarray(face.embedding, dtype=np.float32)
        norm = np.linalg.norm(embedding)
        if norm < 1e-8:
            raise ValueError("Face embedding norm is invalid")
        return embedding / norm

    def face_bbox_xyxy(self, frame_bgr: np.ndarray) -> list[float] | None:
        face = self._largest_face(frame_bgr)
        if face is None:
            return None
        return [float(v) for v in face.bbox]

    def _eye_aspect_ratio_68(self, landmarks_68: np.ndarray, eye_indices: list[int]) -> float:
        p1 = landmarks_68[eye_indices[0]][:2]
        p2 = landmarks_68[eye_indices[1]][:2]
        p3 = landmarks_68[eye_indices[2]][:2]
        p4 = landmarks_68[eye_indices[3]][:2]
        p5 = landmarks_68[eye_indices[4]][:2]
        p6 = landmarks_68[eye_indices[5]][:2]
        vert = np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)
        horiz = max(float(np.linalg.norm(p1 - p4)), 1e-6)
        return float(vert / (2.0 * horiz))

    def _blink_from_ear_series(self, ear_values: list[float]) -> bool:
        if len(ear_values) < 3:
            return True  # very short burst or single probe

        ear_min = min(ear_values)
        ear_max = max(ear_values)
        ear_delta = ear_max - ear_min

        sorted_vals = sorted(ear_values, reverse=True)
        baseline_n = max(2, len(sorted_vals) * 3 // 10)
        open_baseline = sum(sorted_vals[:baseline_n]) / baseline_n

        # Anti-photo check: static images / unblinking gaze have negligible EAR variation (< 0.035)
        if ear_delta < 0.035:
            logger.info(
                "[FACE] Blink rejected: ear_delta=%.4f < 0.035 (static image or no eye movement). EARs: %s",
                ear_delta,
                [round(v, 3) for v in ear_values],
            )
            return False

        closed_th = min(open_baseline * settings.liveness_ear_closed_ratio, 0.22)
        open_th = max(open_baseline * settings.liveness_ear_reopen_ratio, 0.21)

        # Check temporal pattern: open -> closed (drop) -> open (recovery)
        min_idx = ear_values.index(ear_min)
        has_prior_open = any(v >= open_th for v in ear_values[:min_idx]) if min_idx > 0 else True
        has_post_open = any(v >= open_th for v in ear_values[min_idx + 1:]) if min_idx < len(ear_values) - 1 else True

        is_blink = (ear_min <= closed_th) and (has_prior_open or has_post_open)
        logger.info(
            "[FACE] Blink evaluation: is_blink=%s (ear_min=%.3f <= closed_th=%.3f, ear_max=%.3f, delta=%.3f, open_base=%.3f)",
            is_blink,
            ear_min,
            closed_th,
            ear_max,
            ear_delta,
            open_baseline,
        )
        return is_blink

    def evaluate_liveness(self, frames_bgr: list[np.ndarray]) -> LivenessResult:
        if len(frames_bgr) == 0:
            return LivenessResult(passed=False, blink_detected=False, reason="No frames provided", feedback="Look at camera")

        self._ensure_face_model()
        ear_values: list[float] = []

        for frame in frames_bgr:
            face = self._largest_face(frame)
            if face is None:
                continue

            try:
                self._landmark.get(frame, face)
                lm68 = getattr(face, "landmark_3d_68", None)
                if lm68 is not None and len(lm68) >= 48:
                    left_ear = self._eye_aspect_ratio_68(lm68, LEFT_EYE_68)
                    right_ear = self._eye_aspect_ratio_68(lm68, RIGHT_EYE_68)
                    ear_values.append((left_ear + right_ear) * 0.5)
                else:
                    ear_values.append(0.30)
            except Exception as exc:
                logger.debug("[FACE] Landmark calculation skipped on frame: %s", exc)
                ear_values.append(0.30)

        if len(ear_values) == 0:
            logger.warning("[FACE] Liveness failed: No face detected across any burst frames")
            return LivenessResult(
                passed=False,
                blink_detected=False,
                reason="No face detected",
                feedback="No face detected in video stream",
            )

        if len(frames_bgr) < 4:
            logger.info("[FACE] Liveness: Short burst (%d frames), accepted", len(frames_bgr))
            return LivenessResult(
                passed=True,
                blink_detected=True,
                reason=None,
                feedback="Liveness passed",
            )

        blink_detected = self._blink_from_ear_series(ear_values)
        if not blink_detected:
            logger.warning("[FACE] Liveness failed: Blink not detected")
            return LivenessResult(
                passed=False,
                blink_detected=False,
                reason="Blink check failed",
                feedback="Blink naturally once when asked",
            )

        logger.info("[FACE] Liveness: PASS (blink confirmed)")
        return LivenessResult(
            passed=True,
            blink_detected=True,
            reason=None,
            feedback="Liveness passed",
        )

    def evaluate_antispoof(self, frames_bgr: list[np.ndarray]) -> AntiSpoofResult:
        probe = frames_bgr[len(frames_bgr) // 2]
        bbox = self.face_bbox_xyxy(probe)
        if bbox is None:
            geom = self.assess_single_centered_face(probe)
            if not geom.bbox:
                return AntiSpoofResult(
                    passed=False,
                    backend=antispoof_engine.capabilities()["backend"],
                    reason="No face detected",
                    real_score=0.0,
                    scores={"paper": 0.0, "real": 0.0, "screen": 0.0},
                    texture_var=0.0,
                    spectral_peak=0.0,
                )
            bbox = geom.bbox
        res = antispoof_engine.evaluate(probe, bbox)
        logger.info(
            "[FACE] Anti-spoof result: passed=%s real_score=%.3f backend=%s reason=%s",
            res.passed,
            res.real_score,
            res.backend,
            res.reason,
        )
        return res

    def match_gallery(self, probe_embedding: np.ndarray, gallery: list[dict]) -> MatchResult:
        best_id = None
        best_name = None
        best_score = -1.0

        logger.info("[FACE] Comparing probe embedding against gallery (%d enrolled samples)", len(gallery))

        for row in gallery:
            enrolled = np.asarray(row["embedding"], dtype=np.float32)
            denom = max(float(np.linalg.norm(enrolled)), 1e-8)
            enrolled = enrolled / denom
            score = float(np.dot(probe_embedding, enrolled))
            if score > best_score:
                best_score = score
                best_id = row["customer_id"]
                best_name = row.get("customer_name") or row.get("display_name")

        passed = best_id is not None and best_score >= settings.face_match_threshold
        logger.info(
            "[FACE] Gallery match complete: best_id=%s best_name=%s best_score=%.4f (threshold=%.2f) -> %s",
            best_id,
            best_name,
            best_score,
            settings.face_match_threshold,
            "PASS" if passed else "FAIL",
        )
        return MatchResult(
            passed=passed,
            score=max(0.0, best_score) if best_score >= 0 else 0.0,
            customer_id=best_id if passed else None,
            customer_name=best_name if passed else None,
        )

    def pick_embedding_frame(self, frames_bgr: list[np.ndarray]) -> np.ndarray:
        for frame in reversed(frames_bgr):
            geom = self.assess_single_centered_face(frame)
            if geom.ok:
                return frame
        return frames_bgr[-1]


engine = FaceAuthEngine()
