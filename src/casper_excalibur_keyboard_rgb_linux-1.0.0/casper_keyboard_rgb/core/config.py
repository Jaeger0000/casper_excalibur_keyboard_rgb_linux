"""
Configuration constants for Casper WMI keyboard LED control.

Zone codes and brightness levels are derived from the casper-wmi kernel module:
https://github.com/Mustafa-eksi/casper-wmi

Security note:
  - LED_CONTROL_PATH is validated at runtime to ensure it resides
    under /sys/class/leds/ and is not a symlink pointing outside sysfs.
  - All user inputs are strictly validated before being written.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from enum import IntEnum
from pathlib import Path
from typing import Final


# ──────────────────────────────────────────────
# Zone definitions (from casper-wmi driver)
# ──────────────────────────────────────────────
class Zone(IntEnum):
    """Keyboard LED zones as defined in the casper-wmi kernel module."""
    LEFT = 0x03
    CENTER = 0x04
    RIGHT = 0x05
    ALL = 0x06


# Human-readable label → Zone enum mapping
ZONE_LABELS: Final[dict[str, Zone]] = {
    "right": Zone.RIGHT,
    "left": Zone.LEFT,
    "center": Zone.CENTER,
    "all": Zone.ALL,
}


# ──────────────────────────────────────────────
# Brightness levels
# ──────────────────────────────────────────────
class Brightness(IntEnum):
    """Brightness levels supported by the driver."""
    OFF = 0x00
    MID = 0x01
    MAX = 0x02


MAX_BRIGHTNESS: Final[int] = Brightness.MAX
MIN_BRIGHTNESS: Final[int] = Brightness.OFF

BRIGHTNESS_LABELS: Final[dict[int, str]] = {
    Brightness.OFF: "Kapalı",
    Brightness.MID: "Orta",
    Brightness.MAX: "Maksimum",
}


# ──────────────────────────────────────────────
# Sysfs LED control path
# ──────────────────────────────────────────────
LED_CONTROL_PATH: Final[str] = "/sys/class/leds/casper::kbd_backlight/led_control"

# Allowed parent directory – used for path validation
_ALLOWED_SYSFS_PREFIX: Final[str] = "/sys/class/leds/"


# ──────────────────────────────────────────────
# Application paths
# ──────────────────────────────────────────────
APP_NAME: Final[str] = "casper-keyboard-rgb"
CONFIG_DIR: Final[Path] = Path.home() / ".config" / APP_NAME
PROFILES_FILE: Final[Path] = CONFIG_DIR / "profiles.json"

# Polkit action helper script installed by the package
HELPER_SCRIPT_PATH: Final[str] = "/usr/lib/casper-keyboard-rgb/led-write-helper"

# ──────────────────────────────────────────────
# Regex for strict hex color validation
# ──────────────────────────────────────────────
HEX_COLOR_RE: Final[re.Pattern[str]] = re.compile(r"^[0-9A-Fa-f]{6}$")


# ──────────────────────────────────────────────
# Validation helpers
# ──────────────────────────────────────────────
@dataclass(frozen=True, slots=True)
class RGBColor:
    """Immutable RGB color with built-in validation."""

    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        for channel, name in ((self.r, "R"), (self.g, "G"), (self.b, "B")):
            if not isinstance(channel, int) or not (0 <= channel <= 255):
                raise ValueError(
                    f"{name} değeri 0-255 arası tam sayı olmalı, verilen: {channel!r}"
                )

    def to_hex(self) -> str:
        """Return zero-padded uppercase hex string, e.g. 'FF00AB'."""
        return f"{self.r:02X}{self.g:02X}{self.b:02X}"

    @classmethod
    def from_hex(cls, hex_str: str) -> "RGBColor":
        """Create RGBColor from a 6-char hex string like 'FF00AB'."""
        hex_str = hex_str.strip().lstrip("#")
        if not HEX_COLOR_RE.match(hex_str):
            raise ValueError(f"Geçersiz hex renk kodu: {hex_str!r}")
        return cls(
            r=int(hex_str[0:2], 16),
            g=int(hex_str[2:4], 16),
            b=int(hex_str[4:6], 16),
        )


def validate_led_path(path: str) -> str:
    """
    Validate that *path* is a safe sysfs LED control file.

    Raises:
        FileNotFoundError: if the path does not exist.
        PermissionError: if the resolved path escapes the allowed prefix.
    """
    resolved = os.path.realpath(path)  # resolve all symlinks

    # Must still reside under /sys/ after resolving
    if not resolved.startswith("/sys/"):
        raise PermissionError(
            f"LED kontrol dosyası /sys/ dışına işaret ediyor: {resolved}"
        )

    if not os.path.exists(resolved):
        raise FileNotFoundError(
            f"LED kontrol dosyası bulunamadı: {resolved}"
        )

    return resolved
