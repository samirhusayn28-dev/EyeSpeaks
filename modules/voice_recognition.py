"""
Module 5: Voice Recognition - Smart AI Controller + Mic Auto-Retry
"""
from __future__ import annotations
import os, threading, json, time, re
from typing import Callable, Optional

try:
    from google import genai
    GEMINI_AVAILABLE = True
except:
    genai = None
    GEMINI_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except:
    sr = None
    SR_AVAILABLE = False

class DynamicAIController:
    def __init__(self, api_key: str):
        self.api_key = api_key.strip()
        self.client = None
        self.model = None
        self.initialized = False
        self.typing_mode = False
        
        if not self.api_key or self.api_key == "AIzaSyAcS2jI78hkskdRDac46AEueGqQwRr2UsA":
            print("[AI] No valid API key")
            return
            
        try:
            self.client = genai.Client(api_key=self.api_key)
            self.model = "gemini-2.0-flash-exp"
            self.initialized = True
            print("[AI] AI Controller Initialized")
        except Exception as e:
            print(f"[AI] Init failed: {e}")

    def understand_and_act(self, user_command: str) -> dict:
        if not user_command.strip():
            return {"action": "NONE", "params": {}, "message": ""}
        
        if self.typing_mode and user_command.lower() not in ["stop typing", "type mode off", "band karo", "ruk jao"]:
            return {"action": "TYPE_TEXT", "params": {"text": user_command}, "message": f"Typing..."}

        if not self.initialized:
            return {"action": "ERROR", "params": {}, "message": "AI Not Ready"}
        
        try:
            prompt = f"""You control a PC. The user said: "{user_command}"
Current state: Typing Mode is {"ON" if self.typing_mode else "OFF"}.

You MUST reply with ONLY a JSON object. No text, no markdown.
Format: {{"action": "ACTION_NAME", "params": {{"key": "value"}}, "message": "Short status"}}

Available Actions:
- TYPE_TEXT (params: {{"text": "..."}})
- TYPE_MODE_ON / TYPE_MODE_OFF (params: {{}})
- SCROLL (params: {{"direction": "up" or "down"}})
- MOUSE_CLICK (params: {{"type": "left", "right", or "double"}})
- ZOOM (params: {{"direction": "in" or "out"}})
- VOLUME (params: {{"direction": "up" or "down"}})
- OPEN_APP (params: {{"app": "chrome", "notepad", "calculator"}})
- CLOSE_APP (params: {{}})
- CLIPBOARD (params: {{"action": "copy", "paste", "cut"}})
- NONE (if chatting)

Understand Urdu/English naturally. Reply JSON only:"""

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config={'temperature': 0.1, 'max_output_tokens': 100}
            )
            
            if response and response.text:
                json_match = re.search(r'\{.*\}', response.text, re.DOTALL)
                if json_match:
                    data = json.loads(json_match.group())
                    return {
                        "action": data.get("action", "UNKNOWN"),
                        "params": data.get("params", {}),
                        "message": data.get("message", "Done")
                    }
            
            return {"action": "UNKNOWN", "params": {}, "message": "AI Confused"}
            
        except Exception as e:
            return {"action": "ERROR", "params": {}, "message": f"Error: {str(e)[:30]}"}

    def set_typing_mode(self, mode: bool):
        self.typing_mode = mode


class VoiceRecognizer:
    def __init__(self, callback: Optional[Callable[[str, dict], None]] = None, gemini_api_key: Optional[str] = None):
        self.callback = callback
        self._running = False
        self._stop_listening = None
        self._processing = False
        self._lock = threading.Lock()

        _key = (gemini_api_key or os.environ.get("GEMINI_API_KEY", "")).strip()
        self.ai = DynamicAIController(_key) if (_key and GEMINI_AVAILABLE) else None

        self._recognizer = None
        self._microphone = None
        self._mic_ok = False
        self._mic_attempts = 0
        
        self._load_microphone()

    def _load_microphone(self):
        if not SR_AVAILABLE: return
        
        # Auto-retry logic for Mic (Windows PyAudio glitch fix)
        for attempt in range(4):
            try:
                print(f"[Voice] Initializing Mic... (Attempt {attempt+1})")
                mics = sr.Microphone.list_microphone_names()
                if not mics: 
                    print("[Voice] No mics found, retrying...")
                    time.sleep(2)
                    continue
                
                self._recognizer = sr.Recognizer()
                self._recognizer.dynamic_energy_threshold = True
                self._recognizer.energy_threshold = 400
                self._recognizer.pause_threshold = 0.6
                
                self._microphone = sr.Microphone()
                
                # Test mic
                with self._microphone as source:
                    self._recognizer.adjust_for_ambient_noise(source, duration=0.8)
                
                self._mic_ok = True
                self._mic_attempts = 0
                print(f"[Voice] ✅ Mic Ready: {mics[0]}")
                return # Success, exit loop
                
            except Exception as e:
                print(f"[Voice] Mic attempt {attempt+1} failed: {e}")
                self._mic_ok = False
                time.sleep(2) # Wait before retrying
                
        print("[Voice] ❌ Mic failed after 4 attempts.")

    def retry_mic(self):
        """Call this from main.py if mic fails"""
        self._mic_ok = False
        self._load_microphone()

    def start(self):
        if self._running or not self._mic_ok: return
        self._running = True
        try:
            with self._microphone as source:
                self._recognizer.adjust_for_ambient_noise(source, duration=0.5)
            self._stop_listening = self._recognizer.listen_in_background(
                self._microphone, self._background_callback, phrase_time_limit=4
            )
            print("[Voice] 🎤 Listening started...")
        except Exception as e:
            self._running = False
            print(f"[Voice] Start failed: {e}")

    def stop(self):
        self._running = False
        try:
            if callable(self._stop_listening): self._stop_listening(wait_for_stop=False)
        except: pass

    def _background_callback(self, recognizer, audio):
        if not self._running: return
        with self._lock:
            if self._processing: return
            self._processing = True
        try:
            text = self._transcribe(audio)
            if text:
                self._deliver(text)
        finally:
            self._processing = False

    def _transcribe(self, audio) -> str:
        try:
            return self._recognizer.recognize_google(audio, language="en-US").strip()
        except:
            return ""

    def _deliver(self, text: str):
        if not text or not self.callback: return
        response = self.ai.understand_and_act(text) if self.ai else {"action": "ERROR", "params": {}, "message": "No AI"}
        try:
            self.callback(text, response)
        except Exception as e:
            print(f"[Voice] Callback error: {e}")

    def __del__(self):
        self.stop()