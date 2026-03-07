import queue
import sys
import threading

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication

from src.audio.recorder import MicrophoneNotFoundError, Recorder
from src.transcription.chunk_processor import ChunkProcessor
from src.transcription.whisper_engine import TranscriptionError, WhisperEngine
from src.translation.translator import Translator
from src.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("RealTime Recorder")

    recorder = Recorder()
    window = MainWindow()
    translator = Translator()

    result_queue: queue.Queue = queue.Queue()       # (timestamp, text, language)
    translation_queue: queue.Queue = queue.Queue()  # (timestamp, translated_text)

    # --- Load Whisper model in background (keeps UI responsive) ---
    whisper_engine: list = [None]
    engine_error: list = [None]
    engine_ready = threading.Event()

    def load_engine():
        try:
            whisper_engine[0] = WhisperEngine()
        except TranscriptionError as e:
            engine_error[0] = str(e)
        finally:
            engine_ready.set()

    threading.Thread(target=load_engine, daemon=True).start()
    window.show_status("Loading Whisper model...")

    chunk_processor: list = [None]
    engine_status_shown = [False]

    # --- Poll queues every 200ms (main thread — safe for UI updates) ---
    def poll():
        if not engine_status_shown[0] and engine_ready.is_set():
            engine_status_shown[0] = True
            if engine_error[0]:
                window.show_status(f"Error: {engine_error[0]}")
            else:
                window.show_status("Ready — click Record to start")

        while not result_queue.empty():
            try:
                timestamp, text, language = result_queue.get_nowait()
                window.append_transcript(f"[{timestamp}] {text}")
                window.set_transcribing(False)
                src = window.get_source_lang()
                tgt = window.get_target_lang()

                def on_translated(result, ts=timestamp):
                    translation_queue.put((ts, result))

                translator.translate_async(text, src, tgt, on_translated)
            except queue.Empty:
                break

        while not translation_queue.empty():
            try:
                timestamp, result = translation_queue.get_nowait()
                window.append_translation(f"[{timestamp}] {result}")
            except queue.Empty:
                break

    poll_timer = QTimer()
    poll_timer.setInterval(200)
    poll_timer.timeout.connect(poll)
    poll_timer.start()

    # --- Recording callbacks ---

    def on_start():
        if not engine_ready.is_set():
            window.show_error("Whisper model is still loading, please wait...")
            return
        if engine_error[0]:
            window.show_error(engine_error[0])
            return
        try:
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
            path = recorder.stop()
            if path:
                window.show_status(f"Saved: {path}")
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
