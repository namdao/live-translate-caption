from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QStatusBar, QComboBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

import sounddevice as sd

STYLE = """
QMainWindow, QWidget {
    background-color: #1a1a2e;
    color: #e0e0e0;
}
QTextEdit {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #e94560;
    border-radius: 4px;
    padding: 8px;
    font-size: 14px;
}
QPushButton {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #e94560;
    border-radius: 4px;
    padding: 8px 20px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #e94560;
    color: #ffffff;
}
QPushButton:disabled {
    background-color: #0f3460;
    color: #666666;
    border-color: #444466;
}
QLabel {
    color: #e0e0e0;
}
QStatusBar {
    background-color: #0f3460;
    color: #e0e0e0;
}
QComboBox {
    background-color: #16213e;
    color: #e0e0e0;
    border: 1px solid #e94560;
    border-radius: 4px;
    padding: 4px 8px;
    font-size: 13px;
}
QComboBox::drop-down {
    border: none;
}
QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    selection-background-color: #e94560;
}
"""

_SOURCE_LANGS = [
    ("Auto",       "auto"),
    ("Vietnamese", "vi"),
    ("English",    "en"),
    ("Japanese",   "ja"),
    ("Korean",     "ko"),
    ("Chinese",    "zh-CN"),
]

_TARGET_LANGS = [
    ("Vietnamese", "vi"),
    ("English",    "en"),
    ("Japanese",   "ja"),
    ("Korean",     "ko"),
    ("Chinese",    "zh-CN"),
    ("French",     "fr"),
    ("Spanish",    "es"),
    ("German",     "de"),
]


