"""
Color picker widget – wraps QColorDialog with a live preview.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)


class ColorPicker(QWidget):
    """
    A compound widget: colour preview label + pick button.

    Signals
    -------
    color_changed(QColor)
        Emitted whenever the user selects a new colour.
    """

    color_changed = pyqtSignal(QColor)

    def __init__(self, initial: QColor | None = None, parent: QWidget | None = None):
        super().__init__(parent)
        self._color = initial or QColor(255, 0, 0)
        self._build_ui()

    # ── public ────────────────────────────────

    @property
    def color(self) -> QColor:
        return QColor(self._color)  # defensive copy

    @color.setter
    def color(self, value: QColor) -> None:
        if value.isValid():
            self._color = QColor(value)
            self._update_preview()
            self.color_changed.emit(self._color)

    # ── UI construction ───────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._preview = QLabel()
        self._preview.setFixedSize(80, 40)
        self._preview.setStyleSheet(
            f"background-color: {self._color.name()};"
            "border: 2px solid #555; border-radius: 6px;"
        )
        layout.addWidget(self._preview)

        self._hex_label = QLabel(self._color.name().upper())
        self._hex_label.setFixedWidth(80)
        layout.addWidget(self._hex_label)

        btn = QPushButton("Renk Seç")
        btn.setFixedWidth(100)
        btn.clicked.connect(self._on_pick)
        layout.addWidget(btn)

        layout.addStretch()

    def _update_preview(self) -> None:
        self._preview.setStyleSheet(
            f"background-color: {self._color.name()};"
            "border: 2px solid #555; border-radius: 6px;"
        )
        self._hex_label.setText(self._color.name().upper())

    def _on_pick(self) -> None:
        color = QColorDialog.getColor(
            self._color,
            self,
            "Renk Seçin",
            QColorDialog.ColorDialogOption.ShowAlphaChannel
            if False  # alpha not needed for LED
            else QColorDialog.ColorDialogOption(0),
        )
        if color.isValid():
            self.color = color
