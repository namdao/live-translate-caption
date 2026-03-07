from pathlib import Path
from datetime import datetime
from typing import Union
import numpy as np
import soundfile as sf


def ensure_directory(path: Union[str, Path]) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def get_save_path(extension: str) -> Path:
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    recordings_dir = Path.home() / "Recordings"
    ensure_directory(recordings_dir)
    ext = extension.lstrip(".")
    return recordings_dir / f"{timestamp}.{ext}"


def save_wav(audio_data: np.ndarray, sample_rate: int, filepath: Union[str, Path]) -> Path:
    filepath = Path(filepath)
    ensure_directory(filepath.parent)
    sf.write(str(filepath), audio_data, sample_rate)
    return filepath


def save_txt(text: str, filepath: Union[str, Path]) -> Path:
    filepath = Path(filepath)
    ensure_directory(filepath.parent)
    filepath.write_text(text, encoding="utf-8")
    return filepath
