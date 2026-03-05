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
import sys

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"


def _setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(format=LOG_FORMAT, level=level, stream=sys.stderr)


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

    pm = ProfileManager()
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
