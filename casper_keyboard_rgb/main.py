"""
Application entry point.

Usage
─────
    # GUI mode (default)
    casper-keyboard-rgb

    # Restore last-used profile (called by systemd at boot)
    casper-keyboard-rgb --restore
"""

from __future__ import annotations

import argparse
import logging
import os
import pwd
import sys
from pathlib import Path

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, level=level, stream=sys.stderr)


def _find_user_config_dir() -> Path:
    """
    Return the config directory to restore from.

    When the process runs as root (e.g. systemd service) Path.home() resolves
    to /root, not to the desktop user's home.  Scan /etc/passwd for the first
    human user (UID ≥ 1000) who already has a profiles.json and return their
    config directory instead.  Falls back to the standard CONFIG_DIR when no
    match is found.
    """
    from casper_keyboard_rgb.core.config import APP_NAME, CONFIG_DIR

    if os.getuid() != 0:
        return CONFIG_DIR

    for pw in sorted(pwd.getpwall(), key=lambda p: p.pw_uid):
        if pw.pw_uid < 1000:
            continue
        candidate = Path(pw.pw_dir) / ".config" / APP_NAME / "profiles.json"
        if candidate.exists():
            return Path(pw.pw_dir) / ".config" / APP_NAME

    return CONFIG_DIR


def _restore() -> int:
    """
    Restore the last-used LED profile.

    Designed to be called from the systemd oneshot service at boot.
    Runs without a display server, so no GUI is needed.
    """
    from casper_keyboard_rgb.core.config import RGBColor
    from casper_keyboard_rgb.core.led_controller import LEDController, LEDControllerError
    from casper_keyboard_rgb.core.profiles import ProfileManager

    logger = logging.getLogger("restore")

    pm = ProfileManager(config_dir=_find_user_config_dir())
    profile = pm.get_last_used()
    if profile is None:
        logger.info("Geri yüklenecek profil yok – çıkılıyor.")
        return 0

    controller = LEDController()  # direct write works as root via systemd
    try:
        controller.set_color(
            zone=profile.zone,
            brightness=profile.brightness,
            color=RGBColor(profile.r, profile.g, profile.b),
        )
        logger.info("Profil geri yüklendi: %s", pm.get_last_used_name())
    except LEDControllerError as exc:
        logger.error("Profil geri yüklenemedi: %s", exc)
        return 1
    return 0


def _gui() -> int:
    """Launch the PyQt6 GUI."""
    from PyQt6.QtWidgets import QApplication

    from casper_keyboard_rgb.gui.main_window import MainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    app.setDesktopFileName("casper-keyboard-rgb")

    window = MainWindow()
    window.show()
    return app.exec()


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="casper-keyboard-rgb",
        description="Casper Excalibur klavye RGB LED kontrol aracı",
    )
    parser.add_argument(
        "--restore",
        action="store_true",
        help="Son kullanılan profili geri yükle (systemd servisi için)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Ayrıntılı log çıktısı",
    )
    args = parser.parse_args()

    _setup_logging(args.verbose)

    if args.restore:
        return _restore()
    return _gui()


if __name__ == "__main__":
    raise SystemExit(main())
