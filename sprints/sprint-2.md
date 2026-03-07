PROJECT: Realtime Recording App — Sprint 2
CONTEXT: Sprint 1 is complete. recorder.py, file_manager.py, main_window.py exist and work.
GOAL: Add realtime transcription and translation in background threads

TASK 1 — src/transcription/whisper_engine.py:
- Use `faster-whisper` library
- Load model "base" by default (multilingual)
- expose: transcribe_chunk(audio_np_array) → returns (text, language, confidence)
- Audio input: numpy float32 array at 16000 Hz
- Run in a daemon thread, never block UI thread
- First run: download model automatically, print download progress to console
- Support languages: vi, en, ja, ko, zh, fr, es, de + auto-detect
- If model loading fails: raise TranscriptionError with user-friendly message

TASK 2 — src/transcription/chunk_processor.py:
- Accumulate audio chunks from recorder's queue
- Every 4 seconds of audio: send accumulated chunk to whisper_engine
- Use threading.Thread(daemon=True) for processing loop
- Output: put (timestamp, text, language) tuples into a result_queue
- timestamp format: "00:01:23"
- Handle: empty audio chunks, silence detection (skip if amplitude < 0.01)

TASK 3 — src/translation/translator.py:
- Use `deep-translator` (GoogleTranslator)
- expose: translate(text, source_lang, target_lang) → str
- source_lang: "auto" by default
- target_lang: default "vi" (Vietnamese)
- Supported targets: vi, en, ja, ko, zh-CN, fr, es, de
- Run translate() in a ThreadPoolExecutor to avoid blocking
- If translation fails: return original text + "(translation unavailable)"
- Cache last 50 translations to avoid duplicate API calls

TASK 4 — Update src/ui/main_window.py:
- Split MIDDLE section into two panels side by side:
  LEFT panel (55%): "Transcript" label + scrollable text area
  RIGHT panel (45%): "Translation" label + scrollable text area
- Add language selector row above panels:
  "Source:" [dropdown: Auto/Vietnamese/English/Japanese/Korean/Chinese]
  "→ Translate to:" [dropdown: Vietnamese/English/Japanese/Korean/Chinese]
- Each new transcript chunk: append to left panel with timestamp prefix
  Format: "[00:01:23] text here..."
- Each translation: append to right panel aligned with transcript
- Auto-scroll both panels to bottom when new text arrives
- Add loading spinner label "⏳ Transcribing..." that shows/hides appropriately

TASK 5 — Wire up threads in main.py:
- On Record: start recorder → start chunk_processor → start translation consumer
- Use a result_queue that chunk_processor fills
- Main window polls result_queue every 500ms using QTimer
- When result available: update both text panels via Qt signals (thread-safe)
- On Stop: signal all threads to finish, wait max 3 seconds, then cleanup

ADD to requirements.txt:
faster-whisper==1.0.0
deep-translator==1.11.4
ctranslate2==4.0.0

TESTING CHECKLIST:
[ ] Record 10 seconds of speech → transcript appears in left panel
[ ] Translation appears in right panel within 3 seconds of transcript
[ ] Timestamp prefix correct on each chunk
[ ] Switching target language mid-session works
[ ] App UI stays responsive (not frozen) during transcription
[ ] Auto-detect language works for both English and Vietnamese
