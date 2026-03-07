import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import numpy as np

from src.transcription.whisper_engine import WhisperEngine, TranscriptionError

SAMPLE_RATE = 16000
CHUNK_SECONDS = 2
CHUNK_SAMPLES = SAMPLE_RATE * CHUNK_SECONDS
SILENCE_THRESHOLD = 0.02  # raised to cut more noise before sending to Whisper


class ChunkProcessor:
    def __init__(
        self,
        audio_queue: queue.Queue,
        result_queue: queue.Queue,
        whisper_engine: WhisperEngine,
        get_language: Optional[Callable[[], str]] = None,
    ):
        self._audio_queue = audio_queue
        self._result_queue = result_queue
        self._whisper = whisper_engine
        self._get_language = get_language  # callable: returns 'en', 'vi', 'auto', etc.
        self._running = False
        self._collect_thread = None
        self._transcribe_executor = ThreadPoolExecutor(max_workers=1)
        self._start_time = None

    def start(self):
        self._running = True
        self._start_time = time.time()
        self._collect_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._collect_thread.start()

    def stop(self):
        self._running = False

    def _get_timestamp(self) -> str:
        elapsed = int(time.time() - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _transcribe(self, audio: np.ndarray, timestamp: str, language: Optional[str]):
        t0 = time.time()
        try:
            text, lang, _ = self._whisper.transcribe_chunk(audio, language=language)
            elapsed = time.time() - t0
            print(f"[WHISPER] {elapsed:.2f}s → '{text[:60] if text else '(empty)'}'", flush=True)
            if text:
                self._result_queue.put((timestamp, text, lang))
        except TranscriptionError as e:
            print(f"[WHISPER] error: {e}", flush=True)

    def _collect_loop(self):
        buffer = []
        buffer_samples = 0

        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                if chunk is None or len(chunk) == 0:
                    continue
                buffer.append(chunk)
                buffer_samples += len(chunk)

                if buffer_samples >= CHUNK_SAMPLES:
                    audio = np.concatenate(buffer)
                    buffer = []
                    buffer_samples = 0

                    if np.max(np.abs(audio)) >= SILENCE_THRESHOLD:
                        timestamp = self._get_timestamp()
                        language = self._get_language() if self._get_language else None
                        print(f"[CHUNK] submitted at {timestamp}, lang={language}", flush=True)
                        self._transcribe_executor.submit(self._transcribe, audio, timestamp, language)

            except queue.Empty:
                continue

        # Flush remaining audio
        if buffer:
            audio = np.concatenate(buffer)
            if np.max(np.abs(audio)) >= SILENCE_THRESHOLD:
                timestamp = self._get_timestamp()
                language = self._get_language() if self._get_language else None
                self._transcribe_executor.submit(self._transcribe, audio, timestamp, language).result()

        self._transcribe_executor.shutdown(wait=False)
