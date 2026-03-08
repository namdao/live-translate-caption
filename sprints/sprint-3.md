PROJECT: Realtime Recording App — Sprint 3
STATUS: ✅ COMPLETE
CONTEXT: Sprints 1 & 2 complete. Core pipeline works end-to-end.
GOAL: Add waveform visualization, microphone selector, improve UX

TASK 1 — src/ui/waveform_widget.py: ✅
- PyQt6 custom widget using QPainter (no matplotlib)
- Full width × 80px height
- Background: #0d0d1a, waveform color: #e94560
- deque(maxlen=200) circular buffer of RMS floats
- Repaint timer (50ms) only runs when set_active(True) — stops when idle
- On set_active(False): buffer.clear() + extend([0.0]*200) for instant flat line
- Draws connected line, amplitude scaled by min(1.0, amp * 8), centered vertically

TASK 2 — src/ui/level_meter.py: ✅
- Vertical VU meter: 20px wide × 60px tall (fixed size)
- Green (#00ff88) < 0.6, Yellow (#ffcc00) < 0.8, Red (#ff4444) ≥ 0.8
- 50ms decay timer: level *= 0.80 per tick
- Fed from same recorder.viz_queue as waveform

TASK 3 — src/audio/device_manager.py: ✅
- list_input_devices() → list of {id, name, channels, sample_rate}
- get_default_device() → device dict
- validate_device(device_id) → bool
- Uses sounddevice.query_devices()
- Supports BlackHole 2ch virtual audio driver for system audio capture

TASK 4 — Update src/ui/main_window.py: ✅
Left sidebar (220px):
  "🎤 Input Device": QComboBox + 🔄 Refresh button
    blockSignals(True/False) around refresh to prevent spurious device-changed events
  "⚙️ Whisper Model": radio buttons [tiny | base | small | turbo]
    ⚠️ CHANGED: added "turbo" option, removed "large"
  "📁 Output": Save folder label + [Browse] button
    ⚠️ NOTE: output folder is only used for Export (no auto-save on stop)
- Waveform widget between top bar and transcript panels
- Level meter to the right of Stop button
- Device change: stops active recording, shows status message

TASK 5 — Pause/Resume behavior: ✅
- Pause: stop recording audio, freeze timer, keep transcript visible
- Resume: continue recording + timer
- Pause button text → "▶ Resume" when paused
- Status dot: red = recording, yellow = paused, grey = stopped

TASK 6 — Keyboard shortcuts: ✅
- Space: toggle Record/Pause
- Ctrl+S: quick-save current transcript as .txt
- Ctrl+E: open Export dialog
- Esc: Stop recording
- Implemented via QShortcut

TESTING CHECKLIST:
[x] Waveform animates smoothly when speaking
[x] Waveform is flat when not recording
[x] Level meter changes color based on volume
[x] Device dropdown lists all available microphones (including BlackHole)
[x] Switching device while recording: stops + shows message
[x] Space toggles record/pause correctly
[x] Esc stops recording
[x] Ctrl+S saves transcript file
[x] Ctrl+E opens export dialog
