"""
Module 5: Voice Recognition - EyeSpeaks
=========================================
Architecture: AI-FIRST (truly dynamic)
  1. Typing-mode passthrough  — instant
  2. Groq AI  (llama-3.3-70b-versatile, ≤5 s)  — understands ANY command
  3. Local keyword fallback   — only if AI is offline/times out

Why llama-3.3-70b-versatile?
  - Much better instruction-following than 8b; reliably outputs JSON-only
  - Still fast on Groq (~1-2 s for short prompts)
  - Handles Urdu/English mix, numeric params, arbitrary app names
"""

from __future__ import annotations
import os
import threading
import json
import time
import re
from typing import Callable, Optional

try:
    from groq import Groq
    GROQ_AVAILABLE = True
except ImportError:
    Groq = None
    GROQ_AVAILABLE = False

try:
    import speech_recognition as sr
    SR_AVAILABLE = True
except ImportError:
    sr = None
    SR_AVAILABLE = False


# ──────────────────────────────────────────────────────────────────────────────
# AI PROMPT  —  short, dense, example-heavy so the model never guesses wrong
# ──────────────────────────────────────────────────────────────────────────────

_SYSTEM = """\
You are a voice-command parser for a Windows accessibility tool.
The user speaks English, Urdu, or a mix (Roman Urdu).
Your ONLY job: output a single JSON object — no prose, no markdown fences.

Schema:
{"action":"<ACTION>","params":{...},"message":"<1-line status in user's language>"}

─── ACTIONS & PARAMS ─────────────────────────────────────────────────────────
OPEN_APP      params: {"app":"<executable or common name>"}
              "device manager" → app:"devmgmt.msc"
              "task manager"   → app:"taskmgr"
              "control panel"  → app:"control"
              "settings"       → app:"ms-settings:"
              "paint"          → app:"mspaint"
              "run dialog"     → app:"run"
              Any other app    → app: its common exe name or descriptive name

CLOSE_APP     params: {"app":"<name or 'current'>"}

SCROLL        params: {"direction":"up|down|left|right","amount":<int lines, default 3>}

ZOOM          params: {"level":<int% or null>,"direction":"in|out|reset|null"}
              "zoom 150%"     → level:150, direction:null
              "zoom in"       → level:null, direction:"in"
              "reset zoom"    → level:100, direction:"reset"

VOLUME        params: {"direction":"up|down|mute|unmute","amount":<int% or null>}
              "volume 60%"    → direction:null, amount:60
              "mute"          → direction:"mute", amount:null

BRIGHTNESS    params: {"direction":"up|down|max|min|null","level":<int% or null>}
              "brightness full"  → direction:"max", level:100
              "brightness 40%"   → direction:null, level:40
              "brightness kam"   → direction:"down", level:null

MOUSE_CLICK   params: {"button":"left|right|middle","double":<bool>}
MOUSE_MOVE    params: {"direction":"up|down|left|right","amount":<px, default 100>}
MOUSE_SCROLL  params: {"direction":"up|down","amount":<int>}

TYPE_TEXT     params: {"text":"<text to type>"}
TYPE_MODE_ON  params: {}
TYPE_MODE_OFF params: {}

WINDOW_CONTROL params: {"command":"maximize|minimize|close|restore|switch|snap_left|snap_right"}
CLIPBOARD      params: {"command":"copy|paste|cut|select_all"}
MEDIA          params: {"command":"play_pause|next|previous|stop"}
SCREENSHOT     params: {"region":"full|window|selection", default "full"}
LOCK_SCREEN    params: {}
SLEEP          params: {}
RESTART        params: {}
SHUTDOWN       params: {}
KEY_PRESS      params: {"key":"<key combo e.g. ctrl+z, alt+tab, win+d>"}
RUN_COMMAND    params: {"command":"<shell command string>"}
SEARCH_WEB     params: {"query":"<search query>"}
NONE           params: {}   ← use when intent is completely unclear

─── URDU HINTS ───────────────────────────────────────────────────────────────
kholo/open → OPEN_APP
band karo  → CLOSE_APP or WINDOW_CONTROL close
upar       → up   |  neeche/niche → down
bada karo  → ZOOM in  |  chota → ZOOM out
awaaz      → VOLUME   |  roshni/brightness → BRIGHTNESS
likho      → TYPE_TEXT
screenshot lo / capture karo → SCREENSHOT
wapis ao   → KEY_PRESS alt+left
desktop    → KEY_PRESS win+d
─────────────────────────────────────────────────────────────────────────────
Output JSON only. No explanation."""

