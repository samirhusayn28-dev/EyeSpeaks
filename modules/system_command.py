"""
Module 6: System Command Executor
"""
from __future__ import annotations
import platform, subprocess, pyautogui

pyautogui.FAILSAFE = False
pyautogui.PAUSE = 0.05
OS_NAME = platform.system()

APP_MAP = {"chrome": "chrome", "notepad": "notepad", "calculator": "calc", "paint": "mspaint", "edge": "msedge"}

class SystemCommandExecutor:
    def __init__(self):
        self._typing_mode = False

    def execute(self, action: str, params: dict = None) -> str:
        if params is None: params = {}
        handler = getattr(self, f"_handle_{action}", self._handle_UNKNOWN)
        return handler(params)
    
    def _handle_TYPE_TEXT(self, p):
        if self._typing_mode: pyautogui.write(p.get("text", ""), interval=0.03)
        return "Typed"
    
    def _handle_TYPE_MODE_ON(self, p): 
        self._typing_mode = True; return "Typing ON"
        
    def _handle_TYPE_MODE_OFF(self, p): 
        self._typing_mode = False; return "Typing OFF"
    
    def _handle_ZOOM(self, p):
        d = p.get("direction", "in")
        pyautogui.hotkey('ctrl', '+' if d == 'in' else '-')
        return f"Zoom {d}"
    
    def _handle_SCROLL(self, p):
        d = p.get("direction", "down")
        amt = p.get("amount", 300)
        pyautogui.scroll(amt if d == 'up' else -amt)
        return f"Scroll {d}"
    
    def _handle_MOUSE_CLICK(self, p):
        t = p.get("type", "left")
        if t == "right": pyautogui.rightClick()
        elif t == "double": pyautogui.doubleClick()
        else: pyautogui.click()
        return f"{t} click"
    
    def _handle_VOLUME(self, p):
        d = p.get("direction", "up")
        key = 'volumeup' if d == 'up' else 'volumedown'
        for _ in range(3): pyautogui.press(key)
        return f"Volume {d}"
    
    def _handle_OPEN_APP(self, p):
        app = p.get("app", "").lower()
        exe = APP_MAP.get(app, app)
        subprocess.Popen(exe, shell=True)
        return f"Opening {app}"
    
    def _handle_CLOSE_APP(self, p):
        pyautogui.hotkey('alt', 'f4')
        return "Closing App"
    
    def _handle_CLIPBOARD(self, p):
        a = p.get("action", "copy")
        pyautogui.hotkey('ctrl', a[0])
        return a.capitalize()
    
    def _handle_UNKNOWN(self, p):
        return "Unknown Action"