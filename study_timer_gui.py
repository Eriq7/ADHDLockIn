# --- START OF FILE study_timer_gui.py ---
# Modern UI overhaul: animated ring interface for ADHDLockIn
import time
import os
import sys
import json
import webbrowser
import pygame
import requests
from datetime import datetime
from api_client import APIClient

try:
    from bandit import _get_time_of_day, _get_session_depth
    BANDIT_AVAILABLE = True
except ImportError:
    BANDIT_AVAILABLE = False

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSystemTrayIcon, QMessageBox, QSizeGrip, QPushButton, QMenu,
    QLineEdit, QStackedWidget
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QSettings, QRectF
from PyQt6.QtGui import QIcon, QAction, QPainter, QPen, QColor

# Sounds actually used (skip validation of long break sounds from old config)
NEEDED_SOUNDS = {"start_study", "start_short_break"}

# --- Resource path helper (read-only bundled files: icon, sounds) ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- User data path helper (writable files: config, session) ---
def user_data_path(filename):
    home = os.path.expanduser("~")
    app_dir = os.path.join(home, ".adhdlockin")
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, filename)

# --- Default configuration ---
DEFAULT_CONFIG = {
    "study_time_min": 3 * 60,
    "study_time_max": 5 * 60,
    "short_break_duration": 10,
    "music_folder": "study_music",
    "sound_files": {
        "start_study": "start_study.mp3",
        "start_short_break": "start_short_break.mp3"
    },
    "total_study_time": 0
}

# --- Config load/create ---
def load_or_create_config():
    config_path = user_data_path('config.json')
    if not os.path.exists(config_path):
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(DEFAULT_CONFIG, f, indent=4, ensure_ascii=False)
            return DEFAULT_CONFIG
        except Exception as e:
            print(f"Failed to create default config: {e}")
            return DEFAULT_CONFIG

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            user_config = json.load(f)
            updated = False
            for key, value in DEFAULT_CONFIG.items():
                if key not in user_config:
                    user_config[key] = value
                    updated = True
            if updated:
                save_config(user_config)
            return user_config
    except (json.JSONDecodeError, TypeError):
        return DEFAULT_CONFIG

# --- Config save ---
def save_config(config_data):
    config_path = user_data_path('config.json')
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to save config: {e}")

# --- Common styles ---
INPUT_STYLE = """
    QLineEdit {
        background-color: #16213e; color: #ffffff;
        border: 1px solid #0f3460; border-radius: 10px;
        padding: 0 15px; font-size: 14px; min-height: 42px;
    }
    QLineEdit:focus { border: 1px solid #4ecca3; }
"""

SECONDARY_BTN_STYLE = (
    "QPushButton { background: transparent; color: #a0a0b0; border: none; "
    "font-size: 14px; padding: 5px 10px; }"
    "QPushButton:hover { color: #e94560; }"
)