_USER_TMPL = 'Command: "{text}"\nJSON:'


# ──────────────────────────────────────────────────────────────────────────────
# LOCAL FALLBACK  —  only used when AI is offline/errors
# ──────────────────────────────────────────────────────────────────────────────

_LOCAL_RULES: list[tuple[list[str], str, dict]] = [
    # Scroll
    (["scroll up","upar jao","upar karo","oopar"],        "SCROLL",         {"direction":"up","amount":3}),
    (["scroll down","neeche jao","niche jao","neeche"],   "SCROLL",         {"direction":"down","amount":3}),
    # Zoom
    (["zoom in","bada karo","bada"],                       "ZOOM",           {"direction":"in","level":None}),
    (["zoom out","chota karo","chota"],                    "ZOOM",           {"direction":"out","level":None}),
    # Volume
    (["volume up","awaaz zyada","awaaz badhao"],           "VOLUME",         {"direction":"up","amount":None}),
    (["volume down","awaaz kam","mute karo"],              "VOLUME",         {"direction":"down","amount":None}),
    (["mute"],                                             "VOLUME",         {"direction":"mute","amount":None}),
    # Brightness
    (["brightness up","roshni zyada"],                     "BRIGHTNESS",     {"direction":"up","level":None}),
    (["brightness down","roshni kam"],                     "BRIGHTNESS",     {"direction":"down","level":None}),
    (["brightness full","full brightness"],                "BRIGHTNESS",     {"direction":"max","level":100}),
    # Window
    (["maximize","full screen"],                           "WINDOW_CONTROL", {"command":"maximize"}),
    (["minimize","chhupa do"],                             "WINDOW_CONTROL", {"command":"minimize"}),
    (["close window","window band"],                       "WINDOW_CONTROL", {"command":"close"}),
    # Common apps
    (["notepad"],                                          "OPEN_APP",       {"app":"notepad"}),
    (["chrome"],                                           "OPEN_APP",       {"app":"chrome"}),
    (["calculator"],                                       "OPEN_APP",       {"app":"calculator"}),
    (["task manager"],                                     "OPEN_APP",       {"app":"taskmgr"}),
    (["device manager"],                                   "OPEN_APP",       {"app":"devmgmt.msc"}),
    (["file explorer","explorer"],                         "OPEN_APP",       {"app":"explorer"}),
    # Media
    (["play","chalao"],                                    "MEDIA",          {"command":"play_pause"}),
    (["pause","roko"],                                     "MEDIA",          {"command":"play_pause"}),
    (["next song","agla"],                                 "MEDIA",          {"command":"next"}),
    # Clipboard
    (["copy","copy karo"],                                 "CLIPBOARD",      {"command":"copy"}),
    (["paste","paste karo"],                               "CLIPBOARD",      {"command":"paste"}),
    # Misc
    (["screenshot","screen capture"],                      "SCREENSHOT",     {"region":"full"}),
    (["lock screen","lock karo"],                          "LOCK_SCREEN",    {}),
    (["type mode on","typing shuru"],                      "TYPE_MODE_ON",   {}),
    (["stop typing","type mode off","typing band"],        "TYPE_MODE_OFF",  {}),
]


def _local_match(text: str) -> Optional[dict]:
    t = text.lower().strip()
    for keywords, action, params in _LOCAL_RULES:
        for kw in keywords:
            if kw in t:
                return _make(action, params, f"[Local] {action}", "local")
    return None


# ──────────────────────────────────────────────────────────────────────────────
# JSON EXTRACTION  —  4 strategies, handles any model quirk
# ──────────────────────────────────────────────────────────────────────────────

def _extract_json(text: str) -> Optional[dict]:
    # 1 — direct
    try:
        return json.loads(text)
    except Exception:
        pass
    # 2 — markdown fences
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except Exception:
            pass
    # 3 — first { … last }
    s, e = text.find("{"), text.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(text[s:e+1])
        except Exception:
            pass
    # 4 — fix single-quotes / Python literals
    fixed = text.replace("'",'"').replace("True","true").replace("False","false").replace("None","null")
    s, e = fixed.find("{"), fixed.rfind("}")
    if s != -1 and e > s:
        try:
            return json.loads(fixed[s:e+1])
        except Exception:
            pass
    return None


