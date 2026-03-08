import subprocess
import sys
import threading
from pathlib import Path
from typing import List

import numpy as np
from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QCheckBox, QDialog, QFileDialog, QHBoxLayout, QLabel,
    QLineEdit, QProgressBar, QPushButton, QVBoxLayout,
)

from src.storage import file_manager


class ExportDialog(QDialog):
    _export_done     = pyqtSignal(list, list)  # (successes, errors)
    _progress_update = pyqtSignal(int)         # percent 0-100

    def __init__(
        self,
        parent,
        stem: str,
        audio_data,           # np.ndarray or None
        sample_rate: int,
        segments: List[dict],
        save_folder: str,
    ):
        super().__init__(parent)
        self._stem = stem or "recording"
        self._audio_data = audio_data
        self._sample_rate = sample_rate
        self._segments = segments
        self._save_folder = save_folder

        self.setWindowTitle("Export Recording")
        self.setMinimumWidth(480)
        self.setModal(True)

        self._build_ui()
        self._export_done.connect(self._on_export_done)
        self._progress_update.connect(self._progress.setValue)

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)
        layout.setContentsMargins(20, 20, 20, 20)

        layout.addWidget(QLabel("<b>Select formats to export:</b>"))

        # --- Checkboxes ---
        self._chk_wav = QCheckBox("Audio file (.wav)")
        self._chk_wav.setChecked(True)
        self._chk_wav.setEnabled(self._audio_data is not None)
        layout.addWidget(self._chk_wav)

        self._chk_transcript = QCheckBox("Transcript (.txt)")
        self._chk_transcript.setChecked(True)
        layout.addWidget(self._chk_transcript)

        self._chk_translation = QCheckBox("Translation (.txt)")
        self._chk_translation.setChecked(True)
        layout.addWidget(self._chk_translation)

        self._chk_docx = QCheckBox("Word Document (.docx)")
        layout.addWidget(self._chk_docx)

        self._chk_srt = QCheckBox("Subtitles (.srt)")
        layout.addWidget(self._chk_srt)

        self._chk_mp3 = QCheckBox("Audio compressed (.mp3)  —  requires ffmpeg")
        self._chk_mp3.setEnabled(self._audio_data is not None)
        layout.addWidget(self._chk_mp3)

        # --- Save to ---
        layout.addSpacing(4)
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("Save to:"))
        self._path_edit = QLineEdit(self._save_folder)
        path_row.addWidget(self._path_edit)
        browse_btn = QPushButton("Browse")
        browse_btn.setFixedWidth(70)
        browse_btn.clicked.connect(self._browse)
        path_row.addWidget(browse_btn)
        layout.addLayout(path_row)

        # --- Progress bar (hidden until export starts) ---
        self._progress = QProgressBar()
        self._progress.setRange(0, 100)
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        # --- Status label ---
        self._status_label = QLabel("")
        self._status_label.setWordWrap(True)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # --- Open folder button (shown after success) ---
        self._open_btn = QPushButton("Open Folder")
        self._open_btn.setVisible(False)
        self._open_btn.clicked.connect(self._open_folder)
        layout.addWidget(self._open_btn)

        # --- Buttons ---
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(self._cancel_btn)
        self._export_btn = QPushButton("Export")
        self._export_btn.setDefault(True)
        self._export_btn.clicked.connect(self._run_export)
        btn_row.addWidget(self._export_btn)
        layout.addLayout(btn_row)

    def _browse(self):
        folder = QFileDialog.getExistingDirectory(self, "Select export folder", self._path_edit.text())
        if folder:
            self._path_edit.setText(folder)

    def _run_export(self):
        self._export_btn.setEnabled(False)
        self._cancel_btn.setEnabled(False)
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._status_label.setVisible(False)
        self._open_btn.setVisible(False)

        tasks = self._build_tasks()
        if not tasks:
            self._export_btn.setEnabled(True)
            self._cancel_btn.setEnabled(True)
            self._status_label.setText("No formats selected.")
            self._status_label.setVisible(True)
            return

        threading.Thread(target=self._do_export, args=(tasks,), daemon=True).start()

    def _build_tasks(self) -> list:
        folder = Path(self._path_edit.text())
        stem = self._stem
        tasks = []
        if self._chk_wav.isChecked() and self._audio_data is not None:
            tasks.append(("wav", folder / f"{stem}.wav"))
        if self._chk_transcript.isChecked():
            tasks.append(("transcript", folder / f"{stem}_transcript.txt"))
        if self._chk_translation.isChecked():
            tasks.append(("translation", folder / f"{stem}_translation.txt"))
        if self._chk_docx.isChecked():
            tasks.append(("docx", folder / f"{stem}.docx"))
        if self._chk_srt.isChecked():
            tasks.append(("srt", folder / f"{stem}.srt"))
        if self._chk_mp3.isChecked() and self._audio_data is not None:
            tasks.append(("mp3", folder / f"{stem}.mp3"))
        return tasks

    def _do_export(self, tasks: list):
        successes = []
        errors = []
        total = len(tasks)

        for i, (fmt, path) in enumerate(tasks):
            try:
                if fmt == "wav":
                    file_manager.export_wav(self._audio_data, self._sample_rate, path)
                elif fmt == "transcript":
                    file_manager.export_transcript_txt(self._segments, path)
                elif fmt == "translation":
                    file_manager.export_translation_txt(self._segments, path)
                elif fmt == "docx":
                    file_manager.export_docx(self._segments, path)
                elif fmt == "srt":
                    file_manager.export_srt(self._segments, path)
                elif fmt == "mp3":
                    file_manager.export_mp3_from_data(self._audio_data, self._sample_rate, path)
                successes.append(str(path))
            except Exception as e:
                errors.append(f"{fmt.upper()}: {e}")

            pct = int((i + 1) / total * 100)
            self._progress_update.emit(pct)

        self._export_done.emit(successes, errors)

    def _on_export_done(self, successes: list, errors: list):
        self._progress.setValue(100)
        self._export_btn.setEnabled(True)
        self._cancel_btn.setEnabled(True)
        self._status_label.setVisible(True)

        parts = []
        if successes:
            parts.append(f"Exported {len(successes)} file(s) to {self._path_edit.text()}")
        if errors:
            parts.append("Errors:\n" + "\n".join(errors))

        self._status_label.setText("\n".join(parts))
        if successes:
            self._open_btn.setVisible(True)

    def _open_folder(self):
        folder = self._path_edit.text()
        if sys.platform == "darwin":
            subprocess.run(["open", folder])
        elif sys.platform == "win32":
            subprocess.run(["explorer", folder])
        else:
            subprocess.run(["xdg-open", folder])
