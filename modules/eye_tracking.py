"""
Module 2: Eye Tracking - Ultra Fast Cursor
==========================================
Head = 85%
Eyes = 15%
"""

from __future__ import annotations
import numpy as np
from collections import deque

LEFT_IRIS = [468, 469, 470, 471, 472]
RIGHT_IRIS = [473, 474, 475, 476, 477]

LEFT_EYE_INNER = 133
LEFT_EYE_OUTER = 33
LEFT_EYE_TOP = 159
LEFT_EYE_BOTTOM = 145

RIGHT_EYE_INNER = 362
RIGHT_EYE_OUTER = 263
RIGHT_EYE_TOP = 386
RIGHT_EYE_BOTTOM = 374

NOSE_TIP = 4
LEFT_CHEEK = 234
RIGHT_CHEEK = 454
FOREHEAD = 10
CHIN = 152


class EyeTracker:

    CALIBRATION_FRAMES = 20

    HEAD_WEIGHT = 0.88
    EYE_WEIGHT = 0.12

    DEAD_ZONE_X = 0.10
    DEAD_ZONE_Y = 0.10

    SPEED_X = 85  # Increased from 55 to 85
    SPEED_Y = 85  # Increased from 55 to 85

    MAX_DELTA = 90  # Increased from 65 to 90

    SMOOTHING = 0.65

    DRIFT_CORRECTION = 0.02

    def __init__(self):

        self.calibrated = False
        self.frame_count = 0

        self.base_head = np.zeros(2, dtype=np.float64)
        self.base_eye = np.zeros(2, dtype=np.float64)

        self.head_samples = deque(maxlen=self.CALIBRATION_FRAMES)
        self.eye_samples = deque(maxlen=self.CALIBRATION_FRAMES)

        self.prev_dx = 0.0
        self.prev_dy = 0.0
        
        self.drift_x = 0.0
        self.drift_y = 0.0
        self.no_move_frames = 0

    def reset(self):

        self.calibrated = False
        self.frame_count = 0

        self.base_head[:] = 0
        self.base_eye[:] = 0

        self.head_samples.clear()
        self.eye_samples.clear()

        self.prev_dx = 0
        self.prev_dy = 0
        self.drift_x = 0
        self.drift_y = 0
        self.no_move_frames = 0

    def _pt(self, lm, w, h):
        return np.array(
            [lm.x * w, lm.y * h],
            dtype=np.float64
        )

    def _iris_center(self, lms, indices, w, h):

        pts = [
            self._pt(lms[i], w, h)
            for i in indices
        ]

        return np.mean(pts, axis=0)

    def _eye_signal(self, iris, inner, outer, top, bottom):

        gx = (
            (iris[0] - inner[0]) /
            (outer[0] - inner[0] + 1e-6)
        ) - 0.5

        gy = (
            (iris[1] - top[1]) /
            (bottom[1] - top[1] + 1e-6)
        ) - 0.5

        return np.array(
            [gx * 2.0, gy * 2.0],
            dtype=np.float64
        )

    def update(self, frame, results):

        if (
            results is None or
            not getattr(results, "multi_face_landmarks", None)
        ):
            self.no_move_frames += 1
            if self.no_move_frames > 10:
                self.drift_x *= 0.95
                self.drift_y *= 0.95
            return 0, 0, {"status": "no_face"}

        h, w = frame.shape[:2]

        lms = results.multi_face_landmarks[0].landmark

        # --------------------------------------------------
        # EYE SIGNAL
        # --------------------------------------------------

        left_iris = self._iris_center(
            lms,
            LEFT_IRIS,
            w,
            h
        )

        right_iris = self._iris_center(
            lms,
            RIGHT_IRIS,
            w,
            h
        )

        left_eye = self._eye_signal(
            left_iris,
            self._pt(lms[LEFT_EYE_INNER], w, h),
            self._pt(lms[LEFT_EYE_OUTER], w, h),
            self._pt(lms[LEFT_EYE_TOP], w, h),
            self._pt(lms[LEFT_EYE_BOTTOM], w, h),
        )

        right_eye = self._eye_signal(
            right_iris,
            self._pt(lms[RIGHT_EYE_INNER], w, h),
            self._pt(lms[RIGHT_EYE_OUTER], w, h),
            self._pt(lms[RIGHT_EYE_TOP], w, h),
            self._pt(lms[RIGHT_EYE_BOTTOM], w, h),
        )

        eye_signal = (
            left_eye + right_eye
        ) / 2.0

        # --------------------------------------------------
        # HEAD SIGNAL
        # --------------------------------------------------

        nose = self._pt(
            lms[NOSE_TIP],
            w,
            h
        )

        left_cheek = self._pt(
            lms[LEFT_CHEEK],
            w,
            h
        )

        right_cheek = self._pt(
            lms[RIGHT_CHEEK],
            w,
            h
        )

        forehead = self._pt(
            lms[FOREHEAD],
            w,
            h
        )

        chin = self._pt(
            lms[CHIN],
            w,
            h
        )

        face_center_x = (
            left_cheek[0] +
            right_cheek[0]
        ) / 2.0

        face_center_y = (
            forehead[1] +
            chin[1]
        ) / 2.0

        face_width = (
            np.linalg.norm(
                right_cheek - left_cheek
            ) + 1e-6
        )

        face_height = (
            np.linalg.norm(
                forehead - chin
            ) + 1e-6
        )

        head_signal = np.array(
            [
                ((nose[0] - face_center_x) / face_width) * 2.0,
                ((nose[1] - face_center_y) / face_height) * 2.0,
            ],
            dtype=np.float64,
        )

        # --------------------------------------------------
        # CALIBRATION
        # --------------------------------------------------

        if not self.calibrated:

            self.head_samples.append(
                head_signal.copy()
            )

            self.eye_samples.append(
                eye_signal.copy()
            )

            self.frame_count += 1

            if (
                self.frame_count >=
                self.CALIBRATION_FRAMES
            ):
                self.base_head = np.mean(
                    self.head_samples,
                    axis=0
                )

                self.base_eye = np.mean(
                    self.eye_samples,
                    axis=0
                )

                self.calibrated = True

            return 0, 0, {
                "status": "calibrating",
                "frames": self.frame_count
            }

        # --------------------------------------------------
        # RELATIVE MOVEMENT
        # --------------------------------------------------

        head_rel = (
            head_signal - self.base_head
        )

        eye_rel = (
            eye_signal - self.base_eye
        )

        movement = (
            head_rel * self.HEAD_WEIGHT
        ) + (
            eye_rel * self.EYE_WEIGHT
        )

        # Dead zone
        if abs(movement[0]) < self.DEAD_ZONE_X:
            movement[0] = 0

        if abs(movement[1]) < self.DEAD_ZONE_Y:
            movement[1] = 0
            self.no_move_frames += 1
        else:
            self.no_move_frames = 0

        # Drift correction
        if self.no_move_frames > 5:
            self.drift_x *= 0.90
            self.drift_y *= 0.90

        # Cursor speed - INCREASED
        dx_target = (
            movement[0] *
            self.SPEED_X
        )

        dy_target = (
            movement[1] *
            self.SPEED_Y
        )

        dx_target = np.clip(
            dx_target,
            -self.MAX_DELTA,
            self.MAX_DELTA
        )

        dy_target = np.clip(
            dy_target,
            -self.MAX_DELTA,
            self.MAX_DELTA
        )

        dx = (
            self.prev_dx * self.SMOOTHING
        ) + (
            dx_target * (1 - self.SMOOTHING)
        )

        dy = (
            self.prev_dy * self.SMOOTHING
        ) + (
            dy_target * (1 - self.SMOOTHING)
        )

        self.prev_dx = dx
        self.prev_dy = dy

        return (
            int(round(dx)),
            int(round(dy)),
            {
                "status": "ok",
                "dx": int(round(dx)),
                "dy": int(round(dy)),
                "head": head_rel.tolist(),
                "eye": eye_rel.tolist(),
            },
        )

    def track(self, frame, results):
        return self.update(frame, results)