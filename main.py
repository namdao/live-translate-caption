import queue
import sys
import threading
import time

from PyQt6.QtCore import QObject, QTimer, pyqtSignal
from PyQt6.QtWidgets import QApplication

from src.audio.recorder import MicrophoneNotFoundError, Recorder
from src.transcription.chunk_processor import ChunkProcessor
from src.transcription.whisper_engine import TranscriptionError, WhisperEngine
from src.translation.translator import Translator
from src.ui.main_window import MainWindow


class _Bridge(QObject):
    """Thread-safe signal bridge: background threads emit → main thread receives."""
    transcription_ready = pyqtSignal(str, str)   # (timestamp, text)
    translation_ready   = pyqtSignal(str, str)   # (timestamp, translation)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RealTime Recorder")

    recorder = Recorder()
    window = MainWindow()
    translator = Translator()
    bridge = _Bridge()

    result_queue: queue.Queue = queue.Queue()

    whisper_engine: list = [None]
    engine_error: list = [None]
    engine_ready = threading.Event()

    def load_engine(model_size: str = None, backend: str = None):
        engine_ready.clear()
        engine_error[0] = None
        whisper_engine[0] = None
        size = model_size or window.get_selected_model_size()
        bknd = backend or window.get_selected_backend()
        try:
            whisper_engine[0] = WhisperEngine(model_size=size, backend=bknd)
        except TranscriptionError as e:
            engine_error[0] = str(e)
        finally:
            engine_ready.set()

    threading.Thread(target=load_engine, daemon=True).start()
    window.show_status("Loading Whisper model...")

    chunk_processor: list = [None]
    engine_status_shown = [False]
    record_start_time: list = [0.0]

    # --- Reload model when user changes size or backend ---
    def on_model_size_changed(size: str):
        engine_status_shown[0] = False
        window.set_model_loading(True)
        window.show_status(f"Loading '{size}' model...")
        threading.Thread(target=load_engine, args=(size,), daemon=True).start()

    def on_backend_changed(backend: str):
        engine_status_shown[0] = False
        window.set_model_loading(True)
        window.show_status(f"Switching to {backend.upper()} backend...")
        threading.Thread(target=load_engine, kwargs={"backend": backend}, daemon=True).start()

    window.model_size_changed.connect(on_model_size_changed)
    window.backend_changed.connect(on_backend_changed)

    # --- Translation signal: fires immediately from translator thread → no poll wait ---
    bridge.translation_ready.connect(window.update_segment_translation)

    # --- Transcription signal: fires from poll timer → add segment + kick off translation ---
    def on_transcription(timestamp: str, text: str):
        window.add_segment(timestamp, text)
        window.set_transcribing(False)
        src = window.get_source_lang()
        tgt = window.get_target_lang()
        translator.translate_async(
            text, src, tgt,
            lambda result, ts=timestamp: bridge.translation_ready.emit(ts, result),
        )

    bridge.transcription_ready.connect(on_transcription)

    # --- Poll transcript queue (100ms) ---
    def poll():
        if not engine_status_shown[0] and engine_ready.is_set():
            engine_status_shown[0] = True
            window.set_model_loading(False)
            if engine_error[0]:
                window.show_status(f"Error: {engine_error[0]}")
            else:
                window.show_status("Ready — click Record to start")

        while True:
            try:
                timestamp, text, language = result_queue.get_nowait()
                bridge.transcription_ready.emit(timestamp, text)
            except queue.Empty:
                break

    poll_timer = QTimer()
    poll_timer.setInterval(100)
    poll_timer.timeout.connect(poll)
    poll_timer.start()

    # --- Poll viz queue (50ms) for waveform + level meter ---
    def poll_viz():
        vq = recorder.viz_queue
        while True:
            try:
                rms = vq.get_nowait()
                window.push_audio_level(rms)
            except queue.Empty:
                break

    viz_timer = QTimer()
    viz_timer.setInterval(50)
    viz_timer.timeout.connect(poll_viz)
    viz_timer.start()

    # --- Recording callbacks ---

    def on_start():
        if not engine_ready.is_set():
            window.show_error("Whisper model is still loading, please wait...")
            return
        if engine_error[0]:
            window.show_error(engine_error[0])
            return
        try:
            record_start_time[0] = time.time()
            recorder.start(device_index=window.get_device_index())
            cp = ChunkProcessor(
                recorder.audio_queue, result_queue, whisper_engine[0],
                get_language=window.get_source_lang,
            )
            cp.start()
            chunk_processor[0] = cp
        except MicrophoneNotFoundError as e:
            window.show_error(str(e))

    def on_stop():
        if chunk_processor[0]:
            chunk_processor[0].stop()
            chunk_processor[0] = None
        try:
            result = recorder.stop()
            if result:
                stem, audio_data, sample_rate = result
                recorder_elapsed = int(time.time() - record_start_time[0])
                h = recorder_elapsed // 3600
                m = (recorder_elapsed % 3600) // 60
                s = recorder_elapsed % 60
                window.set_last_recording(stem, audio_data, sample_rate)
                window.show_status(
                    f"Recorded: {stem}  —  duration {h:02d}:{m:02d}:{s:02d}  —  click Export to save"
                )
            else:
                window.show_status("Stopped (no audio recorded)")
        except Exception as e:
            window.show_error(str(e))

    window.recording_started.connect(on_start)
    window.recording_stopped.connect(on_stop)
    window.recording_paused.connect(recorder.pause)
    window.recording_resumed.connect(recorder.resume)

    window.show()
    ret = app.exec()
    translator.shutdown()
    sys.exit(ret)


if __name__ == "__main__":
    main()
