# RealTime Recorder — Project Context

## Goal
Desktop app: ghi âm realtime → transcription → translation → export file
Supports three transcription backends: MLX Whisper (GPU), OpenAI Whisper (CPU), macOS Live Captions

## Tech stack
- Python 3.9, PyQt6==6.4.2 (6.6.1 broken on macOS arm64)
- sounddevice, soundfile, numpy
- mlx-whisper (Apple Silicon GPU) + openai-whisper (CPU fallback)
- deep-translator (GoogleTranslator)
- python-docx, pydub (export)

## Architecture
```
[Microphone] → Recorder → audio_queue → ChunkProcessor → WhisperEngine ┐
                                                                         ├→ result_queue
[Live Captions window] → LiveCaptionsReader ──────────────────────────────┘
                                                                         ↓
                                                              _Bridge (Qt signal)
                                                                         ↓
                                                    Translator (GoogleTranslator)
                                                                         ↓
                                                              UI (MainWindow)
```

## Thread model
- Main thread: UI only (PyQt6)
- Thread 2: audio recording (sounddevice callback)
- Thread 3: ChunkProcessor collect loop
- Thread 4: ThreadPoolExecutor — Whisper inference
- Thread 5: ThreadPoolExecutor — Google Translate (max 2 workers)
- Thread 6: LiveCaptionsReader poll loop (when Live Captions backend active)
- Communication: queue.Queue() + pyqtSignal (_Bridge) for translation

## Key data formats
- Segment = { timestamp: "00:01:23", text: str, translation: str }
- Audio chunk = numpy float32, 16000Hz, mono
- recorder.stop() returns (stem: str, audio_data: np.ndarray, sample_rate: int) or None
  ⚠️ Audio is kept in memory — NOT written to disk until user clicks Export

## Transcription backends
- MLX (default): mlx-whisper, Apple Silicon GPU, ~0.2–0.5s per chunk
  Repo names: tiny→whisper-tiny, base→whisper-base-mlx, small→whisper-small-mlx, turbo→whisper-turbo
- OpenAI: openai-whisper, CPU only (MPS breaks on sparse tensor ops), ~4–5s per chunk
- Live Captions: reads macOS system captions via AppleScript Accessibility API
  Path: static text → UI element 1 → scroll area 1 → group 1 → window 1
  No model loading needed; default backend on startup

## Sentence accumulator (ChunkProcessor + LiveCaptionsReader)
- Buffer short fragments until: ends with .!? AND ≥6 words, OR ≥40 words, OR 2.5s pause
- Prevents displaying partial words/fragments in UI

## Live Captions dedup (word-anchor algorithm)
- _anchor = last 6 normalized words seen in previous poll
- Each poll: find anchor in new window (longest match first, shorter on fail)
- Fallback: find last anchor word if sequence not found (handles word insertions)
- Normalization: lowercase + strip all punctuation (robust against LC corrections)

## Conventions
- NEVER update UI directly from background threads → use Qt signals
- Translation result: emitted via _Bridge.translation_ready signal (not polled)
- All errors: catch + show in status bar, never crash app
- Audio stored in memory after recording; written to disk only on Export

## Sprint status
- [x] Sprint 1: Recording + basic UI
- [x] Sprint 2: Whisper + translation pipeline
- [x] Sprint 3: Waveform + mic selector + UX + keyboard shortcuts
- [x] Sprint 4: Export (WAV, TXT, DOCX, SRT, MP3) — in-memory, re-exportable
- [x] Sprint 5: Multi-backend (MLX/OpenAI/LiveCaptions), latency reduction, sentence merging

## Do NOT change
- recorder.py public interface: start() / stop() / pause() / resume()
- stop() return format: (stem, audio_data, sample_rate) tuple or None
- Segment data format: { timestamp, text, translation }
- PyQt6 version: 6.4.2 (do not upgrade)
