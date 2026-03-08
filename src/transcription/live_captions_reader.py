"""
Read real-time text from the macOS Live Captions window via the Accessibility API.

Requirements:
  - macOS Ventura (13.0) or later
  - System Settings → Accessibility → Live Captions → ON
  - Terminal / this app granted Accessibility permission
"""

import queue
import subprocess
import threading
import time
from typing import List, Optional

# Sentence accumulator tuning
MIN_FLUSH_WORDS  = 6
MAX_BUFFER_WORDS = 40
FLUSH_TIMEOUT    = 2.0

# Anchor: how many words from the end of the window we track as our "cursor"
ANCHOR_SIZE = 6

_APPLESCRIPT = """
tell application "System Events"
    if not (exists process "Live Captions") then return ""
    tell process "Live Captions"
        try
            set texts to value of every static text of UI element 1 of scroll area 1 of group 1 of window 1
            set captionText to ""
            repeat with t in texts
                if t is not missing value and t is not "" then
                    set captionText to captionText & t & " "
                end if
            end repeat
            return captionText
        on error
            return ""
        end try
    end tell
end tell
"""


def _norm(word: str) -> str:
    """Normalize a word for comparison: lowercase + strip ALL punctuation."""
    return word.lower().strip(".,!?;:\"'-() ")


class LiveCaptionsReader:
    POLL_INTERVAL = 0.35

    def __init__(self, result_queue: queue.Queue, start_time: float):
        self._result_queue = result_queue
        self._start_time   = start_time
        self._running      = False
        self._thread: Optional[threading.Thread] = None

        self._prev_raw      = ""
        self._anchor: List[str] = []   # last N normalized words we've seen

        # Sentence accumulator
        self._buf_text      = ""
        self._buf_timestamp = ""
        self._buf_updated   = 0.0

    # ------------------------------------------------------------------ #
    #  Public                                                             #
    # ------------------------------------------------------------------ #

    def start(self):
        self._running       = True
        self._prev_raw      = ""
        self._anchor        = []
        self._buf_text      = ""
        self._buf_timestamp = ""
        self._buf_updated   = 0.0
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._buf_text:
            self._result_queue.put((self._buf_timestamp, self._buf_text.strip(), "auto"))
            self._buf_text = ""

    # ------------------------------------------------------------------ #
    #  Dedup: word-anchor with normalized comparison                      #
    # ------------------------------------------------------------------ #

    def _extract_new(self, current: str) -> str:
        """
        Find genuinely new words by locating our anchor (last N normalized
        words) in the current window text.  Everything after the anchor is new.
        Normalization (lowercase + strip punctuation) makes this robust
        against Live Captions adding/changing punctuation or spacing.
        """
        curr_words = current.split()

        # Build parallel arrays: original words + normalized (skip empty/punct-only)
        words = []     # (original_word, normalized_word)
        for w in curr_words:
            n = _norm(w)
            if n:  # skip bare punctuation like "." or ","
                words.append((w, n))

        curr_orig = [w for w, _ in words]
        curr_norm = [n for _, n in words]

        if not self._anchor:
            # First poll — everything is new
            self._anchor = curr_norm[-ANCHOR_SIZE:]
            return current

        # Search for anchor in current normalized words (longest match first)
        for alen in range(len(self._anchor), 1, -1):
            sub_anchor = self._anchor[-alen:]
            for i in range(len(curr_norm) - alen + 1):
                if curr_norm[i : i + alen] == sub_anchor:
                    new_start = i + alen
                    # Update anchor to end of current window
                    self._anchor = curr_norm[-ANCHOR_SIZE:]
                    if new_start < len(curr_orig):
                        return " ".join(curr_orig[new_start:])
                    return ""

        # Anchor sequence not found (Live Captions inserted/changed words).
        # Fallback: find the LAST occurrence of the last anchor word.
        # Everything after it is new.
        last_anchor = self._anchor[-1]
        last_pos = -1
        for i in range(len(curr_norm) - 1, -1, -1):
            if curr_norm[i] == last_anchor:
                last_pos = i
                break

        self._anchor = curr_norm[-ANCHOR_SIZE:]
        if last_pos >= 0 and last_pos + 1 < len(curr_orig):
            return " ".join(curr_orig[last_pos + 1 :])
        return ""

    # ------------------------------------------------------------------ #
    #  Sentence accumulator                                               #
    # ------------------------------------------------------------------ #

    def _accumulate(self, timestamp: str, text: str):
        # Skip if the new text is already inside the buffer
        if text and self._buf_text and text in self._buf_text:
            return

        if not self._buf_timestamp:
            self._buf_timestamp = timestamp
        self._buf_text    = (self._buf_text + " " + text).strip()
        self._buf_updated = time.time()

        word_count    = len(self._buf_text.split())
        ends_sentence = bool(self._buf_text) and self._buf_text[-1] in ".!?"

        if (ends_sentence and word_count >= MIN_FLUSH_WORDS) or word_count >= MAX_BUFFER_WORDS:
            self._flush()

    def _flush(self):
        if self._buf_text:
            self._result_queue.put((self._buf_timestamp, self._buf_text, "auto"))
            print(f"[LiveCaptions] → '{self._buf_text[:80]}'", flush=True)
            self._buf_text      = ""
            self._buf_timestamp = ""
            self._buf_updated   = 0.0

    # ------------------------------------------------------------------ #
    #  Helpers                                                            #
    # ------------------------------------------------------------------ #

    def _get_timestamp(self) -> str:
        elapsed = int(time.time() - self._start_time)
        h = elapsed // 3600
        m = (elapsed % 3600) // 60
        s = elapsed % 60
        return f"{h:02d}:{m:02d}:{s:02d}"

    @staticmethod
    def _clean(text: str) -> str:
        """Remove 'missing value' artifacts from AppleScript output."""
        return text.replace("missing value", "").replace("  ", " ").strip()

    def _read_captions(self) -> str:
        try:
            r = subprocess.run(
                ["osascript", "-e", _APPLESCRIPT],
                capture_output=True, text=True, timeout=0.8,
            )
            return self._clean(r.stdout.strip())
        except Exception:
            return ""

    # ------------------------------------------------------------------ #
    #  Poll loop                                                          #
    # ------------------------------------------------------------------ #

    def _poll_loop(self):
        print("[LiveCaptions] Polling started.", flush=True)

        check = subprocess.run(
            ["osascript", "-e",
             'tell application "System Events" to return '
             '(exists process "Live Captions")'],
            capture_output=True, text=True, timeout=2,
        )
        if check.stdout.strip().lower() != "true":
            print(
                "[LiveCaptions] Process not found — enable in "
                "System Settings → Accessibility → Live Captions",
                flush=True,
            )
            return

        while self._running:
            raw = self._read_captions()

            if raw and raw != self._prev_raw:
                new_text = self._extract_new(raw).strip()
                if new_text:
                    self._accumulate(self._get_timestamp(), new_text)
                self._prev_raw = raw

            # Timeout flush: speaker paused
            if self._buf_text and time.time() - self._buf_updated >= FLUSH_TIMEOUT:
                self._flush()

            time.sleep(self.POLL_INTERVAL)

        print("[LiveCaptions] Polling stopped.", flush=True)
