"""
Zone selector widget – lets the user choose which keyboard zone to light.
"""

from __future__ import annotations

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QRadioButton,
    QWidget,
)

from casper_keyboard_rgb.core.config import ZONE_LABELS

# Display label → internal key
_DISPLAY_MAP: dict[str, str] = {
    "Tümü": "all",
    "Sol": "left",
    "Orta": "center",
    "Sağ": "right",
}

_REVERSE_MAP: dict[str, str] = {v: k for k, v in _DISPLAY_MAP.items()}


class ZoneSelector(QWidget):
    """
    Radio-button group for keyboard zone selection.

    Signals
    -------
    zone_changed(str)
        Emitted with the internal zone key (``"all"``, ``"left"``, etc.).
    """

    zone_changed = pyqtSignal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._buttons: dict[str, QRadioButton] = {}
        self._build_ui()

    # ── public ────────────────────────────────

    @property
    def zone(self) -> str:
        """Return the currently selected zone key."""
        for key, btn in self._buttons.items():
            if btn.isChecked():
                return key
        return "all"  # fallback

    @zone.setter
    def zone(self, key: str) -> None:
        if key in self._buttons:
            self._buttons[key].setChecked(True)

    # ── UI construction ───────────────────────

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        group = QButtonGroup(self)

        for display_label, key in _DISPLAY_MAP.items():
            rb = QRadioButton(display_label)
            rb.toggled.connect(self._on_toggled)
            group.addButton(rb)
            layout.addWidget(rb)
            self._buttons[key] = rb

        # Default: all
        self._buttons["all"].setChecked(True)

    def _on_toggled(self, checked: bool) -> None:
        if checked:
            self.zone_changed.emit(self.zone)
