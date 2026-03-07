from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QTextEdit, QLabel, QStatusBar
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QFont

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
"""


class MainWindow(QMainWindow):
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal()
    recording_paused = pyqtSignal()
    recording_resumed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RealTime Recorder")
        self.setMinimumSize(700, 500)
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
        layout.setSpacing(12)
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

        # --- Transcript area ---
        self._transcript = QTextEdit()
        self._transcript.setReadOnly(True)
        self._transcript.setPlaceholderText("Transcript will appear here...")
        layout.addWidget(self._transcript, stretch=1)

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
        self.recording_stopped.emit()

    def _tick(self):
        self._elapsed_seconds += 1
        self._update_timer_label()

    def _update_timer_label(self):
        h = self._elapsed_seconds // 3600
        m = (self._elapsed_seconds % 3600) // 60
        s = self._elapsed_seconds % 60
        self._timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    # --- Public API for main.py ---

    def show_status(self, message: str):
        self.statusBar().showMessage(message)

    def append_transcript(self, text: str):
        self._transcript.append(text)

    def show_error(self, message: str):
        self._set_idle_state()
        self._timer.stop()
        self._btn_pause.setText("Pause")
        self.statusBar().showMessage(f"Error: {message}")
