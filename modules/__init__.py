"""
EyeSpeaks Modules Package
=========================
Safe lazy imports for all core modules.
"""

from __future__ import annotations
from importlib import import_module
from typing import Any, Optional


def _safe_import(module_name: str, attr_name: str) -> Optional[Any]:
    try:
        module = import_module(f".{module_name}", __name__)
        return getattr(module, attr_name)
    except Exception as e:
        print(f"[Module Load Failed] {module_name}: {e}")
        return None


FaceDetector = _safe_import("face_detection", "FaceDetector")
EyeTracker = _safe_import("eye_tracking", "EyeTracker")
BlinkDetector = _safe_import("blink_detection", "BlinkDetector")
CursorController = _safe_import("cursor_control", "CursorController")
VoiceRecognizer = _safe_import("voice_recognition", "VoiceRecognizer")
SystemCommandExecutor = _safe_import("system_command", "SystemCommandExecutor")

__all__ = [
    name for name in [
        "FaceDetector", "EyeTracker", "BlinkDetector",
        "CursorController", "VoiceRecognizer", "SystemCommandExecutor",
    ]
    if globals().get(name) is not None
]