"""
Brightness slider widget – maps 0/1/2 onto human-readable labels.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QSlider,
    QWidget,
)

from casper_keyboard_rgb.core.config import BRIGHTNESS_LABELS, MAX_BRIGHTNESS, MIN_BRIGHTNESS


class BrightnessSlider(QWidget):
    """
    Horizontal slider for brightness (0-2) with a dynamic label.

    Signals
    -------
    brightness_changed(int)
        Emitted when the user drags the slider.
    """

    brightness_changed = pyqtSignal(int)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._build_ui()

    # ── public ────────────────────────────────

    @property
    def brightness(self) -> int:
        return self._slider.value()

    @brightness.setter
    def brightness(self, value: int) -> None:
        clamped = max(MIN_BRIGHTNESS, min(value, MAX_BRIGHTNESS))
        self._slider.setValue(clamped)

    # ── UI ────────────────────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._slider = QSlider(Qt.Orientation.Horizontal)
        self._slider.setMinimum(MIN_BRIGHTNESS)
        self._slider.setMaximum(MAX_BRIGHTNESS)
        self._slider.setValue(MAX_BRIGHTNESS)
        self._slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self._slider.setTickInterval(1)
        self._slider.setSingleStep(1)
        self._slider.setPageStep(1)
        self._slider.valueChanged.connect(self._on_changed)
        layout.addWidget(self._slider, stretch=1)

        self._label = QLabel(BRIGHTNESS_LABELS[MAX_BRIGHTNESS])
        self._label.setFixedWidth(90)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._label)

    def _on_changed(self, value: int) -> None:
        self._label.setText(BRIGHTNESS_LABELS.get(value, str(value)))
        self.brightness_changed.emit(value)
