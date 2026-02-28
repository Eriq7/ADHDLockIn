# --- START OF FILE study_timer_gui.py ---
import time
import os
import sys
import json
import pygame
from datetime import datetime
from bandit import select_interval, update_reward, _get_context_key, _get_time_of_day, _get_session_depth

try:
    from db import init_db, log_session_to_db, close_db
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    print("Warning: psycopg2 not installed, DB features disabled. Run with .venv/bin/python3")

try:
    from cache import init_cache, close_cache
    CACHE_AVAILABLE = True
except ImportError:
    CACHE_AVAILABLE = False

# --- PyQt6 Imports ---
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QMenu,
    QSystemTrayIcon, QMessageBox, QSizeGrip
)
from PyQt6.QtCore import Qt, QTimer, QObject, pyqtSignal, QSettings
from PyQt6.QtGui import QIcon, QAction

# --- Resource path helper ---
def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

# --- Default configuration ---
DEFAULT_CONFIG = {
    "study_time_min": 3 * 60,
    "study_time_max": 5 * 60,
    "short_break_duration": 10,
    "long_break_threshold": 90 * 60,
    "long_break_duration": 20 * 60,
    "music_folder": "study_music",
    "sound_files": {
        "start_study": "start_study.mp3",
        "start_short_break": "start_short_break.mp3",
        "start_long_break": "start_long_break.mp3",
        "end_long_break": "end_long_break.mp3"
    },
    "total_study_time": 0
}

# --- Config load/create ---
def load_or_create_config():
    config_path = resource_path('config.json')
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
    config_path = resource_path('config.json')
    try:
        with open(config_path, 'w', encoding='utf-8') as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Error: Failed to save config: {e}")

