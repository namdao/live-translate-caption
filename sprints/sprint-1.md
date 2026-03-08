PROJECT: Realtime Recording App — Sprint 1
STATUS: ✅ COMPLETE
GOAL: Working audio recorder that saves WAV files and displays live text

Project structure:
realtime-recorder/
├── main.py
├── requirements.txt
├── src/
│   ├── audio/recorder.py
│   ├── ui/main_window.py
│   └── storage/file_manager.py

TASK 1 — src/audio/recorder.py: ✅
- Use `sounddevice` to record audio from default microphone
- Record in chunks of 1024 frames at 16000 Hz, mono channel
- Use a queue.Queue() to pass audio chunks to other threads
- Expose: start(), stop(), pause(), resume() methods
- On stop: normalize audio to -3 dBFS (peak = 0.707), keep in memory
  ⚠️ CHANGED: stop() no longer saves to disk — returns (stem, audio_data, sample_rate)
  WAV is only written when user clicks Export
- Add error handling: if no microphone found, raise MicrophoneNotFoundError
- Bounded viz_queue (maxsize=100) for waveform/level meter data

TASK 2 — src/storage/file_manager.py: ✅
- export_wav(audio_data, sample_rate, filepath) → writes WAV (PCM_16) from numpy array
- save_txt(text, filepath) → saves raw text string (used by Ctrl+S quick-save)
- get_save_path(extension) → returns auto-named path
- ensure_directory(path) → creates directory if not exists

TASK 3 — src/ui/main_window.py: ✅
- PyQt6, dark theme: background #1a1a2e, text #e0e0e0, accent #e94560
- Layout:
  TOP: App title "🎙 RealTime Recorder" + status dot
  MIDDLE: Transcript + Translation panels
  BOTTOM: [Record] [Pause] [Stop] [Export] buttons + timer "00:00:00"
- Timer updates every second using QTimer
- Buttons disable/enable correctly based on state

TASK 4 — main.py: ✅
- Entry point that launches the PyQt6 app
- Connects UI buttons to recorder methods via signals/slots

requirements.txt:
sounddevice==0.4.6
soundfile==0.12.1
PyQt6==6.4.2          ← pinned to 6.4.2 (6.6.1 broken on macOS arm64 Python 3.9)
numpy==1.26.0

TESTING CHECKLIST:
[x] App launches without error
[x] Click Record → timer starts counting
[x] Click Stop → status bar shows recording name + duration
[x] Click Export → WAV file written to chosen folder
[x] WAV file is playable in any media player
[x] Click Pause → timer freezes, click Resume → timer continues
[x] If no mic: error message shown in UI, app does not crash