# ──────────────────────────────────────────────────────────────────────────────
# HELPER
# ──────────────────────────────────────────────────────────────────────────────

def _make(action="NONE", params=None, message="", source="") -> dict:
    return {"action": action, "params": params or {}, "message": message, "source": source}


# ──────────────────────────────────────────────────────────────────────────────
# AI CONTROLLER
# ──────────────────────────────────────────────────────────────────────────────

class DynamicAIController:
    """AI-first command parser. Local rules are emergency fallback only."""

    DEFAULT_API_KEY = ""  # Use GROQ_API_KEY environment variable    # 70b is used for its superior instruction-following (JSON reliability).
    # Groq serves it at ~300 tok/s so real-world latency is still ~1-2 s.
    MODEL = "llama-3.3-70b-versatile"

    def __init__(self, api_key: str = None):
        self.api_key = (api_key or os.environ.get("GROQ_API_KEY","") or self.DEFAULT_API_KEY).strip()
        self.client: Optional[Groq] = None
        self.initialized = False
        self.typing_mode = False
        self.last_error: Optional[str] = None

        if not GROQ_AVAILABLE:
            self.last_error = "groq not installed — run: pip install groq"
            print("[AI] ❌", self.last_error)
            return

        if not self.api_key or len(self.api_key) < 10:
            self.last_error = "No API key"
            return

        try:
            print(f"[AI] Connecting to Groq ({self.MODEL})…")
            self.client = Groq(api_key=self.api_key, timeout=12.0)
            # Lightweight test — just checks auth & connectivity
            test = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[{"role":"user","content":'Return {"action":"OK"}'}],
                max_tokens=10,
            )
            if test and test.choices:
                self.initialized = True
                print("[AI] ✅ Groq AI ready — truly dynamic mode")
            else:
                self.last_error = "Empty test response"
        except Exception as exc:
            self.last_error = str(exc)
            print(f"[AI] ❌ Init failed: {exc}")

    # ──────────────────────────────────────────────────────────────────────────
    def understand_command(self, text: str) -> dict:
        """
        Resolution order:
          1. Typing-mode passthrough  (instant)
          2. Groq AI                  (~1-3 s, truly dynamic)
          3. Local keyword fallback   (instant, only if AI offline)
        """
        text = text.strip()
        if not text:
            return _make("NONE")

        # ── 1. Typing-mode passthrough ────────────────────────────────────
        if self.typing_mode:
            stop = {"stop typing","type mode off","band karo","ruk jao","stop","typing band"}
            if text.lower() in stop:
                self.typing_mode = False
                return _make("TYPE_MODE_OFF", message="Typing mode OFF")
            return _make("TYPE_TEXT", {"text": text}, "Typing…")

        # ── 2. Groq AI (primary path) ─────────────────────────────────────
        if self.initialized:
            result = self._call_ai(text)
            if result:
                action = result["action"]
                if action == "TYPE_MODE_ON":
                    self.typing_mode = True
                elif action == "TYPE_MODE_OFF":
                    self.typing_mode = False
                print(f"[AI] ✅ AI → {action}  params={result['params']}")
                return result
            # AI returned garbage JSON — fall through to local
            print("[AI] ⚠️  AI parse failed, trying local fallback")

        # ── 3. Local keyword fallback ─────────────────────────────────────
        local = _local_match(text)
        if local:
            if local["action"] == "TYPE_MODE_ON":
                self.typing_mode = True
            print(f"[AI] 🔁 Local fallback → {local['action']}")
            return local

        print("[AI] ❓ Unknown command (no AI, no local match)")
        return _make("UNKNOWN", message=f"Could not understand: {text[:40]}")

    # ──────────────────────────────────────────────────────────────────────────
    def _call_ai(self, text: str) -> Optional[dict]:
        """Call Groq, extract JSON. Returns None on any failure."""
        try:
            resp = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system",  "content": _SYSTEM},
                    {"role": "user",    "content": _USER_TMPL.format(text=text)},
                ],
                max_tokens=120,
                temperature=0.0,   # deterministic — we want exact JSON, not creativity
                stop=["\n\n"],     # prevents model rambling after the JSON
            )
            raw = (resp.choices[0].message.content or "").strip()
            print(f"[AI] Raw: {raw!r}")
            parsed = _extract_json(raw)
            if parsed and "action" in parsed:
                return _make(
                    action=str(parsed["action"]).upper(),
                    params=parsed.get("params", {}),
                    message=parsed.get("message", ""),
                    source="ai",
                )
        except Exception as exc:
            print(f"[AI] ❌ API error: {exc}")
        return None

    def set_typing_mode(self, mode: bool):
        self.typing_mode = mode


