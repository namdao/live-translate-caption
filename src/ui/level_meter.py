from PyQt6.QtCore import QTimer
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QWidget


class LevelMeter(QWidget):
    """Vertical VU bar: green → yellow → red with smooth decay."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(20, 60)
        self._level = 0.0

        self._decay_timer = QTimer()
        self._decay_timer.setInterval(50)
        self._decay_timer.timeout.connect(self._decay)
        self._decay_timer.start()

    def set_level(self, rms: float):
        level = min(1.0, rms * 8)
        if level > self._level:
            self._level = level

    def _decay(self):
        self._level *= 0.80
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#0d0d1a"))

        h = self.height()
        fill_h = int(self._level * h)
        y = h - fill_h

        if self._level < 0.6:
            color = QColor("#00ff88")
        elif self._level < 0.8:
            color = QColor("#ffcc00")
        else:
            color = QColor("#ff4444")

        painter.fillRect(0, y, self.width(), fill_h, color)