# ==============================================================================
# Core Logic Layer (DO NOT CHANGE: original logic)
# ==============================================================================
class StudyTimerLogic(QObject):
    state_changed = pyqtSignal(str, str)
    time_updated = pyqtSignal(int)
    notification_requested = pyqtSignal(str, str)

    def __init__(self, config):
        super().__init__()
        self.config = config

        if DB_AVAILABLE:
            try:
                init_db()
            except Exception as e:
                print(f"Warning: DB init failed: {e}")

        if CACHE_AVAILABLE:
            try:
                init_cache()
            except Exception as e:
                print(f"Warning: Redis cache init failed: {e}")

        self.is_paused = False
        self.time_remaining_on_pause = 0
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.on_timer_timeout)

        pygame.mixer.init()
        self.sound_paths = self._validate_and_get_sound_paths()

        self.total_study_time = self.config.get("total_study_time", 0)
        self.current_cycle_study_time = 0
        self.current_session_start_time = None
        self.current_session_duration = 0
        self.current_selected_interval = None

        self.reset_cycle()

    def _log_incomplete_session(self):
        if not self.current_session_start_time or not DB_AVAILABLE:
            return
        try:
            end_time = datetime.now()
            actual_duration = int((end_time - self.current_session_start_time).total_seconds())
            if actual_duration > 0:
                log_session_to_db(
                    start_time=self.current_session_start_time,
                    end_time=end_time,
                    duration_seconds=actual_duration,
                    completed=False,
                    interval_selected=self.current_selected_interval,
                    context_key=_get_context_key(self.cycle_count),
                    time_of_day=_get_time_of_day(),
                    session_depth=_get_session_depth(self.cycle_count),
                    round_number=self.cycle_count
                )
        except Exception as e:
            print(f"Warning: Failed to log incomplete session: {e}")

    def _clear_current_session(self):
        self.current_session_start_time = None
        self.current_session_duration = 0

    def reset_cycle(self):
        if getattr(self, "current_state", None) == "studying" and getattr(self, "current_selected_interval", None):
            update_reward(self.cycle_count, self.current_selected_interval, completed=False)
            self._log_incomplete_session()
        self.timer.stop()
        self.cycle_count = 0
        self.current_state = "stopped"
        self.is_paused = False
        self.current_selected_interval = None
        self._clear_current_session()
        self.current_cycle_study_time = 0
        # MODIFIED BRANDING TEXT
        self.state_changed.emit("EZLockIn\nRight-click to Start", self.current_state)
        self.time_updated.emit(self.total_study_time)

    def reset_all(self):
        self.total_study_time = 0
        self.reset_cycle()
        self.time_updated.emit(self.total_study_time)

    def on_timer_timeout(self):
        if self.current_state == "studying":
            if self.current_session_start_time and self.current_session_duration > 0:
                end_time = datetime.now()
                if DB_AVAILABLE:
                    try:
                        log_session_to_db(
                            start_time=self.current_session_start_time,
                            end_time=end_time,
                            duration_seconds=self.current_session_duration,
                            completed=True,
                            interval_selected=self.current_selected_interval,
                            context_key=_get_context_key(self.cycle_count),
                            time_of_day=_get_time_of_day(),
                            session_depth=_get_session_depth(self.cycle_count),
                            round_number=self.cycle_count
                        )
                    except Exception as e:
                        print(f"Warning: Failed to log session to DB: {e}")
            if self.current_selected_interval:
                update_reward(self.cycle_count, self.current_selected_interval, completed=True)
            self._clear_current_session()

            study_duration = self.timer.property("duration")
            self.total_study_time += study_duration
            self.current_cycle_study_time += study_duration
            self._run_short_break_cycle()

        elif self.current_state == "short_breaking":
            if self.current_cycle_study_time >= self.config["long_break_threshold"]:
                self._run_long_break_cycle()
            else:
                self._run_study_cycle()

        elif self.current_state == "long_breaking":
            self._play_sound("end_long_break")
            self.current_state = "long_break_finished"
            self.state_changed.emit("🎉 Long Break Ended\nRight-click to start a new cycle", self.current_state)
            self.notification_requested.emit("Break Finished", "Ready to start the next session?")

    def _run_study_cycle(self):
        self.cycle_count += 1
        self.current_state = "studying"
        study_duration = select_interval(self.cycle_count)
        self.current_selected_interval = study_duration

        self.current_session_start_time = datetime.now()
        self.current_session_duration = study_duration

        self.state_changed.emit(f"📚 Studying...\n(Round {self.cycle_count})", self.current_state)
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
        elif self.current_state in ["stopped", "long_break_finished"]:
            self.is_paused = False
            if self.current_state == "long_break_finished":
                self.reset_cycle()
            if self.current_cycle_study_time >= self.config["long_break_threshold"]:
                self._run_long_break_cycle()
            else:
                self._run_study_cycle()

    def _run_short_break_cycle(self):
        self.current_state = "short_breaking"
        break_duration = self.config["short_break_duration"]
        self.state_changed.emit("☕ Short Break...", self.current_state)
        self.time_updated.emit(self.total_study_time)
        self._play_sound("start_short_break")
        self.timer.setProperty("duration", 0)
        self.timer.start(break_duration * 1000)

    def _run_long_break_cycle(self):
        self.current_state = "long_breaking"
        break_duration = self.config["long_break_duration"]
        self.state_changed.emit("🧘 Long Break...", self.current_state)
        self.time_updated.emit(self.total_study_time)
        self._play_sound("start_long_break")
        self.current_cycle_study_time = 0
        self.timer.setProperty("duration", 0)
        self.timer.start(break_duration * 1000)

    def pause(self):
        if self.timer.isActive():
            self.time_remaining_on_pause = self.timer.remainingTime()
            self.timer.stop()
            self.is_paused = True
            self.state_changed.emit("⏸️ Paused", self.current_state)

    def _resume(self):
        if self.is_paused:
            self.timer.start(self.time_remaining_on_pause)
            self.is_paused = False
            self._play_sound("start_study")
            original_state_text = {
                "studying": f"📚 Studying...\n(Round {self.cycle_count})",
                "short_breaking": "☕ Short Break...",
                "long_breaking": "🧘 Long Break..."
            }.get(self.current_state, "Unknown")
            self.state_changed.emit(original_state_text, self.current_state)

    def stop(self):
        self.timer.stop()
        pygame.mixer.quit()

