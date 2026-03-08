from collections import deque

from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import QWidget


class WaveformWidget(QWidget):
    """Scrolling amplitude waveform, updated at 20 fps."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(80)
        self._buffer = deque([0.0] * 200, maxlen=200)
        self._active = False

        self._repaint_timer = QTimer()
        self._repaint_timer.setInterval(50)  # 20 fps
        self._repaint_timer.timeout.connect(self.update)
        # Timer starts only when recording (set_active(True))

    def push_level(self, rms: float):
        """Feed one RMS amplitude sample (0.0–1.0)."""
        self._buffer.append(rms)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._repaint_timer.start()
        else:
            self._buffer.clear()
            self._buffer.extend([0.0] * self._buffer.maxlen)
            self._repaint_timer.stop()
            self.update()  # final repaint to show flat line

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0d0d1a"))

        w = self.width()
        h = self.height()
        mid = h // 2

        pen = QPen(QColor("#e94560"))
        pen.setWidth(2)
        painter.setPen(pen)

        samples = list(self._buffer)
        n = len(samples)
        if n < 2:
            painter.drawLine(0, mid, w, mid)
            return

        step = w / n
        prev_x, prev_y = 0, mid

        for i, amp in enumerate(samples):
            x = int(i * step)
            # Scale RMS (typically 0–0.1) for visual clarity
            scaled = min(1.0, amp * 8)
            y = int(mid - scaled * (mid - 4))
            if i == 0:
                prev_x, prev_y = x, y
            else:
                painter.drawLine(prev_x, prev_y, x, y)
                prev_x, prev_y = x, y
