from pathlib import Path

import sounddevice as sd
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QKeySequence, QPalette, QShortcut
from PyQt6.QtWidgets import (
    QButtonGroup, QFileDialog, QGroupBox, QHBoxLayout, QLabel,
    QMainWindow, QProgressBar, QPushButton, QRadioButton, QSizePolicy,
    QStatusBar, QTextEdit, QVBoxLayout, QWidget, QComboBox,
)

from src.ui.waveform_widget import WaveformWidget
from src.ui.level_meter import LevelMeter

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
    padding: 8px 16px;
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
QLabel { color: #e0e0e0; }
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
    font-size: 12px;
}
QComboBox::drop-down { border: none; }
QComboBox QAbstractItemView {
    background-color: #16213e;
    color: #e0e0e0;
    selection-background-color: #e94560;
}
QGroupBox {
    border: 1px solid #444466;
    border-radius: 4px;
    margin-top: 10px;
    padding-top: 6px;
    font-size: 12px;
    font-weight: bold;
    color: #aaaacc;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 8px;
    padding: 0 4px;
}
QRadioButton { color: #e0e0e0; font-size: 12px; }
QRadioButton::indicator {
    width: 12px; height: 12px; border-radius: 6px;
}
QRadioButton::indicator:unchecked {
    background-color: #16213e;
    border: 2px solid #444466;
}
QRadioButton::indicator:checked {
    background-color: #e94560;
    border: 2px solid #e94560;
}
QProgressBar {
    background-color: #16213e;
    border: 1px solid #444466;
    border-radius: 3px;
    height: 10px;
    text-align: center;
    font-size: 10px;
}
QProgressBar::chunk { background-color: #e94560; }
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

_MODEL_SIZES = ["tiny", "base", "small", "turbo"]


class MainWindow(QMainWindow):
    recording_started  = pyqtSignal()
    recording_stopped  = pyqtSignal()
    recording_paused   = pyqtSignal()
    recording_resumed  = pyqtSignal()
    model_size_changed    = pyqtSignal(str)
    backend_changed       = pyqtSignal(str)   # 'mlx' or 'openai'
    save_folder_changed   = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("RealTime Recorder")
        self.setMinimumSize(1000, 600)
        self.setStyleSheet(STYLE)

        self._elapsed_seconds = 0
        self._is_recording = False
        self._is_paused = False
        self._save_folder = str(Path.home() / "Recordings")
        self._segments: list = []        # [{timestamp, text, translation}]
        self._last_stem: str = ""
        self._last_audio_data = None
        self._last_sample_rate: int = 16000

        self._build_ui()
        self._setup_timer()
        self._setup_shortcuts()

    # ------------------------------------------------------------------ #
    #  UI construction                                                     #
    # ------------------------------------------------------------------ #

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setSpacing(0)
        root_layout.setContentsMargins(0, 0, 0, 0)

        root_layout.addWidget(self._build_sidebar(), 0)
        root_layout.addWidget(self._build_content(), 1)

        self.setStatusBar(QStatusBar())
        self._set_idle_state()

    def _build_sidebar(self) -> QWidget:
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        sidebar.setStyleSheet("background-color: #0f0f1e; border-right: 1px solid #222244;")
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(10, 12, 10, 12)
        layout.setSpacing(8)

        # --- Input Device ---
        dev_group = QGroupBox("Input Device")
        dev_layout = QVBoxLayout(dev_group)
        dev_layout.setSpacing(4)

        self._device_combo = QComboBox()
        self._device_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self._device_combo.currentIndexChanged.connect(self._on_device_changed)
        dev_layout.addWidget(self._device_combo)

        refresh_btn = QPushButton("Refresh devices")
        refresh_btn.setToolTip("Re-scan audio devices")
        refresh_btn.clicked.connect(self._refresh_devices)
        dev_layout.addWidget(refresh_btn)
        layout.addWidget(dev_group)
        self._refresh_devices()

        # --- Backend selector ---
        backend_group = QGroupBox("Whisper Backend")
        backend_layout = QVBoxLayout(backend_group)
        backend_layout.setSpacing(2)

        self._backend_group = QButtonGroup(self)
        self._rb_mlx    = QRadioButton("MLX  (Apple GPU)")
        self._rb_openai = QRadioButton("OpenAI  (CPU)")
        self._rb_mlx.setChecked(True)
        self._backend_group.addButton(self._rb_mlx)
        self._backend_group.addButton(self._rb_openai)
        backend_layout.addWidget(self._rb_mlx)
        backend_layout.addWidget(self._rb_openai)

        self._backend_group.buttonClicked.connect(self._on_backend_clicked)
        layout.addWidget(backend_group)

        # --- Settings (model size) ---
        settings_group = QGroupBox("Whisper Model")
        settings_layout = QVBoxLayout(settings_group)
        settings_layout.setSpacing(2)

        self._model_group = QButtonGroup(self)
        default_model = "turbo"
        for size in _MODEL_SIZES:
            rb = QRadioButton(size)
            if size == default_model:
                rb.setChecked(True)
            self._model_group.addButton(rb)
            settings_layout.addWidget(rb)

        self._model_group.buttonClicked.connect(
            lambda btn: self.model_size_changed.emit(btn.text())
        )

        self._model_progress = QProgressBar()
        self._model_progress.setVisible(False)
        self._model_progress.setRange(0, 0)  # indeterminate
        settings_layout.addWidget(self._model_progress)
        layout.addWidget(settings_group)

        # --- Output folder ---
        output_group = QGroupBox("Output Folder")
        output_layout = QVBoxLayout(output_group)
        output_layout.setSpacing(4)

        self._folder_label = QLabel(self._save_folder)
        self._folder_label.setWordWrap(True)
        self._folder_label.setStyleSheet("font-size: 11px; color: #aaaacc;")
        output_layout.addWidget(self._folder_label)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_folder)
        output_layout.addWidget(browse_btn)
        layout.addWidget(output_group)

        layout.addStretch()
        return sidebar

    def _build_content(self) -> QWidget:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setSpacing(8)
        layout.setContentsMargins(14, 12, 14, 8)

        # --- Top bar ---
        top = QHBoxLayout()
        title = QLabel("RealTime Recorder")
        title.setFont(QFont("Arial", 16, QFont.Weight.Bold))
        top.addWidget(title)
        top.addStretch()
        self._status_dot = QLabel("●")
        self._status_dot.setStyleSheet("color: #444466; font-size: 20px;")
        top.addWidget(self._status_dot)
        layout.addLayout(top)

        # --- Language selector row ---
        lang_row = QHBoxLayout()
        lang_row.addWidget(QLabel("Source:"))
        self._src_combo = QComboBox()
        for name, _ in _SOURCE_LANGS:
            self._src_combo.addItem(name)
        lang_row.addWidget(self._src_combo)

        arrow = QLabel("→ Translate to:")
        arrow.setStyleSheet("margin-left: 10px;")
        lang_row.addWidget(arrow)
        self._tgt_combo = QComboBox()
        for name, _ in _TARGET_LANGS:
            self._tgt_combo.addItem(name)
        lang_row.addWidget(self._tgt_combo)
        lang_row.addStretch()

        self._spinner = QLabel("")
        self._spinner.setStyleSheet("color: #ffcc00; font-size: 12px;")
        lang_row.addWidget(self._spinner)
        layout.addLayout(lang_row)

        # --- Waveform ---
        self._waveform = WaveformWidget()
        layout.addWidget(self._waveform)

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

        lw = QWidget(); lw.setLayout(left_col)
        rw = QWidget(); rw.setLayout(right_col)
        panels.addWidget(lw, 55)
        panels.addWidget(rw, 45)
        layout.addLayout(panels, stretch=1)

        # --- Bottom controls ---
        bottom = QHBoxLayout()
        bottom.setSpacing(8)

        self._btn_record = QPushButton("● Record")
        self._btn_record.setToolTip("Start recording  [Space]")
        self._btn_pause  = QPushButton("⏸ Pause")
        self._btn_pause.setToolTip("Pause / Resume  [Space]")
        self._btn_stop   = QPushButton("■ Stop")
        self._btn_stop.setToolTip("Stop recording  [Esc]")
        self._btn_export = QPushButton("Export...")
        self._btn_export.setToolTip("Export transcript and audio  [Ctrl+E]")
        self._btn_export.setEnabled(False)

        self._timer_label = QLabel("00:00:00")
        self._timer_label.setFont(QFont("Courier", 14))
        self._timer_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        self._level_meter = LevelMeter()

        bottom.addWidget(self._btn_record)
        bottom.addWidget(self._btn_pause)
        bottom.addWidget(self._btn_stop)
        bottom.addWidget(self._btn_export)
        bottom.addStretch()
        bottom.addWidget(self._timer_label)
        bottom.addWidget(self._level_meter)
        layout.addLayout(bottom)

        self._btn_record.clicked.connect(self._on_record)
        self._btn_pause.clicked.connect(self._on_pause)
        self._btn_stop.clicked.connect(self._on_stop)
        self._btn_export.clicked.connect(self._on_export)

        return content

    def _setup_timer(self):
        self._timer = QTimer()
        self._timer.setInterval(1000)
        self._timer.timeout.connect(self._tick)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence(Qt.Key.Key_Space), self).activated.connect(
            self._toggle_record_pause
        )
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(
            self._save_transcript_to_file
        )
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self).activated.connect(
            self._on_stop
        )
        QShortcut(QKeySequence("Ctrl+E"), self).activated.connect(
            self._on_export
        )

    # ------------------------------------------------------------------ #
    #  State helpers                                                       #
    # ------------------------------------------------------------------ #

    def _set_idle_state(self):
        self._btn_record.setEnabled(True)
        self._btn_pause.setEnabled(False)
        self._btn_stop.setEnabled(False)
        self._btn_pause.setText("⏸ Pause")
        self._status_dot.setStyleSheet("color: #444466; font-size: 20px;")
        self._waveform.set_active(False)
        # Enable Export only if there is something to export
        self._btn_export.setEnabled(bool(self._last_audio_data is not None or self._segments))

    def _set_recording_state(self):
        self._btn_record.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_export.setEnabled(False)
        self._btn_pause.setText("⏸ Pause")
        self._status_dot.setStyleSheet("color: #e94560; font-size: 20px;")
        self._waveform.set_active(True)

    def _set_paused_state(self):
        self._btn_record.setEnabled(False)
        self._btn_pause.setEnabled(True)
        self._btn_stop.setEnabled(True)
        self._btn_pause.setText("▶ Resume")
        self._status_dot.setStyleSheet("color: #ffcc00; font-size: 20px;")
        self._waveform.set_active(False)

    # ------------------------------------------------------------------ #
    #  Slots                                                               #
    # ------------------------------------------------------------------ #

    def _on_record(self):
        self._elapsed_seconds = 0
        self._segments = []
        self._last_stem = ""
        self._last_audio_data = None
        self._transcript.clear()
        self._translation.clear()
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
            self._set_recording_state()
            self.recording_resumed.emit()

    def _on_stop(self):
        if not self._is_recording:
            return
        self._timer.stop()
        self._is_recording = False
        self._is_paused = False
        self._set_idle_state()
        self.set_transcribing(False)
        self.recording_stopped.emit()

    def _on_export(self):
        from src.ui.export_dialog import ExportDialog
        dlg = ExportDialog(
            self,
            self._last_stem,
            self._last_audio_data,
            self._last_sample_rate,
            self._segments,
            self._save_folder,
        )
        dlg.exec()

    def _toggle_record_pause(self):
        if not self._is_recording:
            self._on_record()
        else:
            self._on_pause()

    def _tick(self):
        self._elapsed_seconds += 1
        self._update_timer_label()

    def _update_timer_label(self):
        h = self._elapsed_seconds // 3600
        m = (self._elapsed_seconds % 3600) // 60
        s = self._elapsed_seconds % 60
        self._timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")

    def _on_device_changed(self):
        if self._is_recording:
            self._on_stop()
            self.show_status("Device changed — recording stopped")

    def _refresh_devices(self):
        self._device_combo.blockSignals(True)
        self._device_combo.clear()
        self._device_combo.addItem("Default (system microphone)", userData=None)
        for idx, d in enumerate(sd.query_devices()):
            if d['max_input_channels'] > 0:
                self._device_combo.addItem(d['name'], userData=idx)
        self._device_combo.blockSignals(False)

    def _browse_folder(self):
        folder = QFileDialog.getExistingDirectory(
            self, "Select save folder", self._save_folder
        )
        if folder:
            self._save_folder = folder
            self._folder_label.setText(folder)
            self.save_folder_changed.emit(folder)

    def _save_transcript_to_file(self):
        text = self._transcript.toPlainText().strip()
        if not text:
            self.show_status("Nothing to save")
            return
        from datetime import datetime
        from src.storage.file_manager import save_txt
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        path = Path(self._save_folder) / f"transcript_{ts}.txt"
        save_txt(text, path)
        self.show_status(f"Transcript saved: {path}")

    # ------------------------------------------------------------------ #
    #  Public API                                                          #
    # ------------------------------------------------------------------ #

    def show_status(self, message: str):
        self.statusBar().showMessage(message)

    def append_transcript(self, text: str):
        self._transcript.append(text)
        self._transcript.verticalScrollBar().setValue(
            self._transcript.verticalScrollBar().maximum()
        )

    def add_segment(self, timestamp: str, text: str):
        """Add a new transcript segment and display it."""
        self._segments.append({"timestamp": timestamp, "text": text, "translation": ""})
        self.append_transcript(f"[{timestamp}] {text}")

    def update_segment_translation(self, timestamp: str, translation: str):
        """Attach translation to matching segment and display it."""
        for seg in reversed(self._segments):
            if seg["timestamp"] == timestamp:
                seg["translation"] = translation
                break
        self.append_translation(f"[{timestamp}] {translation}")

    def append_translation(self, text: str):
        self._translation.append(text)
        self._translation.verticalScrollBar().setValue(
            self._translation.verticalScrollBar().maximum()
        )

    def set_last_recording(self, stem: str, audio_data, sample_rate: int):
        self._last_stem = stem
        self._last_audio_data = audio_data
        self._last_sample_rate = sample_rate

    def set_transcribing(self, active: bool):
        self._spinner.setText("⏳ Transcribing..." if active else "")

    def set_model_loading(self, loading: bool):
        self._model_progress.setVisible(loading)

    def push_audio_level(self, rms: float):
        self._waveform.push_level(rms)
        self._level_meter.set_level(rms)

    def get_device_index(self):
        return self._device_combo.currentData()

    def get_source_lang(self) -> str:
        return _SOURCE_LANGS[self._src_combo.currentIndex()][1]

    def get_target_lang(self) -> str:
        return _TARGET_LANGS[self._tgt_combo.currentIndex()][1]

    def get_selected_model_size(self) -> str:
        btn = self._model_group.checkedButton()
        return btn.text() if btn else "turbo"

    def get_selected_backend(self) -> str:
        return "mlx" if self._rb_mlx.isChecked() else "openai"

    def _on_backend_clicked(self, btn):
        backend = "mlx" if btn is self._rb_mlx else "openai"
        self.backend_changed.emit(backend)

    def show_error(self, message: str):
        self._set_idle_state()
        self._timer.stop()
        self.set_transcribing(False)
        self.statusBar().showMessage(f"Error: {message}")