# ==============================================================================
# GUI Layer (English-only UI)
# ==============================================================================
class StudyTimerGUI(QWidget):
    def __init__(self, config):
        super().__init__()
        self.config = config

        try:
            self.logic = StudyTimerLogic(self.config)
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
        self.settings = QSettings("MyStudyTimer", "App")
        self.is_always_on_top = self.settings.value("ui/alwaysOnTop", True, type=bool)

        self.create_tray_icon()

        self.countdown_timer = QTimer(self)
        self.countdown_timer.setInterval(1000)
        self.countdown_timer.timeout.connect(self.update_countdown_display)

        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            (Qt.WindowType.WindowStaysOnTopHint if self.is_always_on_top else Qt.WindowType.Widget)
        )

        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        self.background_widget = QWidget(self)
        self.background_widget.setObjectName("background")

        bg_layout = QVBoxLayout(self.background_widget)
        bg_layout.setContentsMargins(10, 10, 10, 0)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_label.setWordWrap(True)

        self.total_time_label = QLabel()
        self.total_time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.total_time_label.setObjectName("total_time_label")

        bg_layout.addWidget(self.status_label)
        bg_layout.addWidget(self.total_time_label)
        bg_layout.addStretch()

        grip_layout = QHBoxLayout()
        grip_layout.setContentsMargins(0, 0, 0, 0)
        grip_layout.addStretch()
        self.size_grip = QSizeGrip(self.background_widget)
        grip_layout.addWidget(self.size_grip)
        bg_layout.addLayout(grip_layout)

        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(self.background_widget)

        self.load_settings()
        self.update_stylesheet()

        self.logic.state_changed.connect(self.update_status)
        self.logic.time_updated.connect(self.update_total_time)
        self.logic.notification_requested.connect(self.show_notification)

        self.logic.reset_cycle()

    def show_notification(self, title, message):
        self.tray.showMessage(title, message, self.tray_icon, 5000)

    def confirm_and_reset_all(self):
        reply = QMessageBox.question(
            self,
            'Confirm Reset',
            "Clear all accumulated focus time?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            self.logic.reset_all()

    def populate_context_menu(self, menu: QMenu):
        menu.clear()
        menu.setStyleSheet("""
            QMenu { background-color: #3B4252; border: 1px solid #4C566A; }
            QMenu::item { padding: 8px 20px; color: #ECEFF4; }
            QMenu::item:selected { background-color: #5E81AC; }
            QMenu::item:disabled { color: #4C566A; }
            QMenu::separator { height: 1px; background: #4C566A; margin: 4px 0; }
        """)

        if self.logic.timer.isActive() or self.logic.is_paused:
            remaining_ms = self.logic.time_remaining_on_pause if self.logic.is_paused else self.logic.timer.remainingTime()
            mins, secs = divmod(remaining_ms // 1000, 60)
            status_text = f"⏳ {self.logic.current_state.replace('_', ' ')}: {int(mins)}m {int(secs)}s"
            info_action = QAction(status_text, self)
            info_action.setDisabled(True)
            menu.addAction(info_action)

        if self.logic.current_state != 'stopped':
            long_break_threshold = self.config.get("long_break_threshold", 90 * 60)
            current_study_time = self.logic.total_study_time

            if current_study_time < long_break_threshold:
                remaining_seconds = long_break_threshold - current_study_time
                if self.logic.current_state == "studying" and self.logic.timer.isActive():
                    timer_remaining_secs = self.logic.timer.remainingTime() // 1000
                    remaining_seconds -= timer_remaining_secs

                mins, _secs = divmod(remaining_seconds, 60)
                long_break_status_text = f"🎯 Long Break in ~{int(mins)}m"
            else:
                long_break_status_text = "🎉 Long Break Available"

            long_break_action = QAction(long_break_status_text, self)
            long_break_action.setDisabled(True)
            menu.addAction(long_break_action)

        menu.addSeparator()

        is_running = self.logic.timer.isActive()
        is_paused = self.logic.is_paused

        start_action = QAction("▶️ Start / Resume", self)
        start_action.triggered.connect(self.logic.start_or_resume)
        if is_running and not is_paused:
            start_action.setDisabled(True)

        pause_action = QAction("⏸️ Pause", self)
        pause_action.triggered.connect(self.logic.pause)
        if not is_running or is_paused:
            pause_action.setDisabled(True)

        always_on_top_text = f"{'✅' if self.is_always_on_top else '🔲'} Always on Top"
        always_on_top_action = QAction(always_on_top_text, self)
        always_on_top_action.triggered.connect(self.toggle_always_on_top)

        opacity_menu = QMenu("💧 Opacity", self)
        for val in [1.0, 0.9, 0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2, 0.1]:
            op_action = QAction(f"{int(val * 100)}%", self)
            op_action.triggered.connect(lambda _, v=val: self.set_opacity(v))
            opacity_menu.addAction(op_action)

        reset_menu = QMenu("🔄 Reset", self)
        reset_cycle_action = QAction("Reset Current Cycle", self)
        reset_cycle_action.triggered.connect(self.logic.reset_cycle)
        clear_all_action = QAction("🗑️ Clear All Statistics", self)
        clear_all_action.triggered.connect(self.confirm_and_reset_all)
        reset_menu.addAction(reset_cycle_action)
        reset_menu.addAction(clear_all_action)

        quit_action = QAction("❌ Quit", self)
        quit_action.triggered.connect(self.close)

        menu.addAction(start_action)
        menu.addAction(pause_action)
        menu.addSeparator()
        menu.addAction(always_on_top_action)
        menu.addMenu(opacity_menu)
        menu.addMenu(reset_menu)
        menu.addSeparator()
        menu.addAction(quit_action)

    def update_stylesheet(self):
        opacity = self.settings.value("ui/opacity", 0.8, type=float)
        self.background_widget.setStyleSheet(f"""
            #background {{ background-color: rgba(46, 52, 64, {opacity}); border-radius: 10px; border: 1px solid #88C0D0; }}
            QLabel {{ background-color: transparent; color: #D8DEE9; font-family: 'Helvetica Neue', 'Segoe UI', Arial, sans-serif; font-size: 15px; }}
            #total_time_label {{ font-size: 12px; color: #A3BE8C; padding-top: 5px; }}
            QSizeGrip {{ background-color: transparent; width: 15px; height: 15px; }}
        """)

    def update_status(self, status_text, state_name):
        if state_name == "long_breaking":
            self.countdown_timer.start()
            self.update_countdown_display()
        else:
            self.countdown_timer.stop()
            self.status_label.setText(status_text)
        self.update_stylesheet()

    def update_countdown_display(self):
        if self.logic.timer.isActive():
            remaining_ms = self.logic.timer.remainingTime()
            mins, secs = divmod(remaining_ms // 1000, 60)
            self.status_label.setText(f"🧘 Long Break\n{int(mins):02}:{int(secs):02}")

    def create_tray_icon(self):
        self.tray_icon = QIcon(resource_path('icon.ico'))
        self.tray = QSystemTrayIcon(self.tray_icon, self)
        # MODIFIED TOOLTIP
        self.tray.setToolTip("EZLockIn")
        self.tray_menu = QMenu(self)
        self.tray_menu.aboutToShow.connect(self.update_tray_menu)
        self.tray.setContextMenu(self.tray_menu)
        self.tray.show()

    def update_tray_menu(self):
        self.populate_context_menu(self.tray_menu)

    def contextMenuEvent(self, event):
        context_menu = QMenu(self)
        self.populate_context_menu(context_menu)
        context_menu.exec(event.globalPos())

    def toggle_always_on_top(self):
        self.is_always_on_top = not self.is_always_on_top
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, self.is_always_on_top)
        self.show()

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

    def closeEvent(self, event):
        if self.logic.current_state == "studying" and self.logic.current_selected_interval:
            update_reward(self.logic.cycle_count, self.logic.current_selected_interval, completed=False)
            self.logic._log_incomplete_session()
        self.logic._clear_current_session()
        self.save_settings()
        if not self._init_failed:
            self.config['total_study_time'] = self.logic.total_study_time
            save_config(self.config)
            self.logic.stop()
            self.tray.hide()
        if CACHE_AVAILABLE:
            close_cache()
        if DB_AVAILABLE:
            close_db()
        event.accept()
        QApplication.quit()

    def update_total_time(self, total_seconds):
        self.total_time_label.setText(f"Total focus: {total_seconds // 3600}h {(total_seconds // 60) % 60}m")

    def set_opacity(self, value):
        self.settings.setValue("ui/opacity", value)
        self.update_stylesheet()

    def save_settings(self):
        if self._init_failed:
            return
        self.settings.setValue("ui/geometry", self.saveGeometry())
        self.settings.setValue("ui/opacity", self.settings.value("ui/opacity", 0.8))
        self.settings.setValue("ui/alwaysOnTop", self.is_always_on_top)

    def load_settings(self):
        geometry = self.settings.value("ui/geometry")
        if geometry:
            self.restoreGeometry(geometry)
        else:
            self.resize(220, 120)
        self.update_total_time(self.logic.total_study_time)

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
    window = StudyTimerGUI(config)

    if window._init_failed:
        sys.exit(1)

    window.show()
    sys.exit(app.exec())