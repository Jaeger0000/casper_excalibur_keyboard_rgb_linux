"""
Main application window.
"""

from __future__ import annotations

import logging
from typing import Optional

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QColor, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from casper_keyboard_rgb.core.config import RGBColor
from casper_keyboard_rgb.core.led_controller import LEDController, LEDControllerError
from casper_keyboard_rgb.core.profiles import ProfileManager
from casper_keyboard_rgb.gui.brightness_slider import BrightnessSlider
from casper_keyboard_rgb.gui.color_picker import ColorPicker
from casper_keyboard_rgb.gui.zone_selector import ZoneSelector
from casper_keyboard_rgb.utils.permission_handler import run_preflight_checks
from casper_keyboard_rgb.utils.validator import validate_profile_name

logger = logging.getLogger(__name__)

_WINDOW_TITLE = "Casper Excalibur Klavye RGB"
_WINDOW_SIZE = QSize(480, 520)

# ──────────────────────────────────────────────
# Stylesheet
# ──────────────────────────────────────────────
_STYLESHEET = """
QMainWindow {
    background-color: #1e1e2e;
}
QGroupBox {
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 8px;
    margin-top: 14px;
    padding: 14px 10px 10px 10px;
    font-weight: bold;
}
QGroupBox::title {
    subcontrol-origin: margin;
    left: 12px;
    padding: 0 6px;
}
QLabel {
    color: #cdd6f4;
}
QPushButton {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 8px 16px;
    font-size: 13px;
}
QPushButton:hover {
    background-color: #45475a;
}
QPushButton:pressed {
    background-color: #585b70;
}
QPushButton#applyBtn {
    background-color: #a6e3a1;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#applyBtn:hover {
    background-color: #94e2d5;
}
QPushButton#offBtn {
    background-color: #f38ba8;
    color: #1e1e2e;
    font-weight: bold;
}
QPushButton#offBtn:hover {
    background-color: #eba0ac;
}
QComboBox {
    background-color: #313244;
    color: #cdd6f4;
    border: 1px solid #45475a;
    border-radius: 6px;
    padding: 6px 10px;
}
QComboBox QAbstractItemView {
    background-color: #313244;
    color: #cdd6f4;
    selection-background-color: #45475a;
}
QSlider::groove:horizontal {
    background: #45475a;
    height: 8px;
    border-radius: 4px;
}
QSlider::handle:horizontal {
    background: #cba6f7;
    width: 18px;
    margin: -5px 0;
    border-radius: 9px;
}
QSlider::sub-page:horizontal {
    background: #cba6f7;
    border-radius: 4px;
}
QRadioButton {
    color: #cdd6f4;
    spacing: 6px;
}
QRadioButton::indicator {
    width: 16px;
    height: 16px;
}
QStatusBar {
    color: #a6adc8;
    background-color: #181825;
}
"""


