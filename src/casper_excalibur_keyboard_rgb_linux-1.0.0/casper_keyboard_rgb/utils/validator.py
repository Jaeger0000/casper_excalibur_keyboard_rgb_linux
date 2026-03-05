"""
Input validators used across the application.
"""

from __future__ import annotations

import re

from casper_keyboard_rgb.core.config import (
    MAX_BRIGHTNESS,
    MIN_BRIGHTNESS,
    RGBColor,
    ZONE_LABELS,
)


def validate_zone(zone: str) -> str:
    """Return the canonical zone key or raise ValueError."""
    key = zone.strip().lower()
    if key not in ZONE_LABELS:
        raise ValueError(
            f"Geçersiz bölge: {zone!r}. Geçerli değerler: {list(ZONE_LABELS)}"
        )
    return key


def validate_brightness(value: int) -> int:
    """Return brightness if valid, else raise ValueError."""
    if not isinstance(value, int) or not (MIN_BRIGHTNESS <= value <= MAX_BRIGHTNESS):
        raise ValueError(
            f"Parlaklık {MIN_BRIGHTNESS}-{MAX_BRIGHTNESS} arasında olmalı, "
            f"verilen: {value!r}"
        )
    return value


def validate_color_hex(hex_str: str) -> RGBColor:
    """Parse and validate a hex colour string, return RGBColor."""
    return RGBColor.from_hex(hex_str)


def validate_profile_name(name: str) -> str:
    """
    Validate a profile name.

    Rules:
    - 1-50 characters
    - Only letters, digits, spaces, hyphens, underscores, Turkish chars
    - No leading/trailing whitespace
    """
    name = name.strip()
    if not name:
        raise ValueError("Profil adı boş olamaz")
    if len(name) > 50:
        raise ValueError("Profil adı en fazla 50 karakter olabilir")
    # Allow Unicode letters (covers Turkish İ, Ş, Ğ, etc.), digits, spaces, hyphens, underscores
    if not re.match(r"^[\w\s\-]+$", name, re.UNICODE):
        raise ValueError(
            "Profil adı yalnızca harf, rakam, boşluk, tire ve alt çizgi içerebilir"
        )
    return name
