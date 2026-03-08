PROJECT: Realtime Recording App — Sprint 5
STATUS: ✅ COMPLETE
CONTEXT: Sprints 1-4 complete. App exports, transcribes, and translates.
GOAL: Multi-backend transcription, Live Captions integration, latency reduction, export redesign

─────────────────────────────────────────────────────────────────
TASK 1 — Export redesign: audio kept in memory, not auto-saved
─────────────────────────────────────────────────────────────────
src/audio/recorder.py:
  - stop() no longer writes to disk
  - Returns (stem, audio_data, sample_rate) tuple or None
  - stem = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
  - Audio normalized to -3 dBFS in memory before returning

src/storage/file_manager.py:
  - export_wav(audio_data, sample_rate, filepath) — writes WAV from numpy array
  - export_transcript_txt(segments, filepath) — transcript only
  - export_translation_txt(segments, filepath) — translation only
  - export_mp3_from_data(audio_data, sample_rate, filepath) — converts from memory, no temp file

src/ui/export_dialog.py:
  - Accepts (stem, audio_data, sample_rate) instead of wav file path
  - Checkboxes: WAV ✓ | Transcript ✓ | Translation ✓ | DOCX | SRT | MP3
  - WAV and MP3 write from in-memory numpy array (re-exportable)
  - Deleting exported files and clicking Export again re-exports all from memory
  - No same-file copy error (no file is written on stop)

src/ui/main_window.py:
  - set_last_recording(stem, audio_data, sample_rate) replaces set_last_wav()
  - Transcript + translation panels cleared on new recording start
  - Export button enabled after stop, not auto-opened

main.py:
  - Removed auto-open export dialog on stop
  - Removed save_folder_changed → recorder.save_dir wiring (recorder has no save_dir)
  - Status bar shows "click Export to save" hint after stop

─────────────────────────────────────────────────────────────────
TASK 2 — Latency reduction
─────────────────────────────────────────────────────────────────
src/transcription/chunk_processor.py:
  - CHUNK_SECONDS: 2 → 1 (halves audio collection wait)
  - Sentence accumulator added:
      MIN_FLUSH_WORDS = 6   → flush on sentence-end only if enough words
      MAX_BUFFER_WORDS = 40 → force flush
      FLUSH_TIMEOUT = 2.5s  → flush on speaker pause
  - Short fragments (< 6 words) buffered and merged with next chunk
  - _check_timeout_flush() called from collect loop on queue.Empty

main.py:
  - _Bridge(QObject) with pyqtSignal for translation:
      translation callback emits signal directly → 0ms display wait
      (was: put into translation_queue → polled every 200ms)
  - Poll timer: 200ms → 100ms for transcript queue
  - Translation no longer uses a queue — fires instantly via Qt signal

─────────────────────────────────────────────────────────────────
TASK 3 — Multi-backend Whisper engine
─────────────────────────────────────────────────────────────────
src/transcription/whisper_engine.py:
  - Split into two classes + factory function:
      MLXWhisperEngine  — Apple Silicon GPU via mlx-whisper
      OpenAIWhisperEngine — CPU via openai-whisper (device="cpu")
      WhisperEngine(model_size, backend) — factory, returns correct class
  - MLX HuggingFace repo mapping (names differ per model size):
      tiny  → mlx-community/whisper-tiny
      base  → mlx-community/whisper-base-mlx
      small → mlx-community/whisper-small-mlx
      turbo → mlx-community/whisper-turbo
  - Both engines share same hallucination filtering + _TRANSCRIBE_KWARGS

src/ui/main_window.py:
  - New "Backend" section in sidebar:
      ○ MLX  (Apple GPU)
      ○ OpenAI  (CPU)
      ● Live Captions  (System)   ← default on startup
  - Model section title updates: "MLX Model" / "OpenAI Model"
  - Model section hidden when Live Captions selected (no model needed)

main.py:
  - load_engine() skips Whisper loading when backend == "live_captions"
  - on_backend_changed() handler reloads engine on switch
  - Startup message: "Live Captions ready" (not "Loading Whisper model...")

requirements.txt:
  mlx-whisper>=0.4.0
  openai-whisper>=20240930   (both kept)

─────────────────────────────────────────────────────────────────
TASK 4 — macOS Live Captions integration
─────────────────────────────────────────────────────────────────
src/transcription/live_captions_reader.py (NEW):
  Reads real-time captions from macOS Live Captions window via AppleScript.

  Requirements:
    - macOS Ventura 13.0+
    - System Settings → Accessibility → Live Captions → ON
    - App granted Accessibility permission

  AppleScript path (discovered via diagnostic):
    value of every static text of UI element 1
      of scroll area 1 of group 1 of window 1
    (NOT "entire contents" — that fails silently; NOT using "result" var — reserved word)

  Dedup algorithm — word-anchor with normalization:
    - _anchor: last 6 normalized words from previous window text
    - Each poll: search for anchor in new window (longest match first, try shorter on fail)
    - Everything after anchor = genuinely new words
    - Normalization: lowercase + strip all punctuation → robust against corrections
    - Fallback: if anchor sequence not found, find last anchor word (handles insertions)
    - "missing value" AppleScript artifacts filtered in _clean()

  Sentence accumulator (same as ChunkProcessor):
    MIN_FLUSH_WORDS = 6, MAX_BUFFER_WORDS = 40, FLUSH_TIMEOUT = 2.0s

  Integration:
    - Same result_queue as Whisper → same translation pipeline
    - Recorder still runs (waveform viz + WAV capture for export)
    - Polling interval: 350ms

TESTING CHECKLIST:
[x] Stop → no file written to disk; status shows "click Export to save"
[x] Export → WAV + transcript.txt + translation.txt written to chosen folder
[x] Delete exported files → Export again → all files re-exported from memory
[x] Transcript + translation panels cleared on new recording
[x] Translation displays immediately when API returns (no poll delay)
[x] Short speech fragments merged into complete sentences before display
[x] MLX backend loads correct HuggingFace repo per model size
[x] Live Captions selected by default on startup; model section hidden
[x] Live Captions text appears in UI without duplicates
[x] Switching backend reloads engine; switching to Live Captions is instant