class MainWindow(QMainWindow):
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    recording_paused = pyqtSignal()
    recording_resumed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RealTime Recorder")
        self.setMinimumSize(900, 560)
        self.setStyleSheet(STYLE)

        self._elapsed_seconds = 0
        self._is_recording = False
        self._is_paused = False

        self._build_ui()
        self._setup_timer()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(10)
        layout.setContentsMargins(16, 16, 16, 8)

        # --- Top bar ---
        top = QHBoxLayout()
        title = QLabel("RealTime Recorder")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        top.addWidget(title)
        top.addStretch()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #444466; font-size: 20px;")
        top.addWidget(self._status_dot)
        layout.addLayout(top)

        # --- Device selector row ---
        dev_row = QHBoxLayout()
        dev_row.addWidget(QLabel("Input device:"))
        self._device_combo = QComboBox()
        self._device_combo.setMinimumWidth(260)
        dev_row.addWidget(self._device_combo)
        refresh_btn = QPushButton("↺")
        refresh_btn.setFixedWidth(32)
        refresh_btn.setToolTip("Refresh device list")
        refresh_btn.clicked.connect(self._refresh_devices)
        dev_row.addWidget(refresh_btn)
        dev_row.addStretch()
        layout.addLayout(dev_row)
        self._refresh_devices()

        # --- Language selector row ---
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Source:"))
        self._src_combo = QComboBox()
        for name, _ in _SOURCE_LANGS:
            self._src_combo.addItem(name)
        lang_row.addWidget(self._src_combo)

        arrow = QLabel("→ Translate to:")
        arrow.setStyleSheet("margin-left: 12px;")
        lang_row.addWidget(arrow)
        self._tgt_combo = QComboBox()
        for name, _ in _TARGET_LANGS:
            self._tgt_combo.addItem(name)
        lang_row.addWidget(self._tgt_combo)

        lang_row.addStretch()

        self._spinner = QLabel("")
        self._spinner.setStyleSheet("color: #ffcc00; font-size: 13px;")
        lang_row.addWidget(self._spinner)
        layout.addLayout(lang_row)

        # --- Two-panel transcript + translation ---
        panels = QHBoxLayout()
        panels.setSpacing(10)

        left_col = QVBoxLayout()
        left_col.addWidget(QLabel("Transcript"))
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setPlaceholderText("Transcript will appear here...")
        left_col.addWidget(self._transcript)

        right_col = QVBoxLayout()
        right_col.addWidget(QLabel("Translation"))
        self._translation = QTextEdit()
        self._translation.setReadOnly(True)
        self._translation.setPlaceholderText("Translation will appear here...")
        right_col.addWidget(self._translation)

        left_widget = QWidget()
        left_widget.setLayout(left_col)
        right_widget = QWidget()
        right_widget.setLayout(right_col)

        panels.addWidget(left_widget, 55)
        panels.addWidget(right_widget, 45)
        layout.addLayout(panels, stretch=1)

        # --- Bottom controls ---
        bottom = QHBoxLayout()
        self._btn_record = QPushButton("Record")
        self._btn_pause = QPushButton("Pause")
        self._btn_stop = QPushButton("Stop")
        self._timer_label = QLabel("00:00:00")
        self._timer_label.setFont(QFont("Courier", 14))
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        bottom.addWidget(self._btn_record)
        bottom.addWidget(self._btn_pause)
        bottom.addWidget(self._btn_stop)
        bottom.addStretch()
        bottom.addWidget(self._timer_label)
        layout.addLayout(bottom)

        self.setStatusBar(QStatusBar())
        self._set_idle_state()

        self._btn_record.clicked.connect(self._on_record)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_stop.clicked.connect(self._on_stop)

    def _setup_timer(self):
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    # --- State helpers ---

    def _set_idle_state(self):
        self._btn_record.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._status_dot.setStyleSheet("color: #444466; font-size: 20px;")

    def _set_recording_state(self):
        self._btn_record.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._status_dot.setStyleSheet("color: #e94560; font-size: 20px;")

    def _set_paused_state(self):
        self._btn_record.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_pause.setText("Resume")
        self._btn_stop.setEnabled(True)
        self._status_dot.setStyleSheet("color: #ff9900; font-size: 20px;")

    # --- Slots ---

    def _on_record(self):
        self._elapsed_seconds = 0
        self._update_timer_label()
        self._timer.start()
        self._is_recording = True
        self._is_paused = False
        self._set_recording_state()
        self.recording_started.emit()

    def _on_pause(self):
        if not self._is_paused:
            self._is_paused = True
            self._timer.stop()
            self._set_paused_state()
            self.recording_paused.emit()
        else:
            self._is_paused = False
            self._timer.start()
            self._btn_pause.setText("Pause")
            self._set_recording_state()
            self.recording_resumed.emit()

    def _on_stop(self):
        self._timer.stop()
        self._is_recording = False
        self._is_paused = False
        self._btn_pause.setText("Pause")
        self._set_idle_state()
        self.set_transcribing(False)
        self.recording_stopped.emit()

    def _tick(self):
        self._elapsed_seconds += 1
        self._update_timer_label()

    def _update_timer_label(self):
        h = self._elapsed_seconds // 3600
        m = (self._elapsed_seconds % 3600) // 60
        s = self._elapsed_seconds % 60
        self._timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # --- Public API ---

    def show_status(self, message: str):
        self.statusBar().showMessage(message)

    def append_transcript(self, text: str):
        self._transcript.append(text)
        self._transcript.verticalScrollBar().setValue(
            self._transcript.verticalScrollBar().maximum()
        )

    def append_translation(self, text: str):
        self._translation.append(text)
        self._translation.verticalScrollBar().setValue(
            self._translation.verticalScrollBar().maximum()
        )

    def set_transcribing(self, active: bool):
        self._spinner.setText("⏳ Transcribing..." if active else "")

    def _refresh_devices(self):
        self._device_combo.clear()
        self._device_combo.addItem("Default (system microphone)", userData=None)
        for idx, d in enumerate(sd.query_devices()):
            if d['max_input_channels'] > 0:
                self._device_combo.addItem(d['name'], userData=idx)

    def get_device_index(self):
        """Returns selected device index, or None for system default."""
        return self._device_combo.currentData()

    def get_source_lang(self) -> str:
        idx = self._src_combo.currentIndex()
        return _SOURCE_LANGS[idx][1]

    def get_target_lang(self) -> str:
        idx = self._tgt_combo.currentIndex()
        return _TARGET_LANGS[idx][1]

    def show_error(self, message: str):
        self._set_idle_state()
        self._timer.stop()
        self._btn_pause.setText("Pause")
        self.set_transcribing(False)
        self.statusBar().showMessage(f"Error: {message}")
