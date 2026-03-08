import queue
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Optional

import numpy as np

from src.transcription.whisper_engine import WhisperEngine, TranscriptionError

SAMPLE_RATE     = 16000
CHUNK_SECONDS   = 1
CHUNK_SAMPLES   = SAMPLE_RATE * CHUNK_SECONDS
SILENCE_THRESHOLD = 0.02

# Sentence accumulator tuning
MIN_FLUSH_WORDS   = 6    # flush when buffer reaches this many words
MAX_BUFFER_WORDS  = 40   # force flush even if sentence isn't "done"
FLUSH_TIMEOUT     = 2.5  # flush after this many seconds of no new chunks


class ChunkProcessor:
    def __init__(
        self,
        audio_queue: queue.Queue,
        result_queue: queue.Queue,
        whisper_engine,
        get_language: Optional[Callable[[], str]] = None,
    ):
        self._audio_queue  = audio_queue
        self._result_queue = result_queue
        self._whisper      = whisper_engine
        self._get_language = get_language
        self._running      = False
        self._collect_thread = None
        self._transcribe_executor = ThreadPoolExecutor(max_workers=1)
        self._start_time   = None

        # --- Sentence accumulator ---
        self._buf_text      = ""
        self._buf_timestamp = ""
        self._buf_lang      = ""
        self._buf_updated   = 0.0
        self._buf_lock      = threading.Lock()

    def start(self):
        self._running    = True
        self._start_time = time.time()
        self._collect_thread = threading.Thread(target=self._collect_loop, daemon=True)
        self._collect_thread.start()

    def stop(self):
        self._running = False

    # ------------------------------------------------------------------ #

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
            print(f"[CHUNK] {elapsed:.2f}s → '{text[:60] if text else '(empty)'}'", flush=True)
            if text:
                self._accumulate(timestamp, text, lang)
        except TranscriptionError as e:
            print(f"[WHISPER] error: {e}", flush=True)

    # ------------------------------------------------------------------ #
    #  Sentence accumulator                                               #
    # ------------------------------------------------------------------ #

    def _accumulate(self, timestamp: str, text: str, lang: str):
        with self._buf_lock:
            if not self._buf_timestamp:
                self._buf_timestamp = timestamp
            self._buf_text    = (self._buf_text + " " + text).strip()
            self._buf_lang    = lang
            self._buf_updated = time.time()

            word_count = len(self._buf_text.split())
            ends_sentence = self._buf_text[-1] in ".!?" if self._buf_text else False

            should_flush = (
                (ends_sentence and word_count >= MIN_FLUSH_WORDS) or
                word_count >= MAX_BUFFER_WORDS
            )
            if should_flush:
                self._flush_locked()

    def _flush_locked(self):
        """Emit buffered sentence. Must be called with _buf_lock held."""
        if self._buf_text:
            self._result_queue.put((self._buf_timestamp, self._buf_text, self._buf_lang))
            print(f"[FLUSH] '{self._buf_text[:80]}'", flush=True)
            self._buf_text      = ""
            self._buf_timestamp = ""
            self._buf_lang      = ""
            self._buf_updated   = 0.0

    def _check_timeout_flush(self):
        """Called from collect loop — flush if speaker paused long enough."""
        with self._buf_lock:
            if self._buf_text and time.time() - self._buf_updated >= FLUSH_TIMEOUT:
                self._flush_locked()

    # ------------------------------------------------------------------ #

    def _collect_loop(self):
        buffer         = []
        buffer_samples = 0

        while self._running:
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                if chunk is None or len(chunk) == 0:
                    continue
                buffer.append(chunk)
                buffer_samples += len(chunk)

                if buffer_samples >= CHUNK_SAMPLES:
                    audio          = np.concatenate(buffer)
                    buffer         = []
                    buffer_samples = 0

                    if np.max(np.abs(audio)) >= SILENCE_THRESHOLD:
                        timestamp = self._get_timestamp()
                        language  = self._get_language() if self._get_language else None
                        self._transcribe_executor.submit(
                            self._transcribe, audio, timestamp, language
                        )

            except queue.Empty:
                self._check_timeout_flush()

        # Flush remaining audio
        if buffer:
            audio = np.concatenate(buffer)
            if np.max(np.abs(audio)) >= SILENCE_THRESHOLD:
                timestamp = self._get_timestamp()
                language  = self._get_language() if self._get_language else None
                self._transcribe_executor.submit(
                    self._transcribe, audio, timestamp, language
                ).result()

        # Final flush of any buffered sentence
        with self._buf_lock:
            self._flush_locked()

        self._transcribe_executor.shutdown(wait=False)