# ──────────────────────────────────────────────────────────────────────────────
# VOICE RECOGNIZER
# ──────────────────────────────────────────────────────────────────────────────

class VoiceRecognizer:
    """Microphone → STT → DynamicAIController → callback."""

    def __init__(
        self,
        callback: Optional[Callable[[str, dict], None]] = None,
        groq_api_key: Optional[str] = None,
    ):
        self.callback = callback
        self._running = False
        self._stop_listening = None
        self._processing = False
        self._lock = threading.Lock()

        api_key = (groq_api_key or os.environ.get("GROQ_API_KEY", "")).strip()
        self.ai = DynamicAIController(api_key)

        if self.ai.initialized:
            print("[Voice] ✅ AI-first dynamic mode — any command works")
        else:
            print(f"[Voice] ⚠️  AI offline ({self.ai.last_error}) — local keywords only")

        self._recognizer: Optional[sr.Recognizer] = None
        self._microphone: Optional[sr.Microphone] = None
        self._mic_ok = False
        self._load_microphone()

    def _load_microphone(self):
        if not SR_AVAILABLE:
            print("[Voice] ❌ SpeechRecognition not installed — run: pip install SpeechRecognition")
            return

        for attempt in range(4):
            try:
                print(f"[Voice] Initialising mic… (attempt {attempt+1}/4)")
                mics = sr.Microphone.list_microphone_names()
                if not mics:
                    time.sleep(2)
                    continue

                self._recognizer = sr.Recognizer()
                self._recognizer.dynamic_energy_threshold = True
                self._recognizer.energy_threshold = 400
                self._recognizer.pause_threshold = 0.6

                self._microphone = sr.Microphone()
                with self._microphone as src:
                    self._recognizer.adjust_for_ambient_noise(src, duration=0.8)

                self._mic_ok = True
                print(f"[Voice] ✅ Mic ready: {mics[0]}")
                return

            except Exception as exc:
                print(f"[Voice] Attempt {attempt+1} failed: {exc}")
                time.sleep(2)

        print("[Voice] ❌ Microphone init failed after 4 attempts")

    def retry_mic(self):
        self._mic_ok = False
        self._load_microphone()

    def start(self):
        if self._running or not self._mic_ok:
            if not self._mic_ok:
                print("[Voice] Cannot start — mic not ready")
            return
        self._running = True
        try:
            with self._microphone as src:
                self._recognizer.adjust_for_ambient_noise(src, duration=0.5)
            self._stop_listening = self._recognizer.listen_in_background(
                self._microphone,
                self._background_callback,
                phrase_time_limit=6,   # longer window for complex commands
            )
            print("[Voice] 🎤 Listening…")
        except Exception as exc:
            self._running = False
            print(f"[Voice] ❌ Could not start: {exc}")

    def stop(self):
        self._running = False
        try:
            if callable(self._stop_listening):
                self._stop_listening(wait_for_stop=False)
        except Exception:
            pass

    def _background_callback(self, recognizer, audio):
        if not self._running:
            return
        with self._lock:
            if self._processing:
                return
            self._processing = True
        try:
            text = self._transcribe(audio)
            if text:
                print(f"[Voice] Heard: {text!r}")
                self._deliver(text)
        finally:
            self._processing = False

    def _transcribe(self, audio) -> str:
        try:
            # hi-IN picks up Roman Urdu better than en-US
            return self._recognizer.recognize_google(audio, language="hi-IN").strip()
        except Exception:
            try:
                # fallback to en-US
                return self._recognizer.recognize_google(audio, language="en-US").strip()
            except Exception:
                return ""

    def _deliver(self, text: str):
        if not text or not self.callback:
            return
        t0 = time.time()
        response = self.ai.understand_command(text)
        elapsed = time.time() - t0
        print(f"[Voice] {elapsed:.2f}s → {response['action']}  source={response.get('source','?')}")
        try:
            self.callback(text, response)
        except Exception as exc:
            print(f"[Voice] Callback error: {exc}")

    def __del__(self):
        self.stop()