"""Tests for src.utils.validator."""

import pytest

from src.core.config import RGBColor
from src.utils.validator import (
    validate_brightness,
    validate_color_hex,
    validate_profile_name,
    validate_zone,
)


class TestValidateZone:
    def test_valid_zones(self):
        assert validate_zone("all") == "all"
        assert validate_zone("LEFT") == "left"
        assert validate_zone(" Right ") == "right"
        assert validate_zone("center") == "center"

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_zone("top")


class TestValidateBrightness:
    def test_valid(self):
        assert validate_brightness(0) == 0
        assert validate_brightness(1) == 1
        assert validate_brightness(2) == 2

    def test_invalid_high(self):
        with pytest.raises(ValueError):
            validate_brightness(3)

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            validate_brightness("two")  # type: ignore[arg-type]


class TestValidateColorHex:
    def test_valid(self):
        c = validate_color_hex("FF8000")
        assert c == RGBColor(255, 128, 0)

    def test_with_hash(self):
        c = validate_color_hex("#00FF00")
        assert c == RGBColor(0, 255, 0)

    def test_invalid(self):
        with pytest.raises(ValueError):
            validate_color_hex("ZZZZZZ")


class TestValidateProfileName:
    def test_valid(self):
        assert validate_profile_name("Kırmızı") == "Kırmızı"
        assert validate_profile_name("  Mavi  ") == "Mavi"
        assert validate_profile_name("profil-1") == "profil-1"
        assert validate_profile_name("test_profil") == "test_profil"

    def test_empty(self):
        with pytest.raises(ValueError, match="boş"):
            validate_profile_name("")

    def test_only_spaces(self):
        with pytest.raises(ValueError, match="boş"):
            validate_profile_name("   ")

    def test_too_long(self):
        with pytest.raises(ValueError, match="50"):
            validate_profile_name("a" * 51)

    def test_special_chars(self):
        with pytest.raises(ValueError):
            validate_profile_name("profil;drop table")