# ==============================================================================
# Core Logic Layer
# ==============================================================================
class StudyTimerLogic(QObject):
    state_changed = pyqtSignal(str, str)
    time_updated = pyqtSignal(int)
    notification_requested = pyqtSignal(str, str)

    def __init__(self, config, username="local_user"):
        super().__init__()
        self.config = config
        self.username = username
        self.api_client = APIClient(user_id=username)

        self.is_paused = False
        self.time_remaining_on_pause = 0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.on_timer_timeout)

        pygame.mixer.init()
        self.sound_paths = self._validate_and_get_sound_paths()

        self.total_study_time = self.config.get("total_study_time", 0)
        self.current_session_start_time = None
        self.current_session_duration = 0
        self.current_selected_interval = None

        self.reset_cycle()

    @staticmethod
    def _get_time_of_day_simple():
        hour = datetime.now().hour
        if 5 <= hour < 12:
            return "morning"
        elif 12 <= hour < 17:
            return "afternoon"
        elif 17 <= hour < 21:
            return "evening"
        else:
            return "night"

    @staticmethod
    def _get_session_depth_simple(cycle_count):
        if cycle_count <= 2:
            return "early"
        elif cycle_count <= 5:
            return "mid"
        else:
            return "deep"

    def _log_incomplete_session(self):
        if not self.current_session_start_time:
            return
        try:
            end_time = datetime.now()
            actual_duration = int((end_time - self.current_session_start_time).total_seconds())
            if actual_duration > 0:
                time_of_day = _get_time_of_day() if BANDIT_AVAILABLE else self._get_time_of_day_simple()
                session_depth = _get_session_depth(self.cycle_count) if BANDIT_AVAILABLE else self._get_session_depth_simple(self.cycle_count)
                context_key = f"{time_of_day}_{session_depth}"

                api_success = self.api_client.post_session(
                    start_time=self.current_session_start_time,
                    end_time=end_time,
                    duration=actual_duration,
                    completed=False,
                    interval_selected=self.current_selected_interval,
                    context_key=context_key,
                    time_of_day=time_of_day,
                    session_depth=session_depth,
                    round_number=self.cycle_count
                )

                if not api_success:
                    print("API unavailable, incomplete session data not recorded")
        except Exception as e:
            print(f"Warning: Failed to log incomplete session: {e}")

    def _clear_current_session(self):
        self.current_session_start_time = None
        self.current_session_duration = 0

    def reset_cycle(self):
        if getattr(self, "current_state", None) == "studying" and getattr(self, "current_selected_interval", None):
            self._log_incomplete_session()
        self.timer.stop()
        self.cycle_count = 0
        self.current_state = "stopped"
        self.is_paused = False
        self.current_selected_interval = None
        self._clear_current_session()
        self.state_changed.emit("Ready", self.current_state)
        self.time_updated.emit(self.total_study_time)

    def on_timer_timeout(self):
        if self.current_state == "studying":
            if self.current_session_start_time and self.current_session_duration > 0:
                end_time = datetime.now()
                time_of_day = _get_time_of_day() if BANDIT_AVAILABLE else self._get_time_of_day_simple()
                session_depth = _get_session_depth(self.cycle_count) if BANDIT_AVAILABLE else self._get_session_depth_simple(self.cycle_count)
                context_key = f"{time_of_day}_{session_depth}"

                api_success = self.api_client.post_session(
                    start_time=self.current_session_start_time,
                    end_time=end_time,
                    duration=self.current_session_duration,
                    completed=True,
                    interval_selected=self.current_selected_interval,
                    context_key=context_key,
                    time_of_day=time_of_day,
                    session_depth=session_depth,
                    round_number=self.cycle_count
                )

                if not api_success:
                    print("API unavailable, session data not recorded")
            self._clear_current_session()

            study_duration = self.timer.property("duration")
            self.total_study_time += study_duration
            self._run_short_break_cycle()

        elif self.current_state == "short_breaking":
            self._run_study_cycle()

    def _run_study_cycle(self):
        self.cycle_count += 1
        self.current_state = "studying"

        time_of_day = _get_time_of_day() if BANDIT_AVAILABLE else self._get_time_of_day_simple()
        session_depth = _get_session_depth(self.cycle_count) if BANDIT_AVAILABLE else self._get_session_depth_simple(self.cycle_count)

        study_duration = self.api_client.get_recommendation(time_of_day, session_depth)

        if study_duration is None:
            print("API unavailable, using default interval (240s)")
            study_duration = 240

        self.current_selected_interval = study_duration
        self.current_session_start_time = datetime.now()
        self.current_session_duration = study_duration

        self.state_changed.emit(f"Round {self.cycle_count}", self.current_state)
        self._play_sound("start_study")
        self.timer.setProperty("duration", study_duration)
        self.timer.start(study_duration * 1000)

    def load_persistent_time(self, total_study_time):
        self.total_study_time = total_study_time
        self.time_updated.emit(self.total_study_time)

    def _validate_and_get_sound_paths(self):
        folder_path = resource_path(self.config["music_folder"])
        if not os.path.isdir(folder_path):
            raise FileNotFoundError(f"Resource folder not found: {folder_path}")
        paths = {}
        for key, filename in self.config["sound_files"].items():
            if key not in NEEDED_SOUNDS:
                continue
            path = os.path.join(folder_path, filename)
            if not os.path.isfile(path):
                raise FileNotFoundError(f"Audio file not found: {path}")
            paths[key] = path
        return paths

    def _play_sound(self, sound_key):
        sound_path = self.sound_paths.get(sound_key)
        if not sound_path:
            return
        try:
            pygame.mixer.music.load(sound_path)
            pygame.mixer.music.play()
        except pygame.error as e:
            print(f"Audio Error: {e}")

    def start_or_resume(self):
        if self.is_paused:
            self._resume()
        elif self.current_state == "stopped":
            self.is_paused = False
            self._run_study_cycle()

    def _run_short_break_cycle(self):
        self.current_state = "short_breaking"
        break_duration = self.config["short_break_duration"]
        self.state_changed.emit("Break", self.current_state)
        self.time_updated.emit(self.total_study_time)
        self._play_sound("start_short_break")
        self.timer.setProperty("duration", 0)
        self.timer.start(break_duration * 1000)

    def pause(self):
        if self.timer.isActive():
            self.time_remaining_on_pause = self.timer.remainingTime()
            self.timer.stop()
            self.is_paused = True
            self.state_changed.emit("Paused", self.current_state)

    def _resume(self):
        if self.is_paused:
            self.timer.start(self.time_remaining_on_pause)
            self.is_paused = False
            self._play_sound("start_study")
            original_state_text = {
                "studying": f"Round {self.cycle_count}",
                "short_breaking": "Break"
            }.get(self.current_state, "Ready")
            self.state_changed.emit(original_state_text, self.current_state)

    def stop(self):
        self.timer.stop()
        pygame.mixer.quit()

