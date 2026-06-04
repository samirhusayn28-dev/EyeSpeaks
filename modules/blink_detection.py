"""
Module 3: Blink Detection - Balanced for Both Eyes
==================================================
"""
from __future__ import annotations
import time
from collections import deque
import numpy as np

LEFT_EYE_EAR_PTS  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_EAR_PTS = [362, 385, 387, 263, 373, 380]

def _ear(landmarks, eye_indices, frame_shape):
    h, w = frame_shape[:2]
    def pt(idx):
        lm = landmarks[idx]
        return np.array([lm.x * w, lm.y * h], dtype=np.float64)
    p1, p2, p3, p4, p5, p6 = [pt(i) for i in eye_indices]
    return (np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5)) / (2.0 * np.linalg.norm(p1 - p4) + 1e-6)


class BlinkDetector:
    # ── Separate baseline thresholds per eye ──────────────────────────────
    LEFT_THRESHOLD  = 0.24   # Left eye naturally higher EAR → higher cutoff
    RIGHT_THRESHOLD = 0.21

    COOLDOWN     = 0.80
    MIN_FRAMES   = 3         # 3 frames enough — reduces missed detections
    HISTORY_SIZE = 4         # Smaller window → faster response

    # ── Adaptive calibration ──────────────────────────────────────────────
    CALIB_FRAMES   = 60      # First 60 frames = calibration window
    CALIB_RATIO    = 0.75    # threshold = open_avg * 0.75

    def __init__(self):
        self._left_calib : deque = deque(maxlen=self.CALIB_FRAMES)
        self._right_calib: deque = deque(maxlen=self.CALIB_FRAMES)
        self._calibrated  = False
        self._left_thresh  = self.LEFT_THRESHOLD
        self._right_thresh = self.RIGHT_THRESHOLD
        self.reset()

    def reset(self):
        self._last_action        = 0.0
        self._left_history       = deque(maxlen=self.HISTORY_SIZE)
        self._right_history      = deque(maxlen=self.HISTORY_SIZE)
        self._left_closed_streak  = 0
        self._right_closed_streak = 0

    # ── Auto-calibration from real open-eye baseline ──────────────────────
    def _maybe_calibrate(self, raw_left: float, raw_right: float):
        if self._calibrated:
            return

        # Only collect frames where BOTH eyes are clearly open
        if raw_left > 0.20 and raw_right > 0.20:
            self._left_calib.append(raw_left)
            self._right_calib.append(raw_right)

        if len(self._left_calib) >= self.CALIB_FRAMES:
            self._left_thresh  = float(np.mean(self._left_calib))  * self.CALIB_RATIO
            self._right_thresh = float(np.mean(self._right_calib)) * self.CALIB_RATIO
            self._calibrated   = True
            print(f"[BlinkDetector] Calibrated → "
                  f"L={self._left_thresh:.3f}  R={self._right_thresh:.3f}")

    def detect(self, frame, results, threshold_scale: float = None):
        if results is None or not getattr(results, "multi_face_landmarks", None):
            self.reset()
            return None

        lms = results.multi_face_landmarks[0].landmark
        now = time.monotonic()

        raw_left  = _ear(lms, LEFT_EYE_EAR_PTS,  frame.shape)
        raw_right = _ear(lms, RIGHT_EYE_EAR_PTS, frame.shape)

        # Feed calibration window
        self._maybe_calibrate(raw_left, raw_right)

        # Use calibrated OR manual override thresholds
        l_thresh = threshold_scale if threshold_scale else self._left_thresh
        r_thresh = threshold_scale if threshold_scale else self._right_thresh

        self._left_history.append(raw_left)
        self._right_history.append(raw_right)
        avg_left  = float(np.mean(self._left_history))
        avg_right = float(np.mean(self._right_history))

        left_closed  = avg_left  < l_thresh
        right_closed = avg_right < r_thresh

        # Both closed → normal blink, ignore
        if left_closed and right_closed:
            self._left_closed_streak  = 0
            self._right_closed_streak = 0
            return None

        # ── Left Wink ─────────────────────────────────────────────────────
        if left_closed and not right_closed:
            self._left_closed_streak  += 1
            self._right_closed_streak  = 0
            if (self._left_closed_streak >= self.MIN_FRAMES
                    and now - self._last_action >= self.COOLDOWN):
                self._last_action        = now
                self._left_closed_streak = 0
                return "left_click"
        else:
            self._left_closed_streak = 0

        # ── Right Wink ────────────────────────────────────────────────────
        if right_closed and not left_closed:
            self._right_closed_streak += 1
            self._left_closed_streak   = 0
            if (self._right_closed_streak >= self.MIN_FRAMES
                    and now - self._last_action >= self.COOLDOWN):
                self._last_action         = now
                self._right_closed_streak = 0
                return "right_click"
        else:
            self._right_closed_streak = 0

        return None

    # ── Debug helper ──────────────────────────────────────────────────────
    def debug_info(self, frame, results) -> dict | None:
        """Call this in your display loop to print live EAR values."""
        if results is None or not getattr(results, "multi_face_landmarks", None):
            return None
        lms = results.multi_face_landmarks[0].landmark
        return {
            "left_ear"   : round(_ear(lms, LEFT_EYE_EAR_PTS,  frame.shape), 3),
            "right_ear"  : round(_ear(lms, RIGHT_EYE_EAR_PTS, frame.shape), 3),
            "l_thresh"   : round(self._left_thresh,  3),
            "r_thresh"   : round(self._right_thresh, 3),
            "calibrated" : self._calibrated,
        }