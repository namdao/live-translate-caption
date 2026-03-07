# RealTime Recorder — Project Context

## Goal
Desktop app: ghi âm realtime → transcription (Whisper) → translation → export file

## Tech stack
- Python 3.10+, PyQt6, faster-whisper, deep-translator, sounddevice

## Architecture
Recorder → ChunkProcessor → WhisperEngine → Translator → UI (via Qt signals)

## Thread model
- Main thread: UI only (PyQt6)
- Thread 2: audio recording (sounddevice callback)
- Thread 3: transcription queue consumer
- Thread 4: translation queue consumer
- Communication: queue.Queue() between all threads

## Key data format
Segment = { timestamp: "00:01:23", text: str, translation: str }
Audio chunk = numpy float32, 16000Hz, mono

## Conventions
- NEVER update UI directly from background threads → use Qt signals
- All errors: catch + show in status bar, never crash app
- Auto-save path: ~/Recordings/YYYY-MM-DD_HH-MM-SS

## Sprint status
- [x] Sprint 1: Recording + save WAV + basic UI
- [ ] Sprint 2: Whisper + translation (CURRENT)
- [ ] Sprint 3: Waveform + mic selector + UX
- [ ] Sprint 4: Export DOCX/SRT/MP3

## Do NOT change
- recorder.py public interface: start() / stop() / pause() / resume()
- Segment data format (other modules depend on it)
```

---
