PROJECT: Realtime Recording App — Sprint 2
STATUS: ✅ COMPLETE
CONTEXT: Sprint 1 complete. recorder.py, file_manager.py, main_window.py exist and work.
GOAL: Add realtime transcription and translation in background threads

TASK 1 — src/transcription/whisper_engine.py: ✅
- Use `openai-whisper` library (NOT faster-whisper — no binary wheel for Python 3.9/arm64)
  ⚠️ CHANGED from original: faster-whisper replaced by openai-whisper
- Default model: "turbo" (large-v3 distilled, ~8x faster than large-v3)
  ⚠️ CHANGED from original: "base" → "turbo"
- Force device="cpu" (MPS rejected: sparse tensor ops not supported on sparseMPS backend)
- fp16=False for CPU inference
- Hallucination filtering:
    no_speech_threshold=0.8
    condition_on_previous_text=False
    compression_ratio_threshold=1.35
  Phrase blocklist: "thank you", "thanks", "bye", etc.
- expose: transcribe_chunk(audio_np, language=None) → (text, language, confidence)
- If model loading fails: raise TranscriptionError with user-friendly message
- Supports: vi, en, ja, ko, zh, fr, es, de + auto-detect

TASK 2 — src/transcription/chunk_processor.py: ✅
- Accumulate audio chunks from recorder's queue
- Every 2 seconds of audio: send to whisper_engine (ThreadPoolExecutor)
  ⚠️ CHANGED from original: 4s → 2s for lower latency
- Silence detection: skip if RMS amplitude < 0.02
  ⚠️ CHANGED from original: 0.01 → 0.02 to reduce false positives
- Two-thread design: collector loop + ThreadPoolExecutor for inference
  (collector never blocks on Whisper)
- Output: put (timestamp, text, language) into result_queue
- timestamp format: "00:01:23"
- get_language callable injected from UI (not hardcoded)

TASK 3 — src/translation/translator.py: ✅
- Use `deep-translator` (GoogleTranslator)
- expose: translate_async(text, src, tgt, callback) — callback called from thread pool
- ThreadPoolExecutor(max_workers=2) for non-blocking translation
- OrderedDict LRU cache, maxsize=50
- If translation fails: return original text + "(translation unavailable)"
- Supported targets: vi, en, ja, ko, zh-CN, fr, es, de

TASK 4 — Update src/ui/main_window.py: ✅
- Two panels side by side:
  LEFT (55%): "Transcript" + scrollable QTextEdit
  RIGHT (45%): "Translation" + scrollable QTextEdit
- Language selector row:
  "Source:" [Auto/Vietnamese/English/Japanese/Korean/Chinese]
  "→ Translate to:" [Vietnamese/English/Japanese/Korean/Chinese]
- Each transcript chunk appended with "[HH:MM:SS] text" prefix
- Auto-scroll both panels to bottom on new text
- "⏳ Transcribing..." spinner label
- Panels cleared when a new recording starts

TASK 5 — Wire up threads in main.py: ✅
- On Record: start recorder → start chunk_processor
- result_queue polled every 200ms via QTimer (was 500ms — reduced for latency)
  ⚠️ CHANGED from original: 500ms → 200ms
- translation_queue polled in same timer loop
- On Stop: chunk_processor.stop() called before recorder.stop()
- All UI updates via Qt signals (never from background threads)

requirements.txt additions:
openai-whisper>=20240930    ← replaces faster-whisper
deep-translator==1.11.4

TESTING CHECKLIST:
[x] Record 10 seconds of speech → transcript appears in left panel
[x] Translation appears in right panel within 3 seconds of transcript
[x] Timestamp prefix correct on each chunk
[x] Switching target language mid-session works
[x] App UI stays responsive during transcription
[x] Auto-detect language works for English and Vietnamese
[x] Hallucination ("thank you" on silence) filtered out
