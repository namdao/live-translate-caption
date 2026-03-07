import queue
import threading
import numpy as np
import sounddevice as sd
import soundfile as sf
from datetime import datetime
from pathlib import Path


class MicrophoneNotFoundError(Exception):
    pass


class Recorder:
    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024

    def __init__(self, audio_queue: queue.Queue = None):
        self._audio_queue = audio_queue or queue.Queue()
        self._chunks = []
        self._recording = False
        self._paused = False
        self._stream = None
        self._lock = threading.Lock()

    def _callback(self, indata, frames, time, status):
        if self._recording and not self._paused:
            chunk = indata.copy().flatten()
            self._chunks.append(chunk)
            self._audio_queue.put(chunk)

    def start(self):
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            if not input_devices:
                raise MicrophoneNotFoundError("No microphone found")
        except Exception as e:
            if isinstance(e, MicrophoneNotFoundError):
                raise
            raise MicrophoneNotFoundError(f"Failed to query audio devices: {e}")

        with self._lock:
            self._chunks = []
            self._recording = True
            self._paused = False

        try:
            self._stream = sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                blocksize=self.CHUNK_SIZE,
                dtype='float32',
                callback=self._callback,
            )
            self._stream.start()
        except sd.PortAudioError as e:
            self._recording = False
            raise MicrophoneNotFoundError(f"Could not open microphone: {e}")

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def stop(self) -> str:
        with self._lock:
            self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._chunks:
            return None

        audio_data = np.concatenate(self._chunks)
        max_amp = float(np.max(np.abs(audio_data)))
        if max_amp < 0.001:
            raise MicrophoneNotFoundError(
                "Microphone captured silence. Check System Settings → Privacy & Security → Microphone "
                "and ensure Terminal (or your Python app) has access."
            )

        save_path = self._get_save_path()
        save_path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(save_path), audio_data, self.SAMPLE_RATE)
        self._chunks = []
        return str(save_path)

    def _get_save_path(self) -> Path:
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return Path.home() / "Recordings" / f"{timestamp}.wav"

    @property
    def audio_queue(self) -> queue.Queue:
        return self._audio_queue