# ==============================================================================
# Animated Ring Widget
# ==============================================================================
class AnimatedRing(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.angle = 0
        self.is_animating = False
        self.ring_color = "#0f3460"
        self.glow_color = "#0f3460"
        self.status_text = "Ready"
        self.text_color = "#ffffff"

        self.anim_timer = QTimer(self)
        self.anim_timer.setInterval(50)
        self.anim_timer.timeout.connect(self._tick)

    def _tick(self):
        self.angle = (self.angle + 6) % 360
        self.update()

    def start_animation(self):
        self.is_animating = True
        self.anim_timer.start()

    def stop_animation(self):
        self.is_animating = False
        self.anim_timer.stop()
        self.update()

    def set_state(self, state, round_number=0):
        if state == "studying":
            self.ring_color = "#0f3460"
            self.glow_color = "#4ecca3"
            self.status_text = f"Round {round_number}"
            self.text_color = "#4ecca3"
            self.start_animation()
        elif state == "short_breaking":
            self.ring_color = "#0f3460"
            self.glow_color = "#ffc107"
            self.status_text = "Break"
            self.text_color = "#ffc107"
            self.start_animation()
        elif state == "paused":
            self.status_text = "Paused"
            self.text_color = "#a0a0b0"
            self.stop_animation()
        else:  # stopped
            self.ring_color = "#0f3460"
            self.glow_color = "#0f3460"
            self.status_text = "Ready"
            self.text_color = "#ffffff"
            self.stop_animation()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        size = min(self.width(), self.height())
        ring_diameter = size * 0.75
        ring_rect = QRectF(
            (self.width() - ring_diameter) / 2,
            (self.height() - ring_diameter) / 2,
            ring_diameter,
            ring_diameter
        )
        line_width = 6

        # Background ring
        pen = QPen(QColor(self.ring_color), line_width)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.drawEllipse(ring_rect)

        # Glow arc (when animating)
        if self.is_animating:
            glow_pen = QPen(QColor(self.glow_color), line_width + 2)
            glow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            painter.setPen(glow_pen)
            painter.drawArc(
                ring_rect.toRect(),
                int((90 - self.angle) * 16),
                int(-60 * 16)
            )

        # Center text
        font = painter.font()
        font.setPointSize(28)
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(QColor(self.text_color))
        painter.drawText(ring_rect.toRect(), Qt.AlignmentFlag.AlignCenter, self.status_text)

        painter.end()

# ==============================================================================
# Action Button Widget
# ==============================================================================
class ActionButton(QPushButton):
    def set_state(self, state):
        if state == "stopped":
            self.setText("\u25b6  Start")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4ecca3; color: #ffffff;
                    border: none; border-radius: 25px;
                    font-size: 18px; font-weight: bold;
                    padding: 12px 40px;
                }
                QPushButton:hover { background-color: #3dbb92; }
            """)
        elif state in ("studying", "short_breaking"):
            self.setText("\u23f8  Pause")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #ffc107; color: #1a1a2e;
                    border: none; border-radius: 25px;
                    font-size: 18px; font-weight: bold;
                    padding: 12px 40px;
                }
                QPushButton:hover { background-color: #e6ac00; }
            """)
        elif state == "paused":
            self.setText("\u25b6  Resume")
            self.setStyleSheet("""
                QPushButton {
                    background-color: #4ecca3; color: #ffffff;
                    border: none; border-radius: 25px;
                    font-size: 18px; font-weight: bold;
                    padding: 12px 40px;
                }
                QPushButton:hover { background-color: #3dbb92; }
            """)

