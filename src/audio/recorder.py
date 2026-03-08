import queue
import threading
import numpy as np
import sounddevice as sd
from datetime import datetime


class MicrophoneNotFoundError(Exception):
    pass


class Recorder:
    SAMPLE_RATE = 16000
    CHANNELS = 1
    CHUNK_SIZE = 1024

    def __init__(self, audio_queue: queue.Queue = None):
        self._audio_queue = audio_queue or queue.Queue()
        self._viz_queue: queue.Queue = queue.Queue(maxsize=100)
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
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            try:
                self._viz_queue.put_nowait(rms)
            except queue.Full:
                pass  # drop oldest — UI is behind, not critical

    def start(self, device_index: int = None):
        """Start recording. device_index=None uses system default."""
        try:
            devices = sd.query_devices()
            input_devices = [d for d in devices if d['max_input_channels'] > 0]
            if not input_devices:
                raise MicrophoneNotFoundError("No input device found")
            if device_index is not None:
                d = devices[device_index]
                if d['max_input_channels'] < 1:
                    raise MicrophoneNotFoundError(f"Device '{d['name']}' has no input channels")
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
                device=device_index,
                callback=self._callback,
            )
            self._stream.start()
        except sd.PortAudioError as e:
            self._recording = False
            raise MicrophoneNotFoundError(f"Could not open device: {e}")

    def pause(self):
        with self._lock:
            self._paused = True

    def resume(self):
        with self._lock:
            self._paused = False

    def stop(self):
        """Stop recording. Returns (stem, audio_data, sample_rate) or None if no audio."""
        with self._lock:
            self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        if not self._chunks:
            return None

        audio_data = np.concatenate(self._chunks)
        self._chunks = []

        max_amp = float(np.max(np.abs(audio_data)))
        if max_amp < 0.001:
            raise MicrophoneNotFoundError(
                "Microphone captured silence. Check System Settings → Privacy & Security → Microphone "
                "and ensure Terminal (or your Python app) has access."
            )

        # Normalize to -3 dBFS (peak = 0.707) so the file is always audible
        audio_data = audio_data * (0.707 / max_amp)

        stem = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        return stem, audio_data, self.SAMPLE_RATE

    @property
    def audio_queue(self) -> queue.Queue:
        return self._audio_queue

    @property
    def viz_queue(self) -> queue.Queue:
        return self._viz_queue
