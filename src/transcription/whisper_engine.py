import numpy as np
import mlx_whisper

MODEL_REPO = "mlx-community/whisper-large-v3-mlx"

# Phrases Whisper commonly hallucinates on silence/noise
_HALLUCINATION_PHRASES = {
    "thank you", "thanks", "thank you so much", "thanks for watching",
    "please subscribe", "bye", "bye bye", "you", ".",  "", "♪", "♫",
}


class TranscriptionError(Exception):
    pass


class WhisperEngine:
    def __init__(self):
        print("Loading Whisper model (MLX, Apple Silicon)...", flush=True)
        try:
            mlx_whisper.transcribe(
                np.zeros(3200, dtype=np.float32),
                path_or_hf_repo=MODEL_REPO,
            )
            print("Whisper model loaded.", flush=True)
        except Exception as e:
            raise TranscriptionError(f"Failed to load Whisper model: {e}")

    def transcribe_chunk(self, audio_np: np.ndarray, language: str = None) -> tuple:
        """
        Returns (text, language, confidence).
        Pass language='en' (or 'vi', 'ja', etc.) to lock detection and avoid wrong-language outputs.
        Pass language=None for auto-detect.
        """
        try:
            kwargs = dict(
                path_or_hf_repo=MODEL_REPO,
                word_timestamps=False,
                no_speech_threshold=0.8,          # reject chunks that are likely silence/noise
                condition_on_previous_text=False,  # prevent hallucination cascades
                compression_ratio_threshold=1.35,  # reject repetitive/garbage output
            )
            if language and language != "auto":
                kwargs["language"] = language

            result = mlx_whisper.transcribe(audio_np.astype(np.float32), **kwargs)
            text = result.get("text", "").strip()
            lang = result.get("language", "unknown")

            # Drop known hallucination phrases
            if text.lower().strip(".,!? ") in _HALLUCINATION_PHRASES:
                return "", lang, 0.0

            return text, lang, 1.0
        except Exception as e:
            raise TranscriptionError(f"Transcription failed: {e}")
