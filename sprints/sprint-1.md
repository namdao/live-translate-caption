PROJECT: Realtime Recording App — Sprint 1
GOAL: Working audio recorder that saves WAV files and displays live text

Create the following project structure first:
realtime-recorder/
├── main.py
├── requirements.txt
├── src/
│   ├── audio/recorder.py
│   ├── ui/main_window.py
│   └── storage/file_manager.py

TASK 1 — src/audio/recorder.py:
- Use `sounddevice` to record audio from default microphone
- Record in chunks of 1024 frames at 16000 Hz, mono channel
- Use a queue.Queue() to pass audio chunks to other threads
- Expose: start(), stop(), pause(), resume() methods
- On stop: merge all chunks and save as WAV using soundfile
- File naming: ~/Recordings/YYYY-MM-DD_HH-MM-SS.wav
- Auto-create ~/Recordings/ if not exists
- Add error handling: if no microphone found, raise MicrophoneNotFoundError

TASK 2 — src/storage/file_manager.py:
- save_wav(audio_data, sample_rate, filepath) → saves WAV
- save_txt(text, filepath) → saves transcript as .txt
- get_save_path(extension) → returns auto-named path in ~/Recordings/
- ensure_directory(path) → creates directory if not exists

TASK 3 — src/ui/main_window.py:
- Use PyQt6 (preferred) or tkinter
- Dark theme: background #1a1a2e, text #e0e0e0, accent #e94560
- Layout:
  TOP: App title "🎙 RealTime Recorder" + red dot status indicator
  MIDDLE: Large scrollable QTextEdit for displaying transcript text
  BOTTOM: [Record] [Pause] [Stop] buttons + timer label "00:00:00"
- Timer updates every second using QTimer
- Buttons disable/enable correctly based on state
  (e.g., Pause only active when recording)
- When Record clicked: start recorder, start timer
- When Stop clicked: stop recorder, save file, show "Saved: {path}" in status bar

TASK 4 — main.py:
- Entry point that launches the PyQt6 app
- Connects UI buttons to recorder methods via signals/slots

TASK 5 — requirements.txt:
sounddevice==0.4.6
soundfile==0.12.1
PyQt6==6.6.1
numpy==1.26.0

TESTING CHECKLIST (do not finish sprint until all pass):
[ ] App launches without error
[ ] Click Record → timer starts counting
[ ] Click Stop → WAV file appears in ~/Recordings/
[ ] WAV file is playable in any media player
[ ] Click Pause → timer freezes, click Resume → timer continues
[ ] If no mic: error message shown in UI, app does not crash