class MainWindow(QMainWindow):
    """Primary application window."""

    def __init__(self) -> None:
        super().__init__()
        self._controller = LEDController()
        self._profile_mgr = ProfileManager()

        self.setWindowTitle(_WINDOW_TITLE)
        self.setFixedSize(_WINDOW_SIZE)
        self.setStyleSheet(_STYLESHEET)

        self._build_ui()
        self._populate_profiles()
        self._run_preflight()

    # ── UI construction ───────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        # ── Colour preview + picker ──
        color_group = QGroupBox("Renk")
        color_layout = QVBoxLayout()

        self._color_preview = QWidget()
        self._color_preview.setFixedHeight(60)
        self._color_preview.setStyleSheet(
            "background-color: #FF0000; border-radius: 10px;"
        )
        color_layout.addWidget(self._color_preview)

        self._color_picker = ColorPicker(QColor(255, 0, 0))
        self._color_picker.color_changed.connect(self._on_color_changed)
        color_layout.addWidget(self._color_picker)

        color_group.setLayout(color_layout)
        root.addWidget(color_group)

        # ── Zone selector ──
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QVBoxLayout()
        self._zone_selector = ZoneSelector()
        zone_layout.addWidget(self._zone_selector)
        zone_group.setLayout(zone_layout)
        root.addWidget(zone_group)

        # ── Brightness ──
        bright_group = QGroupBox("Parlaklık")
        bright_layout = QVBoxLayout()
        self._brightness = BrightnessSlider()
        bright_layout.addWidget(self._brightness)
        bright_group.setLayout(bright_layout)
        root.addWidget(bright_group)

        # ── Profiles ──
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()

        self._profile_combo = QComboBox()
        self._profile_combo.setMinimumWidth(140)
        profile_layout.addWidget(self._profile_combo, stretch=1)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._on_load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._on_save_profile)
        profile_layout.addWidget(save_btn)

        del_btn = QPushButton("Sil")
        del_btn.clicked.connect(self._on_delete_profile)
        profile_layout.addWidget(del_btn)

        profile_group.setLayout(profile_layout)
        root.addWidget(profile_group)

        # ── Action buttons ──
        btn_row = QHBoxLayout()

        apply_btn = QPushButton("Uygula")
        apply_btn.setObjectName("applyBtn")
        apply_btn.clicked.connect(self._on_apply)
        btn_row.addWidget(apply_btn)

        off_btn = QPushButton("LED Kapat")
        off_btn.setObjectName("offBtn")
        off_btn.clicked.connect(self._on_turn_off)
        btn_row.addWidget(off_btn)

        root.addLayout(btn_row)

        # ── Status bar ──
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Hazır")

    # ── Slots ─────────────────────────────────

    def _on_color_changed(self, color: QColor) -> None:
        self._color_preview.setStyleSheet(
            f"background-color: {color.name()}; border-radius: 10px;"
        )

    def _on_apply(self) -> None:
        color = self._color_picker.color
        rgb = RGBColor(color.red(), color.green(), color.blue())
        zone = self._zone_selector.zone
        brightness = self._brightness.brightness

        try:
            self._controller.set_color(zone=zone, brightness=brightness, color=rgb)
            self._status.showMessage(
                f"Uygulandı: {zone} | #{rgb.to_hex()} | Parlaklık {brightness}"
            )
        except LEDControllerError as exc:
            logger.exception("LED ayarlanamadı")
            QMessageBox.critical(self, "Hata", str(exc))
        except ValueError as exc:
            QMessageBox.warning(self, "Geçersiz Değer", str(exc))

    def _on_turn_off(self) -> None:
        try:
            self._controller.turn_off()
            self._status.showMessage("LED'ler kapatıldı")
        except LEDControllerError as exc:
            logger.exception("LED kapatılamadı")
            QMessageBox.critical(self, "Hata", str(exc))

    def _populate_profiles(self) -> None:
        self._profile_combo.clear()
        profiles = self._profile_mgr.get_profiles()
        for name in profiles:
            self._profile_combo.addItem(name)

    def _on_load_profile(self) -> None:
        name = self._profile_combo.currentText()
        if not name:
            return

        profiles = self._profile_mgr.get_profiles()
        if name not in profiles:
            QMessageBox.warning(self, "Hata", f"Profil bulunamadı: {name}")
            return

        p = profiles[name]
        self._color_picker.color = QColor(p.r, p.g, p.b)
        self._brightness.brightness = p.brightness
        self._zone_selector.zone = p.zone
        self._status.showMessage(f"Profil yüklendi: {name}")

    def _on_save_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if not ok or not name:
            return

        try:
            name = validate_profile_name(name)
        except ValueError as exc:
            QMessageBox.warning(self, "Geçersiz Ad", str(exc))
            return

        color = self._color_picker.color
        rgb = RGBColor(color.red(), color.green(), color.blue())

        self._profile_mgr.save_profile(
            name=name,
            zone=self._zone_selector.zone,
            brightness=self._brightness.brightness,
            color=rgb,
        )
        self._populate_profiles()
        # Select the newly saved profile
        idx = self._profile_combo.findText(name)
        if idx >= 0:
            self._profile_combo.setCurrentIndex(idx)
        self._status.showMessage(f"Profil kaydedildi: {name}")

    def _on_delete_profile(self) -> None:
        name = self._profile_combo.currentText()
        if not name:
            return

        reply = QMessageBox.question(
            self,
            "Profil Sil",
            f"'{name}' profilini silmek istediğinize emin misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._profile_mgr.delete_profile(name)
            self._populate_profiles()
            self._status.showMessage(f"Profil silindi: {name}")

    # ── Preflight ─────────────────────────────

    def _run_preflight(self) -> None:
        """Show warnings for missing prerequisites."""
        results = run_preflight_checks()
        warnings = [msg for ok, msg in results if not ok]
        if warnings:
            detail = "\n\n".join(warnings)
            QMessageBox.warning(
                self,
                "Uyarı",
                "Bazı bileşenler eksik veya düzgün yapılandırılmamış:\n\n" + detail,
            )
