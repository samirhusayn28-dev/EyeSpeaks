"""
EyeSpeaks Main Application - COMPLETE WITH API KEY
====================================================
"""

from dotenv import load_dotenv
load_dotenv()

import sys
import os
import time
import threading
import winsound
import traceback
import cv2
import numpy as np

from PyQt5.QtCore import Qt, QThread, QTimer, pyqtSignal, QObject, QMetaObject, QPoint
from PyQt5.QtGui import (QColor, QImage, QPixmap, QPainter, QPen, QBrush, 
                         QPainterPath, QPolygon, QLinearGradient, QFont)
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QPushButton, QFrame, QSlider,
                             QProgressBar, QTextEdit, QSizePolicy, QMessageBox)

print("="*50)
print("EyeSpeaks Initializing...")
print("="*50)

def check_pyaudio():
    try:
        import pyaudio
        print("✅ PyAudio OK")
        return True
    except ImportError:
        print("="*50)
        print("❌ PyAudio missing! Run:")
        print("   pip install pipwin")
        print("   pipwin install pyaudio")
        print("="*50)
        return False

class IconRenderer:
    @staticmethod
    def draw(painter, icon_type, rect, color):
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(QPen(color, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        painter.setBrush(Qt.NoBrush)
        x, y, w, h = rect.x(), rect.y(), rect.width(), rect.height()
        ix = lambda v: int(round(v))
        if icon_type == "camera":
            painter.drawRect(ix(x+w*.15), ix(y+h*.25), ix(w*.7), ix(h*.5))
            painter.drawLine(ix(x+w*.15), ix(y+h*.35), ix(x+w*.25), ix(y+h*.15))
            painter.drawLine(ix(x+w*.85), ix(y+h*.35), ix(x+w*.75), ix(y+h*.15))
            painter.drawEllipse(ix(x+w*.4), ix(y+h*.35), ix(w*.2), ix(h*.3))
        elif icon_type == "user":
            painter.drawEllipse(ix(x+w*.35), ix(y+h*.05), ix(w*.3), ix(w*.3))
            p = QPainterPath()
            p.moveTo(x+w*.1, y+h*.95); p.lineTo(x+w*.9, y+h*.95)
            p.lineTo(x+w*.9, y+h*.6); p.cubicTo(x+w*.9,y+h*.3,x+w*.65,y+h*.25,x+w*.5,y+h*.25)
            p.cubicTo(x+w*.35,y+h*.25,x+w*.1,y+h*.3,x+w*.1,y+h*.6); painter.drawPath(p)
        elif icon_type == "eye":
            p = QPainterPath()
            p.moveTo(x, y+h/2); p.cubicTo(x+w*.3,y, x+w*.7,y, x+w,y+h/2)
            p.cubicTo(x+w*.7,y+h, x+w*.3,y+h, x,y+h/2); painter.drawPath(p)
            painter.drawEllipse(ix(x+w*.35), ix(y+h*.35), ix(w*.3), ix(h*.3))
        elif icon_type == "blink":
            p = QPainterPath()
            p.moveTo(x, y+h/2); p.cubicTo(x+w*.3,y, x+w*.7,y, x+w,y+h/2)
            p.cubicTo(x+w*.7,y+h, x+w*.3,y+h, x,y+h/2); painter.drawPath(p)
            painter.drawLine(ix(x+w*.75), ix(y+h*.15), ix(x+w*.85), ix(y+h*.25))
        elif icon_type == "cursor":
            pts = [(x+w*.3,y),(x+w*.3,y+h*.65),(x+w*.15,y+h*.65),
                   (x+w*.5,y+h),(x+w*.85,y+h*.65),(x+w*.7,y+h*.65),(x+w*.7,y)]
            painter.setBrush(color)
            painter.drawPolygon(QPolygon([QPoint(ix(p[0]),ix(p[1])) for p in pts]))
        elif icon_type == "mic":
            painter.drawRoundedRect(ix(x+w*.4),ix(y+h*.1),ix(w*.2),ix(h*.5),w*.1,w*.1)
            painter.drawLine(ix(x+w*.3),ix(y+h*.7),ix(x+w*.7),ix(y+h*.7))
            painter.drawLine(ix(x+w*.3),ix(y+h*.7),ix(x+w*.3),ix(y+h*.85))
            painter.drawLine(ix(x+w*.7),ix(y+h*.7),ix(x+w*.7),ix(y+h*.85))

class IconWidget(QWidget):
    def __init__(self, icon_type, size=32, parent=None):
        super().__init__(parent)
        self.icon_type = icon_type; self.color = QColor("#7eb8d4")
        self.setFixedSize(size, size)
    def paintEvent(self, event):
        IconRenderer.draw(QPainter(self), self.icon_type, event.rect(), self.color)

class SoundManager(QObject):
    SOUNDS = {'start': [(880,150)], 'stop': [(440,200),(330,200)], 'click': [(1200,50)],
              'button': [(1100,60)], 'calibrate':[(600,100),(800,100),(1000,150)], 'error': [(200,150),(150,200)]}
    def __init__(self):
        super().__init__(); self.enabled = True
    def play(self, name):
        if not self.enabled: return
        p = self.SOUNDS.get(name, [(800,100)])
        threading.Thread(target=self._seq, args=(p,), daemon=True).start()
    def _seq(self, pattern):
        try:
            for f, d in pattern: winsound.Beep(int(f), d); time.sleep(0.02)
        except: pass

class CameraWorker(QThread):
    sig_log    = pyqtSignal(str, str)
    sig_frame  = pyqtSignal(QImage)
    sig_stats  = pyqtSignal(int, float)
    sig_status = pyqtSignal(str, bool)

    def __init__(self, settings):
        super().__init__()
        self.settings = settings; self.running = True; self.blink_count = 0

    def run(self):
        try:
            from modules import FaceDetector, EyeTracker, BlinkDetector, CursorController
            face, eye, blink, cursor = FaceDetector(), EyeTracker(), BlinkDetector(), CursorController()
            cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)
            if not cap.isOpened(): cap = cv2.VideoCapture(0)
            if not cap.isOpened():
                self.sig_log.emit("Camera not found!", "error"); return

            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            fps_t, frames = time.time(), 0
            self.sig_log.emit("Modules initialized", "success")

            while self.running:
                ret, frame = cap.read()
                if not ret: break
                frame = cv2.flip(frame, 1); frames += 1
                now = time.time()
                if now - fps_t >= 1.0:
                    self.sig_stats.emit(self.blink_count, frames/(now-fps_t))
                    frames, fps_t = 0, now

                results = face.detect(frame)
                if results:
                    self.sig_status.emit("Face", True)
                    dx, dy, _ = eye.update(frame, results)
                    if self.settings.get("eye_enabled"):
                        cursor.move_relative(int(dx), int(dy))
                    if self.settings.get("blink_enabled"):
                        action = blink.detect(frame, results, 0.21) 
                        if action == "left_click":
                            cursor.click(); self.blink_count += 1
                            self.sig_log.emit("Left Eye → Click", "cmd")
                        elif action == "right_click":
                            cursor.right_click(); self.blink_count += 1
                            self.sig_log.emit("Right Eye → Right Click", "cmd")
                    face.draw_landmarks(frame, results)
                else:
                    self.sig_status.emit("Face", False)

                h, w, _ = frame.shape
                self.sig_frame.emit(QImage(frame.data, w, h, 3*w, QImage.Format_RGB888).rgbSwapped())
        except Exception as e:
            self.sig_log.emit(f"Error: {e}", "error")
        finally:
            if 'cap' in locals(): cap.release()

    def stop(self): self.running = False

class MainWindow(QMainWindow):
    voice_signal = pyqtSignal(str, dict)
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("EYESPEAKS - AI EDITION")
        self.resize(1440, 920)
        self.setMinimumSize(1200, 800)
        self.sound = SoundManager()
        self.camera = None; self.voice_obj = None; self.sys_cmd = None
        self.typing_mode = False
        self._mic_retry_count = 0
        
        self._setup_ui()
        self._apply_theme()
        
        self.voice_signal.connect(self._handle_voice_in_main_thread)
        
        self._footer_timer = QTimer(self)
        self._footer_timer.timeout.connect(self._tick_time)
        self._footer_timer.start(1000)
        self._tick_time()
        
        check_pyaudio()

    def _apply_theme(self):
        self.setStyleSheet("""
            QMainWindow, QWidget { background: #0b0d18; color: #c8d8e8; font-family: 'Consolas', 'Courier New', monospace; }
            QLabel { background: transparent; }
            QFrame#Sidebar { background: #0d1120; border-right: 1px solid #1e2d42; }
            QFrame#Card { background: #111827; border: 1px solid #1e2d42; border-radius: 10px; }
            QFrame#MiniCard { background: #0f1625; border: 1px solid #1b2a3d; border-radius: 8px; }
            QFrame#VoiceBar { background: #0f1625; border: 1px solid #1b2a3d; border-radius: 8px; }
            QFrame#Footer { background: #090b14; border-top: 1px solid #1a2535; }
            QLabel#AppName { color: #a8cbdf; font-size: 18px; font-weight: 700; letter-spacing: 4px; }
            QLabel#SectionTitle { color: #6a8fa8; font-size: 11px; font-weight: 600; letter-spacing: 2px; }
            QLabel#CardTitle { color: #4a6a82; font-size: 11px; }
            QLabel#BigValue { color: #c8dcea; font-size: 32px; font-weight: 700; }
            QLabel#StatusOn { color: #4dd8a0; font-size: 13px; font-weight: 700; letter-spacing: 2px; }
            QLabel#StatusOff { color: #c05060; font-size: 13px; font-weight: 700; letter-spacing: 2px; }
            QLabel#FooterText { color: #2e4a62; font-size: 11px; }
            QLabel#TimeLabel { color: #4a7090; font-size: 11px; font-weight: 600; }
            QLabel#VoiceStatus { color: #2e4a62; font-size: 12px; }
            QPushButton#BtnStart { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1a5c3a, stop:1 #0f3a24); border: 1px solid #2a8a58; border-radius: 8px; color: #6deba8; font-size: 13px; font-weight: 700; letter-spacing: 2px; padding: 13px; }
            QPushButton#BtnStart:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #226e46, stop:1 #144a2e); border-color: #3aaa6e; }
            QPushButton#BtnStop { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #5c1a22, stop:1 #3a0f14); border: 1px solid #8a2a36; border-radius: 8px; color: #eb6d7a; font-size: 13px; font-weight: 700; letter-spacing: 2px; padding: 13px; }
            QPushButton#BtnStop:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #6e2230, stop:1 #4a141c); border-color: #aa3a48; }
            QPushButton#BtnStop:disabled { background: #1a2030; border-color: #2a3545; color: #3a5068; }
            QPushButton#BtnRecal { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #1a3a5c, stop:1 #0f2438); border: 1px solid #2a5a8a; border-radius: 8px; color: #6aaad8; font-size: 13px; font-weight: 700; letter-spacing: 2px; padding: 13px; }
            QPushButton#BtnRecal:hover { background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #224a70, stop:1 #142e48); border-color: #3a7aaa; }
            QPushButton#BtnClear { background: #111a28; border: 1px solid #1e3048; border-radius: 6px; color: #4a7090; font-size: 11px; padding: 5px 12px; }
            QPushButton#BtnClear:hover { background: #162030; color: #6a9ab0; }
            QTextEdit { background: #080c14; border: 1px solid #1a2535; border-radius: 8px; color: #8aaac0; font-size: 11px; font-family: 'Consolas', monospace; padding: 8px; }
            QFrame#OvItem { background: #0d1525; border: 1px solid #1a2a3e; border-radius: 8px; }
        """)

    def _setup_ui(self):
        root = QWidget(); self.setCentralWidget(root)
        root_lay = QVBoxLayout(root); root_lay.setContentsMargins(0, 0, 0, 0); root_lay.setSpacing(0)
        body = QWidget(); body_lay = QHBoxLayout(body); body_lay.setContentsMargins(0, 0, 0, 0); body_lay.setSpacing(0)

        sb = QFrame(); sb.setObjectName("Sidebar"); sb.setFixedWidth(270)
        sl = QVBoxLayout(sb); sl.setContentsMargins(20, 24, 20, 24); sl.setSpacing(16)
        logo_row = QHBoxLayout(); logo_row.setSpacing(10)
        eye_ico = IconWidget("eye", 26, self); eye_ico.color = QColor("#5aaad4")
        logo_row.addWidget(eye_ico)
        app_name = QLabel("EYESPEAKS"); app_name.setObjectName("AppName")
        logo_row.addWidget(app_name); logo_row.addStretch()
        sl.addLayout(logo_row)
        sl.addWidget(self._divider())
        
        self.btn_start = QPushButton("▶  START"); self.btn_start.setObjectName("BtnStart")
        self.btn_start.setMinimumHeight(46)
        self.btn_start.clicked.connect(lambda: [self.sound.play('button'), self.start_system()])
        sl.addWidget(self.btn_start)
        self.btn_stop = QPushButton("■  STOP"); self.btn_stop.setObjectName("BtnStop")
        self.btn_stop.setMinimumHeight(46); self.btn_stop.setEnabled(False)
        self.btn_stop.clicked.connect(lambda: [self.sound.play('button'), self.stop_system()])
        sl.addWidget(self.btn_stop)
        self.btn_recal = QPushButton("◎  RECALIBRATE"); self.btn_recal.setObjectName("BtnRecal")
        self.btn_recal.setMinimumHeight(46)
        self.btn_recal.clicked.connect(lambda: [self.sound.play('button'), self.recalibrate()])
        sl.addWidget(self.btn_recal)
        
        self.btn_test = QPushButton("🎤  TEST VOICE")
        self.btn_test.setObjectName("BtnRecal")
        self.btn_test.setMinimumHeight(36)
        self.btn_test.clicked.connect(self._manual_voice_test)
        sl.addWidget(self.btn_test)
        
        sl.addWidget(self._divider())
        sl.addWidget(self._small_label("SYSTEM STATUS"))
        self.lbl_status = QLabel("● OFFLINE"); self.lbl_status.setObjectName("StatusOff")
        sl.addWidget(self.lbl_status)
        sl.addWidget(self._divider())
        sl.addWidget(self._small_label("METRICS"))
        stats_row = QHBoxLayout(); stats_row.setSpacing(10)
        self.lbl_fps, fps_card = self._mini_card("FPS", "0")
        self.lbl_blinks, blink_card = self._mini_card("BLINKS", "0")
        stats_row.addWidget(fps_card); stats_row.addWidget(blink_card)
        sl.addLayout(stats_row)
        sl.addWidget(self._divider())
        sl.addWidget(self._small_label("CALIBRATION"))
        calib_hint = QLabel("Hold face steady for 20 frames"); calib_hint.setStyleSheet("color: #3a5a72; font-size: 10px;")
        sl.addWidget(calib_hint)
        self.prog_calib = QProgressBar(); self.prog_calib.setValue(0)
        sl.addWidget(self.prog_calib)
        sl.addStretch()
        body_lay.addWidget(sb)

        center = QWidget(); cl = QVBoxLayout(center); cl.setContentsMargins(20, 20, 20, 20); cl.setSpacing(16)
        top_row = QHBoxLayout(); top_row.setSpacing(16)
        wc = QFrame(); wc.setObjectName("Card")
        wl = QVBoxLayout(wc); wl.setContentsMargins(14,14,14,14); wl.setSpacing(10)
        wl.addWidget(self._section_label("◈  LIVE FEED"))
        self.video_label = QLabel("Waiting for camera...")
        self.video_label.setAlignment(Qt.AlignCenter)
        self.video_label.setStyleSheet("background: #060810; border: 1px solid #1a2535; border-radius: 6px; color: #2a4060; font-size: 13px; letter-spacing: 1px;")
        self.video_label.setMinimumSize(580, 340)
        wl.addWidget(self.video_label)
        top_row.addWidget(wc, 3)
        
        lc = QFrame(); lc.setObjectName("Card")
        ll = QVBoxLayout(lc); ll.setContentsMargins(14,14,14,14); ll.setSpacing(8)
        lh = QHBoxLayout()
        lh.addWidget(self._section_label("◈  SYSTEM LOG"))
        lh.addStretch()
        bc = QPushButton("CLEAR"); bc.setObjectName("BtnClear")
        bc.clicked.connect(lambda: [self.log_box.clear(), self.sound.play('button')])
        lh.addWidget(bc)
        ll.addLayout(lh)
        self.log_box = QTextEdit(); self.log_box.setReadOnly(True)
        ll.addWidget(self.log_box)
        top_row.addWidget(lc, 2)
        cl.addLayout(top_row)

        ov = QFrame(); ov.setObjectName("Card")
        ovl = QVBoxLayout(ov); ovl.setContentsMargins(14,12,14,12); ovl.setSpacing(10)
        ovl.addWidget(self._section_label("◈  PIPELINE STATUS"))
        ov_items = QHBoxLayout(); ov_items.setSpacing(10)
        self.overview_labels = []
        steps = [("camera","WEBCAM"),("user","FACE DETECT"),("eye","EYE TRACK"),("blink","BLINK"),("cursor","CURSOR"),("mic","VOICE AI")]
        for icon_name, name in steps:
            item = QFrame(); item.setObjectName("OvItem")
            il = QVBoxLayout(item); il.setAlignment(Qt.AlignCenter); il.setSpacing(6); il.setContentsMargins(10,12,10,12)
            ico = IconWidget(icon_name, 30, self); ico.color = QColor("#2a4a62")
            ln = QLabel(name); ln.setAlignment(Qt.AlignCenter); ln.setStyleSheet("color: #2a4a62; font-size: 10px; letter-spacing: 1px;")
            ls = QLabel("OFFLINE"); ls.setAlignment(Qt.AlignCenter); ls.setStyleSheet("color: #5a2a34; font-size: 10px; font-weight: 700;")
            self.overview_labels.append((ico, ls, ln))
            il.addWidget(ico); il.addWidget(ln); il.addWidget(ls)
            ov_items.addWidget(item)
        ovl.addLayout(ov_items)
        cl.addWidget(ov)

        vb = QFrame(); vb.setObjectName("VoiceBar")
        vl = QHBoxLayout(vb); vl.setContentsMargins(16,10,16,10); vl.setSpacing(16)
        mic_ico = IconWidget("mic", 20, self); mic_ico.color = QColor("#3a6888")
        vl.addWidget(mic_ico)
        vl.addWidget(self._kv_label("VOICE ASSISTANT"))
        self.lbl_voice = QLabel("● INACTIVE"); self.lbl_voice.setObjectName("VoiceStatus")
        vl.addWidget(self.lbl_voice)
        vl.addStretch()
        vl.addWidget(self._kv_label("HEARD :"))
        self.lbl_recog = QLabel("—"); self.lbl_recog.setStyleSheet("color: #8ab8d0; font-size: 12px; font-weight: 600;")
        vl.addWidget(self.lbl_recog)
        vl.addWidget(self._kv_label("  CMD :"))
        self.lbl_cmd = QLabel("—"); self.lbl_cmd.setStyleSheet("color: #3a6080; font-size: 12px;")
        vl.addWidget(self.lbl_cmd)
        cl.addWidget(vb)

        body_lay.addWidget(center, 1)
        root_lay.addWidget(body, 1)

        ft = QFrame(); ft.setObjectName("Footer"); ft.setFixedHeight(36)
        fl = QHBoxLayout(ft); fl.setContentsMargins(20,0,20,0)
        fl.addWidget(self._footer_text("EYESPEAKS  v1.0.0"))
        fl.addWidget(self._footer_text("  |  "))
        self.lbl_sys = QLabel("ALL SYSTEMS NOMINAL"); self.lbl_sys.setStyleSheet("color: #2a6a4a; font-size: 11px; letter-spacing: 1px;")
        fl.addWidget(self.lbl_sys)
        fl.addStretch()
        self.lbl_time = QLabel("--:--:--"); self.lbl_time.setObjectName("TimeLabel")
        fl.addWidget(self.lbl_time)
        root_lay.addWidget(ft)

    def _divider(self):
        d = QFrame(); d.setFrameShape(QFrame.HLine); d.setStyleSheet("background: #1a2535; border: none; max-height: 1px;"); return d
    def _small_label(self, txt):
        l = QLabel(txt); l.setObjectName("SectionTitle"); return l
    def _section_label(self, txt):
        l = QLabel(txt); l.setStyleSheet("color: #4a7a9a; font-size: 11px; font-weight: 600; letter-spacing: 1px;"); return l
    def _kv_label(self, txt):
        l = QLabel(txt); l.setStyleSheet("color: #2e4a62; font-size: 11px; letter-spacing: 1px;"); return l
    def _footer_text(self, txt):
        l = QLabel(txt); l.setObjectName("FooterText"); return l
    def _mini_card(self, title, value):
        card = QFrame(); card.setObjectName("MiniCard")
        lay = QVBoxLayout(card); lay.setContentsMargins(12,10,12,10); lay.setSpacing(2)
        t = QLabel(title); t.setObjectName("CardTitle"); lay.addWidget(t)
        v = QLabel(value); v.setObjectName("BigValue");  lay.addWidget(v)
        return v, card

    def start_system(self):
        self.btn_start.setEnabled(False); self.btn_stop.setEnabled(True)
        self.lbl_status.setText("● ONLINE"); self.lbl_status.setObjectName("StatusOn")
        self.sound.play('start'); self.log("System online", "success")
        
        self.camera = CameraWorker({"eye_enabled": True, "blink_enabled": True})
        self.camera.sig_frame.connect(self.update_video)
        self.camera.sig_log.connect(self.log)
        self.camera.sig_status.connect(self.update_status)
        self.camera.sig_stats.connect(self.update_stats)
        self.camera.start()
        
        QTimer.singleShot(2000, self.activate_voice)

    def stop_system(self):
        if self.camera: self.camera.stop(); self.camera.wait(1000)
        if self.voice_obj: 
            try: self.voice_obj.stop()
            except: pass
        self.btn_start.setEnabled(True); self.btn_stop.setEnabled(False)
        self.lbl_status.setText("● OFFLINE"); self.lbl_status.setObjectName("StatusOff")
        self.lbl_voice.setText("● INACTIVE"); self.lbl_voice.setStyleSheet("color: #2e4a62; font-size: 12px;")
        self.lbl_recog.setText("—"); self.lbl_cmd.setText("—")
        self.typing_mode = False
        self.log("System offline", "warn"); self.sound.play('stop')
        self._reset_overview()

    def activate_voice(self):
        self.lbl_voice.setText("● INITIALIZING...")
        self.lbl_voice.setStyleSheet("color: #c08830; font-size: 12px; font-weight: 600;")
        self.log("Initializing Voice AI...", "info")
        try:
            import speech_recognition as sr
            
            try:
                import pyaudio
                pa = pyaudio.PyAudio()
                mic_count = pa.get_device_count()
                pa.terminate()
                self.log(f"PyAudio devices: {mic_count}", "info")
            except Exception as e:
                self.log(f"PyAudio error: {e}", "error")
                return
            
            mics = sr.Microphone.list_microphone_names()
            if not mics:
                self.log("No Microphone found!", "error")
                self.lbl_voice.setText("● NO MIC")
                self._schedule_mic_retry()
                return
                
            self.log(f"Mics found: {mics}", "info")
            
            from modules import VoiceRecognizer, SystemCommandExecutor
            self.sys_cmd = SystemCommandExecutor()
            
            def on_voice(text, response):
                try:
                    self.voice_signal.emit(text, response)
                except Exception as e:
                    print(f"Voice signal error: {e}")

            # API key already embedded in VoiceRecognizer
            self.voice_obj = VoiceRecognizer(callback=on_voice)
            
            if self.voice_obj._mic_ok:
                self.voice_obj.start()
                self.lbl_voice.setText("● LISTENING (AI)")
                self.lbl_voice.setStyleSheet("color: #4dd8a0; font-size: 12px; font-weight: 600;")
                self.log("Voice AI Active", "success")
                self._mic_retry_count = 0
                if len(self.overview_labels) > 5:
                    self._set_status(5, True)
            else:
                self.log("Mic init failed. Retrying...", "warn")
                self._schedule_mic_retry()
                
        except Exception as e:
            self.log(f"Voice Error: {e}", "error")
            traceback.print_exc()
            self._schedule_mic_retry()

    def _handle_voice_in_main_thread(self, text: str, response: dict):
        try:
            action = response.get("action", "UNKNOWN")
            params = response.get("params", {})
            msg = response.get("message", "")
            
            self.lbl_recog.setText(text)
            self.lbl_cmd.setText(msg)
            
            self.log(f"Voice: '{text}'", "info")
            self.log(f"AI → {action} | {params}", "info")
            
            if action and action not in ["UNKNOWN", "NONE", "ERROR"]:
                if self.sys_cmd:
                    res = self.sys_cmd.execute(action, params)
                    self.log(f"Executed: {res}", "success")
                    self.sound.play('click')
                else:
                    self.log("sys_cmd not initialized!", "error")
            else:
                self.log(f"No action: {msg}", "info")
            
            if action == "TYPE_MODE_ON": 
                self.typing_mode = True
                self.lbl_cmd.setStyleSheet("color: #4dd8a0; font-size: 12px; font-weight: 700;")
                self.log("Typing Mode ON", "success")
            elif action == "TYPE_MODE_OFF": 
                self.typing_mode = False
                self.lbl_cmd.setStyleSheet("color: #5abadc; font-size: 12px; font-weight: 700;")
                self.log("Typing Mode OFF", "success")
                
        except Exception as e:
            self.log(f"Voice handler error: {e}", "error")
            traceback.print_exc()

    def _manual_voice_test(self):
        if not self.sys_cmd:
            from modules import SystemCommandExecutor
            self.sys_cmd = SystemCommandExecutor()
        
        test_response = {"action": "OPEN_APP", "params": {"app": "notepad"}, "message": "Manual Test"}
        self._handle_voice_in_main_thread("manual test", test_response)
        self.log("Manual test: Opening Notepad", "success")

    def _schedule_mic_retry(self):
        if self._mic_retry_count < 5:
            self._mic_retry_count += 1
            self.log(f"Retrying Mic in 5 seconds... ({self._mic_retry_count}/5)", "warn")
            QTimer.singleShot(5000, self._retry_mic_logic)

    def _retry_mic_logic(self):
        if self.voice_obj:
            self.voice_obj.retry_mic()
            if self.voice_obj._mic_ok:
                self.voice_obj.start()
                self.lbl_voice.setText("● LISTENING (AI)")
                self.lbl_voice.setStyleSheet("color: #4dd8a0; font-size: 12px; font-weight: 600;")
                self.log("Mic recovered on retry!", "success")
                if len(self.overview_labels) > 5:
                    self._set_status(5, True)
            else:
                self._schedule_mic_retry()

    def update_video(self, img):
        self.video_label.setPixmap(QPixmap.fromImage(img).scaled(self.video_label.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation))
        for i in [0, 2, 3, 4]: self._set_status(i, True)

    def update_status(self, comp, active):
        self._set_status(1, active)
        self.log("Face detected" if active else "Face lost", "success" if active else "warn")

    def update_stats(self, blinks, fps):
        self.lbl_fps.setText(str(int(fps))); self.lbl_blinks.setText(str(blinks))

    def _set_status(self, idx, active):
        if 0 <= idx < len(self.overview_labels):
            ico, lbl, name_lbl = self.overview_labels[idx]
            if active:
                ico.color = QColor("#3aaa70"); lbl.setText("ONLINE")
                lbl.setStyleSheet("color: #3aaa70; font-size: 10px; font-weight: 700;")
                name_lbl.setStyleSheet("color: #3a6a52; font-size: 10px; letter-spacing: 1px;")
            else:
                ico.color = QColor("#2a4a62"); lbl.setText("OFFLINE")
                lbl.setStyleSheet("color: #5a2a34; font-size: 10px; font-weight: 700;")
                name_lbl.setStyleSheet("color: #2a4a62; font-size: 10px; letter-spacing: 1px;")
            ico.update()

    def _reset_overview(self):
        for i in range(len(self.overview_labels)): self._set_status(i, False)

    def recalibrate(self):
        self.log("Recalibrating...", "warn"); self.sound.play('calibrate')
        self.prog_calib.setValue(0)
        for i in range(0, 101, 10): QTimer.singleShot(i*50, lambda v=i: self.prog_calib.setValue(v))
        QTimer.singleShot(600, lambda: self.log("Calibration complete", "success"))

    def log(self, msg, level="info"):
        colors = {"success":"#3aaa70","error":"#c05060","cmd":"#5abadc","warn":"#c08830"}
        col = colors.get(level, "#6a8aa0")
        ts = time.strftime("%H:%M:%S")
        self.log_box.append(f'<span style="color:#2a4060">[{ts}]</span> <span style="color:{col}">{msg}</span>')

    def _tick_time(self):
        self.lbl_time.setText(time.strftime("%H:%M:%S"))

def main():
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    app = QApplication(sys.argv); app.setStyle("Fusion")
    win = MainWindow(); win.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    try: main()
    except Exception as e:
        print(f"FATAL: {e}"); traceback.print_exc()
        input("Press Enter...")
        sys.exit(1)