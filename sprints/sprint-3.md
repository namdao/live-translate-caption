PROJECT: Realtime Recording App — Sprint 3
CONTEXT: Sprints 1 & 2 complete. Core pipeline works end-to-end.
GOAL: Add waveform visualization, microphone selector, improve UX

TASK 1 — src/ui/waveform_widget.py:
- Create a PyQt6 custom widget using QPainter (no matplotlib dependency)
- Display real-time audio amplitude as a scrolling waveform
- Widget size: full width × 80px height
- Background: #0d0d1a, waveform color: #e94560
- Update 20 times per second (50ms interval via QTimer)
- Keep last 200 amplitude samples in a circular buffer
- Draw as connected line, centered vertically
- If not recording: show flat line at center

TASK 2 — src/ui/level_meter.py:
- Simple VU meter widget (vertical bar, 200px tall × 20px wide)
- Green (#00ff88) for 0-60%, Yellow (#ffcc00) for 60-80%, Red (#ff4444) for 80-100%
- Smooth decay animation (level drops slowly after peak)
- Update from same audio queue as waveform

TASK 3 — src/audio/device_manager.py:
- list_input_devices() → list of {id, name, channels, sample_rate}
- get_default_device() → device dict
- validate_device(device_id) → bool (check device actually works)
- Use sounddevice.query_devices()

TASK 4 — Update src/ui/main_window.py:
- Add to LEFT SIDEBAR (new panel, 220px wide):
  Section "🎤 Input Device":
    QComboBox listing all microphones by name
    Refresh button (🔄) to re-scan devices
  Section "⚙️ Settings":
    Model size: [tiny | base | small] radio buttons
    "Download model" progress bar (hidden by default)
  Section "📁 Output":
    "Save folder:" label + folder path display
    [Browse] button to change save directory
- Add waveform_widget between top bar and transcript panels
- Add level_meter to the right of Stop button
- When device changes: stop current recording if active, reinitialize recorder

TASK 5 — Improve Pause/Resume behavior:
- Pause: stop recording audio but keep timer frozen, keep transcript visible
- Resume: continue recording, timer continues from where it stopped
- Visual: Pause button changes text to "▶ Resume" when paused
- Status indicator: red dot = recording, yellow dot = paused, grey = stopped

TASK 6 — Keyboard shortcuts:
- Space: toggle Record/Pause (only when app window focused)
- Ctrl+S: manual save current transcript as .txt
- Esc: Stop recording
- Use QShortcut for all shortcuts
- Show shortcuts in button tooltips

TESTING CHECKLIST:
[ ] Waveform animates smoothly when speaking
[ ] Waveform is flat when not recording
[ ] Level meter changes color based on volume
[ ] Device dropdown lists all available microphones
[ ] Switching device while recording: handled gracefully (stops + restarts)
[ ] Space toggles record/pause correctly
[ ] Esc stops recording
[ ] Ctrl+S saves transcript file
