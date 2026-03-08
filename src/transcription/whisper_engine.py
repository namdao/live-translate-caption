import time
from typing import Optional

import numpy as np

DEFAULT_MODEL_SIZE = "turbo"

_HALLUCINATION_PHRASES = {
    "thank you", "thanks", "thank you so much", "thanks for watching",
    "please subscribe", "bye", "bye bye", "you", ".", "",
}

_TRANSCRIBE_KWARGS = dict(
    no_speech_threshold=0.8,
    condition_on_previous_text=False,
    compression_ratio_threshold=1.35,
    logprob_threshold=-1.0,
)


class TranscriptionError(Exception):
    pass


def _filter(text: str, lang: str) -> tuple:
    """Strip hallucinations. Returns (text, lang, confidence)."""
    if text.lower().strip(".,!? ") in _HALLUCINATION_PHRASES:
        return "", lang, 0.0
    return text, lang, 1.0


# ── MLX Whisper (Apple Silicon GPU) ──────────────────────────────────────────

class MLXWhisperEngine:
    _HF_REPO = "mlx-community/whisper-{size}"

    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE):
        try:
            import mlx_whisper
            self._mlx_whisper = mlx_whisper
        except ImportError:
            raise TranscriptionError(
                "mlx-whisper is not installed. Run: pip install mlx-whisper"
            )

        self._repo = self._HF_REPO.format(size=model_size)
        print(f"[MLX] Loading '{model_size}' from {self._repo} ...", flush=True)
        try:
            dummy = np.zeros(16000, dtype=np.float32)
            self._mlx_whisper.transcribe(dummy, path_or_hf_repo=self._repo)
            print("[MLX] Model ready (Apple Silicon GPU).", flush=True)
        except Exception as e:
            raise TranscriptionError(f"Failed to load mlx-whisper model: {e}")

    def transcribe_chunk(self, audio_np: np.ndarray, language: Optional[str] = None) -> tuple:
        try:
            kwargs = dict(**_TRANSCRIBE_KWARGS, path_or_hf_repo=self._repo)
            if language and language != "auto":
                kwargs["language"] = language

            t0 = time.time()
            result = self._mlx_whisper.transcribe(audio_np.astype(np.float32), **kwargs)
            elapsed = time.time() - t0

            text = (result.get("text") or "").strip()
            lang = result.get("language") or "unknown"
            print(f"[MLX] {elapsed:.2f}s → '{text[:60] if text else '(empty)'}'", flush=True)
            return _filter(text, lang)
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}")


# ── OpenAI Whisper (CPU) ──────────────────────────────────────────────────────

class OpenAIWhisperEngine:
    def __init__(self, model_size: str = DEFAULT_MODEL_SIZE):
        try:
            import whisper
            self._whisper = whisper
        except ImportError:
            raise TranscriptionError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )

        print(f"[OpenAI] Loading '{model_size}' on CPU ...", flush=True)
        try:
            self._model = self._whisper.load_model(model_size, device="cpu")
            print("[OpenAI] Model ready (CPU).", flush=True)
        except Exception as e:
            raise TranscriptionError(f"Failed to load openai-whisper model: {e}")

    def transcribe_chunk(self, audio_np: np.ndarray, language: Optional[str] = None) -> tuple:
        try:
            kwargs = dict(**_TRANSCRIBE_KWARGS, fp16=False)
            if language and language != "auto":
                kwargs["language"] = language

            t0 = time.time()
            result = self._model.transcribe(audio_np.astype(np.float32), **kwargs)
            elapsed = time.time() - t0

            text = (result.get("text") or "").strip()
            lang = result.get("language") or "unknown"
            print(f"[OpenAI] {elapsed:.2f}s → '{text[:60] if text else '(empty)'}'", flush=True)
            return _filter(text, lang)
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}")


# ── Factory ───────────────────────────────────────────────────────────────────

def WhisperEngine(model_size: str = DEFAULT_MODEL_SIZE, backend: str = "mlx"):
    """Return the appropriate engine instance for the given backend."""
    if backend == "mlx":
        return MLXWhisperEngine(model_size)
    elif backend == "openai":
        return OpenAIWhisperEngine(model_size)
    else:
        raise TranscriptionError(f"Unknown backend: '{backend}'. Choose 'mlx' or 'openai'.")
