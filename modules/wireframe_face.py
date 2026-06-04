"""
Wireframe Face Renderer - Dense Tech Blue
==========================================
Ultra-dense grid with tech blue color scheme
"""

from __future__ import annotations
import cv2
import numpy as np

try:
    import mediapipe as mp
    _MP_CONNECTIONS = list(mp.solutions.face_mesh.FACEMESH_TESSELATION)
    _MP_CONTOURS   = list(mp.solutions.face_mesh.FACEMESH_CONTOURS)
    _MP_IRISES     = list(mp.solutions.face_mesh.FACEMESH_IRISES)
    # Additional dense connections
    _MP_DENSE = list(mp.solutions.face_mesh.FACEMESH_FACE_OVAL)
except Exception:
    _MP_CONNECTIONS = []
    _MP_CONTOURS   = []
    _MP_IRISES     = []
    _MP_DENSE = []


class WireframeFaceRenderer:
    # Tech Blue Color Scheme
    CLR_BG_TOP      = (5, 8, 15)
    CLR_BG_BOT      = (10, 15, 30)
    CLR_MESH        = (30, 60, 100)
    CLR_CONTOUR     = (150, 200, 255)
    CLR_CONT_GLOW   = (40, 120, 220)
    CLR_IRIS        = (180, 220, 255)
    CLR_IRIS_GLOW   = (50, 140, 230)
    CLR_DOT         = (180, 220, 255)
    CLR_HUD         = (80, 170, 255)
    CLR_GRID        = (60, 130, 210)
    CLR_SCAN        = (70, 160, 240)

    def __init__(self):
        self._frame_count = 0
        self._scan_y      = 0

    def render(self, frame, results,
               show_mesh=True, show_contours=True,
               show_irises=True, show_points=True, show_hud=True):

        h, w = frame.shape[:2]

        # Dark navy gradient background
        canvas = np.zeros((h, w, 3), dtype=np.uint8)
        for row in range(h):
            t = row / max(h - 1, 1)
            b = int(self.CLR_BG_TOP[0] * (1-t) + self.CLR_BG_BOT[0] * t)
            g = int(self.CLR_BG_TOP[1] * (1-t) + self.CLR_BG_BOT[1] * t)
            r = int(self.CLR_BG_TOP[2] * (1-t) + self.CLR_BG_BOT[2] * t)
            canvas[row, :] = (b, g, r)

        self._frame_count += 1

        # Dense scanlines
        for y in range(0, h, 3):
            canvas[y] = np.clip(canvas[y].astype(np.int32) - 20, 0, 255).astype(np.uint8)

        # Moving scan sweep
        self._scan_y = (self._scan_y + 4) % h
        ov = canvas.copy()
        cv2.line(ov, (0, self._scan_y), (w, self._scan_y), self.CLR_SCAN, 2)
        cv2.addWeighted(ov, 0.5, canvas, 0.5, 0, canvas)

        # Grid pattern overlay
        self._draw_grid(canvas, w, h)

        if results is None or not getattr(results, "multi_face_landmarks", None):
            self._no_face(canvas, w, h)
            return canvas

        lms = results.multi_face_landmarks[0].landmark
        pts = np.array([[lm.x * w, lm.y * h] for lm in lms], dtype=np.float32)

        # 1. Dense mesh grid (all connections)
        if show_mesh:
            # Draw tesselation (dense mesh)
            for (i, j) in _MP_CONNECTIONS:
                if i < len(pts) and j < len(pts):
                    cv2.line(canvas,
                             (int(pts[i][0]), int(pts[i][1])),
                             (int(pts[j][0]), int(pts[j][1])),
                             self.CLR_MESH, 1, cv2.LINE_AA)
            
            # Draw additional dense connections
            for (i, j) in _MP_DENSE:
                if i < len(pts) and j < len(pts):
                    cv2.line(canvas,
                             (int(pts[i][0]), int(pts[i][1])),
                             (int(pts[j][0]), int(pts[j][1])),
                             self.CLR_GRID, 1, cv2.LINE_AA)

        # 2. Glowing contours (main face outline)
        if show_contours and _MP_CONTOURS:
            glow = np.zeros_like(canvas)
            for (i, j) in _MP_CONTOURS:
                if i < len(pts) and j < len(pts):
                    cv2.line(glow,
                             (int(pts[i][0]), int(pts[i][1])),
                             (int(pts[j][0]), int(pts[j][1])),
                             self.CLR_CONT_GLOW, 5, cv2.LINE_AA)
            cv2.GaussianBlur(glow, (15, 15), 0, dst=glow)
            cv2.add(canvas, glow, dst=canvas)
            for (i, j) in _MP_CONTOURS:
                if i < len(pts) and j < len(pts):
                    cv2.line(canvas,
                             (int(pts[i][0]), int(pts[i][1])),
                             (int(pts[j][0]), int(pts[j][1])),
                             self.CLR_CONTOUR, 1, cv2.LINE_AA)

        # 3. Glowing iris rings
        if show_irises:
            for idx in [468, 473]:
                if idx < len(pts):
                    cx, cy = int(pts[idx][0]), int(pts[idx][1])
                    gl = np.zeros_like(canvas)
                    cv2.circle(gl, (cx, cy), 18, self.CLR_IRIS_GLOW, 6, cv2.LINE_AA)
                    cv2.GaussianBlur(gl, (15, 15), 0, dst=gl)
                    cv2.add(canvas, gl, dst=canvas)
                    cv2.circle(canvas, (cx, cy), 18, self.CLR_IRIS, 1, cv2.LINE_AA)
                    cv2.circle(canvas, (cx, cy),  8, self.CLR_IRIS, 1, cv2.LINE_AA)
                    cv2.circle(canvas, (cx, cy),  2, self.CLR_IRIS,-1)

        # 4. Dense landmark dots
        if show_points:
            # All facial landmarks
            for idx in range(len(pts)):
                if idx < len(pts):
                    cv2.circle(canvas, (int(pts[idx][0]), int(pts[idx][1])),
                               2, self.CLR_DOT, -1, cv2.LINE_AA)

        # 5. HUD elements
        if show_hud:
            self._hud(canvas, w, h, len(pts))

        return canvas

    def _draw_grid(self, canvas, w, h):
        """Draw dense tech grid pattern"""
        grid_spacing = 40
        for x in range(0, w, grid_spacing):
            cv2.line(canvas, (x, 0), (x, h), (15, 25, 45), 1)
        for y in range(0, h, grid_spacing):
            cv2.line(canvas, (0, y), (w, y), (15, 25, 45), 1)

    def _hud(self, canvas, w, h, n):
        m, s, tk = 20, 30, 2
        c = self.CLR_HUD
        for (cx, cy, sx, sy) in [(m,m,1,1),(w-m,m,-1,1),(m,h-m,1,-1),(w-m,h-m,-1,-1)]:
            cv2.line(canvas,(cx,cy),(cx+sx*s,cy),c,tk)
            cv2.line(canvas,(cx,cy),(cx,cy+sy*s),c,tk)
        if (self._frame_count // 12) % 2 == 0:
            cv2.circle(canvas, (w-m-8, m+8), 6, (150,200,255), -1)
        font, fsc = cv2.FONT_HERSHEY_SIMPLEX, 0.4
        for i, txt in enumerate(["NEURAL SCAN ACTIVE", f"NODES : {n}", "TRACKING: STABLE", "MODE: TECH BLUE"]):
            cv2.putText(canvas, txt, (m+4, m+22+i*18), font, fsc, c, 1, cv2.LINE_AA)

    def _no_face(self, canvas, w, h):
        self._hud(canvas, w, h, 0)
        font = cv2.FONT_HERSHEY_SIMPLEX
        txt  = "SCANNING FOR FACE..."
        sz   = cv2.getTextSize(txt, font, 0.7, 1)[0]
        if (self._frame_count // 20) % 2 == 0:
            cv2.putText(canvas, txt, ((w-sz[0])//2, h//2),
                        font, 0.7, self.CLR_CONTOUR, 1, cv2.LINE_AA)