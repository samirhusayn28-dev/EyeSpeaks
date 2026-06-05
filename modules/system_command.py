"""
Module 6: System Command Executor - All Actions
"""

from __future__ import annotations
import platform
import subprocess
import pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05

OS_NAME = platform.system()

APP_MAP = {
    "chrome": "chrome",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
    "paint": "mspaint",
    "edge": "msedge",
    "word": "winword",
    "excel": "excel",
}


class SystemCommandExecutor:
    def __init__(self):
        self._typing_mode = False

    def execute(self, action: str, params: dict = None) -> str:
        if params is None:
            params = {}
        
        handler = getattr(self, f"_handle_{action}", self._handle_UNKNOWN)
        
        try:
            return handler(params)
        except Exception as e:
            return f"Error: {str(e)}"
    
    def _handle_TYPE_TEXT(self, p):
        text = p.get("text", "")
        if self._typing_mode:
            pyautogui.write(text, interval=0.03)
        return f"Typed: {text[:30]}"
    
    def _handle_TYPE_MODE_ON(self, p):
        self._typing_mode = True
        return "Typing mode ON"
        
    def _handle_TYPE_MODE_OFF(self, p):
        self._typing_mode = False
        return "Typing mode OFF"
    
    def _handle_SCROLL(self, p):
        direction = p.get("direction", "down")
        amount = p.get("amount", 300)
        scroll_amount = amount if direction == 'up' else -amount
        pyautogui.scroll(scroll_amount)
        return f"Scrolled {direction}"
    
    def _handle_MOUSE_CLICK(self, p):
        click_type = p.get("type", "left")
        if click_type == "right":
            pyautogui.rightClick()
        elif click_type == "double":
            pyautogui.doubleClick()
        else:
            pyautogui.click()
        return f"{click_type} click"
    
    def _handle_ZOOM(self, p):
        direction = p.get("direction", "in")
        key = '+' if direction == 'in' else '-'
        pyautogui.hotkey('ctrl', key)
        return f"Zoom {direction}"
    
    def _handle_VOLUME(self, p):
        direction = p.get("direction", "up")
        if direction == "mute":
            pyautogui.press('volumemute')
            return "Volume muted"
        key = 'volumeup' if direction == 'up' else 'volumedown'
        for _ in range(3):
            pyautogui.press(key)
        return f"Volume {direction}"
    
    def _handle_OPEN_APP(self, p):
        app = p.get("app", "").lower()
        exe = APP_MAP.get(app, app)
        try:
            subprocess.Popen(exe, shell=True)
            return f"Opening {app}"
        except Exception as e:
            return f"Failed to open {app}: {str(e)}"
    
    def _handle_CLOSE_APP(self, p):
        pyautogui.hotkey('alt', 'f4')
        return "Closing app"
    
    def _handle_WINDOW_CONTROL(self, p):
        action = p.get("action", "maximize")
        if action == "minimize":
            pyautogui.hotkey('win', 'down')
        elif action == "maximize":
            pyautogui.hotkey('win', 'up')
        return f"Window {action}"
    
    def _handle_CLIPBOARD(self, p):
        action = p.get("action", "copy")
        key_map = {"copy": "c", "paste": "v", "cut": "x", "undo": "z", "redo": "y"}
        key = key_map.get(action, action[0])
        pyautogui.hotkey('ctrl', key)
        return f"{action.capitalize()}"
    
    def _handle_MEDIA(self, p):
        action = p.get("action", "play")
        key_map = {"play": "playpause", "pause": "playpause", "next": "next", "previous": "previous"}
        pyautogui.press(key_map.get(action, action))
        return f"Media {action}"
    
    def _handle_BRIGHTNESS(self, p):
        direction = p.get("direction", "up")
        key = 'brightnessup' if direction == 'up' else 'brightnessdown'
        for _ in range(3):
            pyautogui.press(key)
        return f"Brightness {direction}"
    
    def _handle_SCREENSHOT(self, p):
        pyautogui.hotkey('win', 'shift', 's')
        return "Screenshot taken"
    
    def _handle_LOCK_SCREEN(self, p):
        pyautogui.hotkey('win', 'l')
        return "Screen locked"
    
    def _handle_UNKNOWN(self, p):
        return f"Unknown action"