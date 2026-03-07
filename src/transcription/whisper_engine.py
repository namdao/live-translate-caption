import time
from typing import Optional

import numpy as np
import torch
import whisper

# turbo = large-v3 distilled, ~8x faster, same accuracy
MODEL_SIZE = "turbo"

_HALLUCINATION_PHRASES = {
    "thank you", "thanks", "thank you so much", "thanks for watching",
    "please subscribe", "bye", "bye bye", "you", ".", "",
}


class TranscriptionError(Exception):
    pass


class WhisperEngine:
    def __init__(self):
        device = "cpu"  # MPS lacks sparse tensor ops required by Whisper
        print(f"Loading Whisper '{MODEL_SIZE}' on {device}...", flush=True)
        try:
            self._model = whisper.load_model(MODEL_SIZE, device=device)
            self._device = device
            print("Whisper model loaded.", flush=True)
        except Exception as e:
            raise TranscriptionError(f"Failed to load Whisper model: {e}")

    def transcribe_chunk(self, audio_np: np.ndarray, language: Optional[str] = None) -> tuple:
        """Returns (text, language, confidence)."""
        try:
            # openai-whisper expects float32 numpy at 16kHz
            audio = audio_np.astype(np.float32)

            kwargs = dict(
                fp16=False,                       # MPS doesn't support fp16 reliably
                no_speech_threshold=0.8,
                condition_on_previous_text=False,
                compression_ratio_threshold=1.35,
                logprob_threshold=-1.0,
            )
            if language and language != "auto":
                kwargs["language"] = language

            t0 = time.time()
            result = self._model.transcribe(audio, **kwargs)
            elapsed = time.time() - t0

            text = (result.get("text") or "").strip()
            lang = result.get("language") or "unknown"

            print(f"[WHISPER] {elapsed:.2f}s → '{text[:60] if text else '(empty)'}'", flush=True)

            if text.lower().strip(".,!? ") in _HALLUCINATION_PHRASES:
                return "", lang, 0.0

            return text, lang, 1.0

        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}")
