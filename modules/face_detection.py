"""
Module 1: Face Detection
========================
Optimized MediaPipe Face Mesh wrapper
✅ FIXED: Real camera feed ki jagah Wireframe face render hota hai
"""

from __future__ import annotations
from typing import Optional
import cv2
import numpy as np

try:
    import mediapipe as mp
except Exception as e:
    raise ImportError("MediaPipe not installed. Run: pip install mediapipe") from e

from .wireframe_face import WireframeFaceRenderer  # <-- new import


class FaceDetector:
    LEFT_EYE_OUTLINE  = [33, 160, 158, 133, 153, 144]
    RIGHT_EYE_OUTLINE = [362, 385, 387, 263, 373, 380]
    LEFT_IRIS         = [468, 469, 470, 471, 472]
    RIGHT_IRIS        = [473, 474, 475, 476, 477]
    NOSE_TIP          = 4
    LEFT_CHEEK        = 234
    RIGHT_CHEEK       = 454
    FOREHEAD          = 10
    CHIN              = 152

    def __init__(self, max_faces: int = 1, refine_landmarks: bool = True):
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=max_faces,
            refine_landmarks=refine_landmarks,
            min_detection_confidence=0.6,
            min_tracking_confidence=0.6,
            static_image_mode=False,
        )
        self._rgb_buf: Optional[np.ndarray] = None
        self._wireframe = WireframeFaceRenderer()   # ← wireframe renderer

    # ──────────────────────────────────────────
    def detect(self, frame: np.ndarray):
        if frame is None or frame.size == 0:
            return None

        if self._rgb_buf is None or self._rgb_buf.shape != frame.shape:
            self._rgb_buf = np.empty_like(frame)

        cv2.cvtColor(frame, cv2.COLOR_BGR2RGB, dst=self._rgb_buf)
        self._rgb_buf.flags.writeable = False

        try:
            results = self.face_mesh.process(self._rgb_buf)
        finally:
            self._rgb_buf.flags.writeable = True

        return (
            results
            if results and getattr(results, "multi_face_landmarks", None)
            else None
        )

    # ──────────────────────────────────────────
    def draw_landmarks(self, frame: np.ndarray, results, draw_bbox: bool = True):
        """
        ✅ CHANGED: Real face ko black canvas se replace karta hai
        aur uske upar wireframe face draw karta hai.
        Frame in-place modify hota hai (camera worker compatible).
        """
        if frame is None:
            return frame

        # Wireframe render karo (results=None bhi handle hota hai)
        wireframe = self._wireframe.render(frame, results)

        # frame ke pixels ko wireframe se in-place replace karo
        # (CameraWorker sirf frame use karta hai QImage ke liye)
        np.copyto(frame, wireframe)
        return frame

    # ──────────────────────────────────────────
    def close(self):
        try:
            self.face_mesh.close()
        except Exception:
            pass

    def __del__(self):
        self.close()