# ==============================================================================
# Auth Window — Login / Register
# ==============================================================================
class AuthWindow(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config
        self.dragPos = None
        self._login_success = False
        self._registered_username = None

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(400, 500)

        # Center on screen
        screen = QApplication.primaryScreen()
        if screen:
            geo = screen.availableGeometry()
            self.move((geo.width() - 400) // 2, (geo.height() - 500) // 2)

        # --- Background ---
        self.background_widget = QWidget(self)
        self.background_widget.setObjectName("auth_bg")
        self.background_widget.setStyleSheet(
            "#auth_bg { background-color: rgba(26, 26, 46, 242); border-radius: 20px; }"
        )

        bg_layout = QVBoxLayout(self.background_widget)
        bg_layout.setContentsMargins(40, 25, 40, 25)
        bg_layout.setSpacing(0)

        # Close button (top right)
        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("\u2715")
        close_btn.setFixedSize(30, 30)
        close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        close_btn.setStyleSheet(
            "QPushButton { background: transparent; color: #a0a0b0; border: none; font-size: 16px; }"
            "QPushButton:hover { color: #e94560; }"
        )
        close_btn.clicked.connect(self.close)
        close_row.addWidget(close_btn)
        bg_layout.addLayout(close_row)

        # Title
        title = QLabel("ADHDLockIn")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 22px; font-weight: bold; color: #ffffff; background: transparent;")
        bg_layout.addWidget(title)

        subtitle = QLabel("Focus Timer")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 14px; color: #a0a0b0; background: transparent; padding-bottom: 20px;")
        bg_layout.addWidget(subtitle)

        # --- Tab buttons ---
        tab_layout = QHBoxLayout()
        tab_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tab_layout.setSpacing(8)

        self.login_tab_btn = QPushButton("Login")
        self.login_tab_btn.setFixedSize(120, 36)
        self.login_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.login_tab_btn.clicked.connect(lambda: self.switch_tab(0))

        self.register_tab_btn = QPushButton("Register")
        self.register_tab_btn.setFixedSize(120, 36)
        self.register_tab_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.register_tab_btn.clicked.connect(lambda: self.switch_tab(1))

        tab_layout.addWidget(self.login_tab_btn)
        tab_layout.addWidget(self.register_tab_btn)
        bg_layout.addLayout(tab_layout)
        bg_layout.addSpacing(20)

        # --- Stacked content ---
        self.stack = QStackedWidget()
        self.stack.setStyleSheet("background: transparent;")

        # Page 0: Login
        login_page = QWidget()
        login_page.setStyleSheet("background: transparent;")
        login_layout = QVBoxLayout(login_page)
        login_layout.setContentsMargins(0, 0, 0, 0)
        login_layout.setSpacing(0)

        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("Enter your username")
        self.username_input.setStyleSheet(INPUT_STYLE)
        login_layout.addWidget(self.username_input)
        login_layout.addSpacing(12)

        self.secret_key_input = QLineEdit()
        self.secret_key_input.setPlaceholderText("Enter your secret key")
        self.secret_key_input.setStyleSheet(INPUT_STYLE)
        login_layout.addWidget(self.secret_key_input)
        login_layout.addSpacing(20)

        login_btn = QPushButton("Login")
        login_btn.setFixedHeight(45)
        login_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        login_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3; color: #ffffff; font-weight: bold;
                border: none; border-radius: 22px; font-size: 16px;
            }
            QPushButton:hover { background-color: #3dbb92; }
        """)
        login_btn.clicked.connect(self.on_login_clicked)
        login_layout.addWidget(login_btn)
        login_layout.addSpacing(10)

        self.login_error = QLabel("")
        self.login_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.login_error.setWordWrap(True)
        self.login_error.setStyleSheet("color: #e94560; font-size: 12px; background: transparent;")
        self.login_error.hide()
        login_layout.addWidget(self.login_error)

        login_layout.addStretch()
        self.stack.addWidget(login_page)

        # Page 1: Register
        register_page = QWidget()
        register_page.setStyleSheet("background: transparent;")
        reg_layout = QVBoxLayout(register_page)
        reg_layout.setContentsMargins(0, 0, 0, 0)
        reg_layout.setSpacing(0)

        self.username_input_reg = QLineEdit()
        self.username_input_reg.setPlaceholderText("Choose a username")
        self.username_input_reg.setStyleSheet(INPUT_STYLE)
        reg_layout.addWidget(self.username_input_reg)
        reg_layout.addSpacing(4)

        hint = QLabel("3-50 characters. Letters, numbers, and underscores only.")
        hint.setStyleSheet("color: #a0a0b0; font-size: 11px; background: transparent;")
        reg_layout.addWidget(hint)
        reg_layout.addSpacing(20)

        reg_btn = QPushButton("Register")
        reg_btn.setFixedHeight(45)
        reg_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        reg_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3; color: #ffffff; font-weight: bold;
                border: none; border-radius: 22px; font-size: 16px;
            }
            QPushButton:hover { background-color: #3dbb92; }
        """)
        reg_btn.clicked.connect(self.on_register_clicked)
        reg_layout.addWidget(reg_btn)
        reg_layout.addSpacing(10)

        self.reg_error = QLabel("")
        self.reg_error.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.reg_error.setWordWrap(True)
        self.reg_error.setStyleSheet("color: #e94560; font-size: 12px; background: transparent;")
        self.reg_error.hide()
        reg_layout.addWidget(self.reg_error)

        reg_layout.addStretch()
        self.stack.addWidget(register_page)

        # Page 2: Registration Success
        success_page = QWidget()
        success_page.setStyleSheet("background: transparent;")
        success_layout = QVBoxLayout(success_page)
        success_layout.setContentsMargins(0, 0, 0, 0)
        success_layout.setSpacing(0)
        success_layout.addSpacing(30)

        success_title = QLabel("Registration Successful!")
        success_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        success_title.setStyleSheet("color: #4ecca3; font-size: 20px; font-weight: bold; background: transparent;")
        success_layout.addWidget(success_title)
        success_layout.addSpacing(20)

        uname_label = QLabel("Username")
        uname_label.setStyleSheet("color: #a0a0b0; font-size: 12px; background: transparent;")
        success_layout.addWidget(uname_label)

        self.success_username = QLabel("")
        self.success_username.setStyleSheet("color: #ffffff; font-size: 18px; font-weight: bold; background: transparent;")
        success_layout.addWidget(self.success_username)
        success_layout.addSpacing(20)

        skey_label = QLabel("Secret Key")
        skey_label.setStyleSheet("color: #a0a0b0; font-size: 12px; background: transparent;")
        success_layout.addWidget(skey_label)

        self.success_secret_key = QLabel("")
        self.success_secret_key.setStyleSheet(
            "color: #ffffff; font-size: 28px; font-weight: bold; "
            "font-family: 'Courier New', monospace; letter-spacing: 6px; background: transparent;"
        )
        success_layout.addWidget(self.success_secret_key)
        success_layout.addSpacing(20)

        warning = QLabel(
            "\u26a0\ufe0f Please save your username and secret key. "
            "You will need them to log in. This is the only time they will be shown."
        )
        warning.setAlignment(Qt.AlignmentFlag.AlignCenter)
        warning.setWordWrap(True)
        warning.setStyleSheet("color: #ffc107; font-size: 12px; background: transparent;")
        success_layout.addWidget(warning)
        success_layout.addSpacing(20)

        self.copy_btn = QPushButton("Copy to Clipboard")
        self.copy_btn.setFixedHeight(42)
        self.copy_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.copy_btn.setStyleSheet("""
            QPushButton {
                background-color: #0f3460; color: #ffffff;
                border: none; border-radius: 10px; font-size: 14px;
            }
            QPushButton:hover { background-color: #1a4a80; }
        """)
        self.copy_btn.clicked.connect(self.on_copy_credentials)
        success_layout.addWidget(self.copy_btn)
        success_layout.addSpacing(12)

        self.continue_btn = QPushButton("I've saved my credentials \u2014 Continue")
        self.continue_btn.setFixedHeight(45)
        self.continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_btn.setEnabled(False)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #a0a0b0; color: #ffffff; font-weight: bold;
                border: none; border-radius: 22px; font-size: 14px;
            }
        """)
        self.continue_btn.clicked.connect(self.on_continue_clicked)
        success_layout.addWidget(self.continue_btn)

        success_layout.addStretch()
        self.stack.addWidget(success_page)

        bg_layout.addWidget(self.stack, stretch=1)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.background_widget)

        # Default to Login tab
        self.switch_tab(0)

    # --- Tab switching ---
    def switch_tab(self, index):
        self.stack.setCurrentIndex(index)
        if index == 0:
            self.login_tab_btn.setStyleSheet(
                "QPushButton { background-color: #e94560; color: #ffffff; border: none; "
                "border-radius: 18px; font-size: 14px; font-weight: bold; }"
            )
            self.register_tab_btn.setStyleSheet(
                "QPushButton { background-color: #16213e; color: #a0a0b0; border: none; "
                "border-radius: 18px; font-size: 14px; }"
                "QPushButton:hover { color: #ffffff; }"
            )
        else:
            self.register_tab_btn.setStyleSheet(
                "QPushButton { background-color: #e94560; color: #ffffff; border: none; "
                "border-radius: 18px; font-size: 14px; font-weight: bold; }"
            )
            self.login_tab_btn.setStyleSheet(
                "QPushButton { background-color: #16213e; color: #a0a0b0; border: none; "
                "border-radius: 18px; font-size: 14px; }"
                "QPushButton:hover { color: #ffffff; }"
            )
        # Clear errors when switching tabs
        self.login_error.hide()
        self.reg_error.hide()

    # --- Login ---
    def on_login_clicked(self):
        username = self.username_input.text().strip()
        secret_key = self.secret_key_input.text().strip()
        if not username or not secret_key:
            self.show_error("Please fill in both fields.")
            return
        try:
            response = requests.post(
                'https://1ltnq33e02.execute-api.us-east-1.amazonaws.com/api/users/login',
                json={'username': username, 'secretKey': secret_key},
                timeout=5
            )
            data = response.json()
            if data.get('success'):
                self.on_auth_success(username)
            else:
                error_msg = data.get('error', 'Login failed.')
                self.show_error(error_msg)
        except requests.exceptions.ConnectionError:
            self.show_error("Cannot connect to server.\nMake sure the API server is running.")
        except Exception as e:
            self.show_error(f"Error: {str(e)}")

    def show_error(self, msg):
        self.login_error.setText(msg)
        self.login_error.show()

    # --- Register ---
    def on_register_clicked(self):
        username = self.username_input_reg.text().strip()
        if not username:
            self.show_error_reg("Please enter a username.")
            return
        try:
            response = requests.post(
                'https://1ltnq33e02.execute-api.us-east-1.amazonaws.com/api/users/register',
                json={'username': username},
                timeout=5
            )
            data = response.json()
            if data.get('success'):
                secret_key = data['data']['secretKey']
                self.show_registration_success(username, secret_key)
            else:
                error_msg = data.get('error', 'Registration failed.')
                self.show_error_reg(error_msg)
        except requests.exceptions.ConnectionError:
            self.show_error_reg("Cannot connect to server.\nMake sure the API server is running.")
        except Exception as e:
            self.show_error_reg(f"Error: {str(e)}")

    def show_error_reg(self, msg):
        self.reg_error.setText(msg)
        self.reg_error.show()

    def show_registration_success(self, username, secret_key):
        self._registered_username = username
        self._registered_secret_key = secret_key
        self.success_username.setText(username)
        self.success_secret_key.setText(secret_key)
        # Hide tab buttons
        self.login_tab_btn.hide()
        self.register_tab_btn.hide()
        # Show success page
        self.stack.setCurrentIndex(2)

    # --- Copy credentials ---
    def on_copy_credentials(self):
        text = (
            f"ADHDLockIn Credentials\n"
            f"Username: {self._registered_username}\n"
            f"Secret Key: {self._registered_secret_key}"
        )
        QApplication.clipboard().setText(text)
        self.copy_btn.setText("\u2713 Copied!")
        # Enable continue button
        self.continue_btn.setEnabled(True)
        self.continue_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.continue_btn.setStyleSheet("""
            QPushButton {
                background-color: #4ecca3; color: #ffffff; font-weight: bold;
                border: none; border-radius: 22px; font-size: 14px;
            }
            QPushButton:hover { background-color: #3dbb92; }
        """)
        # Reset copy button text after 2 seconds
        QTimer.singleShot(2000, lambda: self.copy_btn.setText("Copy to Clipboard"))

    # --- Continue after registration ---
    def on_continue_clicked(self):
        self.on_auth_success(self._registered_username)

    # --- Auth success ---
    def on_auth_success(self, username):
        self._login_success = True
        # Save session
        session_path = user_data_path('user_session.json')
        with open(session_path, 'w') as f:
            json.dump({"username": username}, f)
        # Hide auth window
        self.hide()
        # Create and show main window
        self.main_window = StudyTimerGUI(self.config, username=username)
        if not self.main_window._init_failed:
            self.main_window.show()

    # --- Dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragPos:
            self.move(event.globalPosition().toPoint() - self.dragPos)

    def mouseReleaseEvent(self, event):
        self.dragPos = None

    # --- Close ---
    def closeEvent(self, event):
        event.accept()
        if not self._login_success:
            QApplication.quit()

# ==============================================================================
# GUI Layer — Modern animated ring interface
# ==============================================================================
class StudyTimerGUI(QWidget):
    def __init__(self, config, username="local_user"):
        super().__init__()
        self.config = config
        self.username = username

        try:
            self.logic = StudyTimerLogic(self.config, username=self.username)
        except FileNotFoundError as e:
            QMessageBox.critical(
                None,
                "Resource Error",
                f"{e}\n\nPlease ensure all assets are in the correct location, then restart the app."
            )
            self._init_failed = True
            return
        self._init_failed = False

        self.dragPos = None
        self.settings = QSettings("ADHDLockIn", "App")

        # Window flags: frameless, tool, no always-on-top
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # --- Build UI ---
        self.background_widget = QWidget(self)
        self.background_widget.setObjectName("background")

        bg_layout = QVBoxLayout(self.background_widget)
        bg_layout.setContentsMargins(20, 20, 20, 10)
        bg_layout.setSpacing(0)

        # Area 1: Title (15%)
        self.title_label = QLabel("ADHDLockIn")
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #ffffff; "
            "background: transparent; padding: 10px 0;"
        )
        bg_layout.addWidget(self.title_label)

        # Area 2: Animated Ring (50%)
        self.ring = AnimatedRing()
        self.ring.setMinimumHeight(200)
        bg_layout.addWidget(self.ring, stretch=5)

        # Area 3: Buttons (35%)
        button_container = QWidget()
        button_container.setStyleSheet("background: transparent;")
        button_layout = QVBoxLayout(button_container)
        button_layout.setContentsMargins(0, 10, 0, 0)
        button_layout.setSpacing(12)
        button_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Main action button
        self.action_button = ActionButton()
        self.action_button.setFixedSize(160, 50)
        self.action_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.action_button.set_state("stopped")
        self.action_button.clicked.connect(self.on_action_button_clicked)

        btn_center = QHBoxLayout()
        btn_center.setAlignment(Qt.AlignmentFlag.AlignCenter)
        btn_center.addWidget(self.action_button)
        button_layout.addLayout(btn_center)

        # Secondary buttons (Quit / Dashboard / Logout)
        secondary_layout = QHBoxLayout()
        secondary_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        secondary_layout.setSpacing(20)

        self.quit_button = QPushButton("Quit")
        self.quit_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.quit_button.setStyleSheet(SECONDARY_BTN_STYLE)
        self.quit_button.clicked.connect(self.close)

        self.dashboard_button = QPushButton("\U0001f4ca Dashboard")
        self.dashboard_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.dashboard_button.setStyleSheet(SECONDARY_BTN_STYLE)
        self.dashboard_button.clicked.connect(self.open_dashboard)

        self.logout_button = QPushButton("Logout")
        self.logout_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.logout_button.setStyleSheet(SECONDARY_BTN_STYLE)
        self.logout_button.clicked.connect(self.on_logout)

        secondary_layout.addWidget(self.quit_button)
        secondary_layout.addWidget(self.dashboard_button)
        secondary_layout.addWidget(self.logout_button)
        button_layout.addLayout(secondary_layout)

        # Guidance text (replaces Total focus)
        guidance_label = QLabel(
            "If you feel distracted, tap Quit \u2014 "
            "we'll recommend a better session time next time."
        )
        guidance_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        guidance_label.setWordWrap(True)
        guidance_label.setStyleSheet(
            "font-size: 11px; color: #a0a0b0; background: transparent; padding-top: 10px;"
        )
        button_layout.addWidget(guidance_label)

        bg_layout.addWidget(button_container, stretch=3)

        # SizeGrip
        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch()
        self.size_grip = QSizeGrip(self.background_widget)
        self.size_grip.setStyleSheet("background: transparent; width: 15px; height: 15px;")
        grip_layout.addWidget(self.size_grip)
        bg_layout.addLayout(grip_layout)

        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.background_widget)

        # Apply stylesheet
        self.background_widget.setStyleSheet(
            self.background_widget.styleSheet() +
            "#background { background-color: rgba(26, 26, 46, 242); border-radius: 20px; }"
        )

        # Tray icon
        self.create_tray_icon()

        # Load settings and connect signals
        self.load_settings()

        self.logic.state_changed.connect(self.on_state_changed)
        self.logic.notification_requested.connect(self.show_notification)

        self.logic.reset_cycle()

    # --- Action handling ---
    def on_action_button_clicked(self):
        if self.logic.is_paused:
            self.logic.start_or_resume()
        elif self.logic.current_state == "stopped":
            self.logic.start_or_resume()
        elif self.logic.current_state in ("studying", "short_breaking"):
            self.logic.pause()

    def on_state_changed(self, status_text, state_name):
        if self.logic.is_paused:
            self.ring.set_state("paused")
            self.action_button.set_state("paused")
        else:
            self.ring.set_state(state_name, self.logic.cycle_count)
            self.action_button.set_state(state_name)

    def open_dashboard(self):
        webbrowser.open("http://adhdlockin-dashboard.s3-website-us-east-1.amazonaws.com")

    def on_logout(self):
        # Delete session file
        session_path = user_data_path("user_session.json")
        try:
            if os.path.exists(session_path):
                os.remove(session_path)
        except Exception as e:
            print(f"Warning: Could not delete session file: {e}")

        # Clean up current session
        if self.logic.current_state == "studying" and self.logic.current_selected_interval:
            self.logic._log_incomplete_session()
        self.logic._clear_current_session()
        self.save_settings()
        self.config['total_study_time'] = self.logic.total_study_time
        save_config(self.config)
        self.logic.stop()
        self.tray.hide()

        # Hide main window, show auth
        self.hide()
        self.auth_window = AuthWindow(self.config)
        self.auth_window.show()

    # --- Notifications ---
    def show_notification(self, title, message):
        self.tray.showMessage(title, message, self.tray_icon, 5000)

    # --- Tray icon (simplified) ---
    def create_tray_icon(self):
        self.tray_icon = QIcon(resource_path('icon.ico'))
        self.tray = QSystemTrayIcon(self.tray_icon, self)
        self.tray.setToolTip("ADHDLockIn")

        tray_menu = QMenu()
        tray_menu.setStyleSheet("""
            QMenu { background-color: #16213e; border: 1px solid #0f3460; }
            QMenu::item { padding: 8px 20px; color: #ffffff; }
            QMenu::item:selected { background-color: #0f3460; }
        """)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(self.close)
        tray_menu.addAction(quit_action)

        self.tray.setContextMenu(tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            if self.isVisible():
                self.hide()
            else:
                self.show()
                self.raise_()

    # --- Window dragging ---
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            if self.size_grip.geometry().contains(event.pos()):
                return
            self.dragPos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and self.dragPos:
            self.move(event.globalPosition().toPoint() - self.dragPos)

    def mouseReleaseEvent(self, event):
        self.dragPos = None

    # --- Settings ---
    def save_settings(self):
        if self._init_failed:
            return
        self.settings.setValue("ui/geometry", self.saveGeometry())

    def load_settings(self):
        geometry = self.settings.value("ui/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(400, 500)
            # Center on screen
            screen = QApplication.primaryScreen()
            if screen:
                screen_geo = screen.availableGeometry()
                x = (screen_geo.width() - 400) // 2
                y = (screen_geo.height() - 500) // 2
                self.move(x, y)

    # --- Close ---
    def closeEvent(self, event):
        if self.logic.current_state == "studying" and self.logic.current_selected_interval:
            self.logic._log_incomplete_session()
        self.logic._clear_current_session()
        self.save_settings()
        if not self._init_failed:
            self.config['total_study_time'] = self.logic.total_study_time
            save_config(self.config)
            self.logic.stop()
            self.tray.hide()
        event.accept()
        QApplication.quit()

# ==============================================================================
# Main entry point
# ==============================================================================
if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    if not os.path.exists(resource_path('icon.ico')):
        QMessageBox.critical(None, "Resource Error", "Critical file 'icon.ico' not found!")
        sys.exit(1)

    config = load_or_create_config()

    # Check for auto-login
    session_path = user_data_path('user_session.json')
    saved_username = None
    if os.path.exists(session_path):
        try:
            with open(session_path, 'r') as f:
                session_data = json.load(f)
                saved_username = session_data.get('username')
        except (json.JSONDecodeError, KeyError):
            pass

    if saved_username:
        window = StudyTimerGUI(config, username=saved_username)
        if window._init_failed:
            sys.exit(1)
        window.show()
    else:
        auth_window = AuthWindow(config)
        auth_window.show()

    sys.exit(app.exec())
