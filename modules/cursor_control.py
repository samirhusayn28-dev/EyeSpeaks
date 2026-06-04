"""
Module 4: Cursor Controller
===========================
Enhanced Windows Cursor Controller

Features:
- Smooth cursor movement
- Anti-jitter filtering
- Fast response
- Relative & absolute movement
- Mouse clicks
- Scrolling
- Hotkeys
- Typing support
"""

from __future__ import annotations

import ctypes
import time
from dataclasses import dataclass
from typing import Tuple

try:
    import pyautogui
    AVAILABLE = True
except Exception:
    pyautogui = None
    AVAILABLE = False


@dataclass
class ScreenSize:
    width: int
    height: int


class POINT(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_long),
        ("y", ctypes.c_long)
    ]


class CursorController:

    JITTER_THRESHOLD = 1

    def __init__(self):

        self.user32 = ctypes.windll.user32

        if AVAILABLE:
            pyautogui.FAILSAFE = False
            pyautogui.PAUSE = 0

        self._screen = self.get_screen_size()

        self._last_x = 0
        self._last_y = 0

        self._last_move_time = time.time()

    # ---------------------------------------------------------
    # Screen Info
    # ---------------------------------------------------------

    def get_screen_size(self) -> ScreenSize:

        return ScreenSize(
            self.user32.GetSystemMetrics(0),
            self.user32.GetSystemMetrics(1)
        )

    def get_position(self) -> Tuple[int, int]:

        pt = POINT()

        self.user32.GetCursorPos(
            ctypes.byref(pt)
        )

        return pt.x, pt.y

    # ---------------------------------------------------------
    # Core Movement
    # ---------------------------------------------------------

    def move_relative(self, dx: int, dy: int):

        if (
            abs(dx) <= self.JITTER_THRESHOLD and
            abs(dy) <= self.JITTER_THRESHOLD
        ):
            return

        x, y = self.get_position()

        nx = x + dx
        ny = y + dy

        nx = max(
            0,
            min(
                self._screen.width - 1,
                nx
            )
        )

        ny = max(
            0,
            min(
                self._screen.height - 1,
                ny
            )
        )

        self.user32.SetCursorPos(
            int(nx),
            int(ny)
        )

        self._last_x = nx
        self._last_y = ny

    def move_to(self, x: int, y: int):

        x = max(
            0,
            min(
                self._screen.width - 1,
                x
            )
        )

        y = max(
            0,
            min(
                self._screen.height - 1,
                y
            )
        )

        self.user32.SetCursorPos(
            int(x),
            int(y)
        )

        self._last_x = x
        self._last_y = y

    def center_cursor(self):

        self.move_to(
            self._screen.width // 2,
            self._screen.height // 2
        )

    # ---------------------------------------------------------
    # Clicks
    # ---------------------------------------------------------

    def click(self):

        self.user32.mouse_event(
            0x0002,
            0,
            0,
            0,
            0
        )

        self.user32.mouse_event(
            0x0004,
            0,
            0,
            0,
            0
        )

    def right_click(self):

        self.user32.mouse_event(
            0x0008,
            0,
            0,
            0,
            0
        )

        self.user32.mouse_event(
            0x0010,
            0,
            0,
            0,
            0
        )

    def middle_click(self):

        self.user32.mouse_event(
            0x0020,
            0,
            0,
            0,
            0
        )

        self.user32.mouse_event(
            0x0040,
            0,
            0,
            0,
            0
        )

    def double_click(self):

        self.click()
        time.sleep(0.08)
        self.click()

    # ---------------------------------------------------------
    # Scrolling
    # ---------------------------------------------------------

    def scroll(self, amount: int):

        self.user32.mouse_event(
            0x0800,
            0,
            0,
            int(amount * 120),
            0
        )

    def scroll_up(self, amount: int = 3):

        self.scroll(abs(amount))

    def scroll_down(self, amount: int = 3):

        self.scroll(-abs(amount))

    # ---------------------------------------------------------
    # Keyboard
    # ---------------------------------------------------------

    def hotkey(self, *keys):

        if AVAILABLE:
            pyautogui.hotkey(*keys)

    def press(self, key: str):

        if AVAILABLE:
            pyautogui.press(key)

    def write(self, text: str):

        if AVAILABLE:
            pyautogui.write(
                text,
                interval=0.01
            )

    def type_text(self, text: str):

        self.write(text)

    # ---------------------------------------------------------
    # Utility
    # ---------------------------------------------------------

    def refresh_screen_size(self):

        self._screen = self.get_screen_size()

    def stop(self):
        passs