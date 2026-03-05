"""Tests for src.core.config – RGBColor and validation helpers."""

import pytest

from casper_keyboard_rgb.core.config import RGBColor, validate_led_path


class TestRGBColor:
    """RGBColor dataclass tests."""

    def test_valid_color(self):
        c = RGBColor(255, 128, 0)
        assert c.r == 255
        assert c.g == 128
        assert c.b == 0

    def test_to_hex(self):
        assert RGBColor(255, 0, 0).to_hex() == "FF0000"
        assert RGBColor(0, 255, 0).to_hex() == "00FF00"
        assert RGBColor(0, 0, 255).to_hex() == "0000FF"
        assert RGBColor(0, 0, 0).to_hex() == "000000"
        assert RGBColor(16, 32, 48).to_hex() == "102030"

    def test_from_hex(self):
        c = RGBColor.from_hex("FF8000")
        assert c == RGBColor(255, 128, 0)

    def test_from_hex_with_hash(self):
        c = RGBColor.from_hex("#00FF00")
        assert c == RGBColor(0, 255, 0)

    def test_from_hex_lowercase(self):
        c = RGBColor.from_hex("aabbcc")
        assert c == RGBColor(170, 187, 204)

    def test_roundtrip(self):
        original = RGBColor(123, 45, 67)
        restored = RGBColor.from_hex(original.to_hex())
        assert restored == original

    def test_invalid_negative(self):
        with pytest.raises(ValueError, match="R"):
            RGBColor(-1, 0, 0)

    def test_invalid_overflow(self):
        with pytest.raises(ValueError, match="G"):
            RGBColor(0, 256, 0)

    def test_invalid_type(self):
        with pytest.raises(ValueError):
            RGBColor(1.5, 0, 0)  # type: ignore[arg-type]

    def test_from_hex_invalid_short(self):
        with pytest.raises(ValueError, match="Geçersiz hex"):
            RGBColor.from_hex("FFF")

    def test_from_hex_invalid_chars(self):
        with pytest.raises(ValueError, match="Geçersiz hex"):
            RGBColor.from_hex("GGHHII")

    def test_immutable(self):
        c = RGBColor(100, 100, 100)
        with pytest.raises(AttributeError):
            c.r = 200  # type: ignore[misc]


class TestValidateLedPath:
    """validate_led_path security tests."""

    def test_rejects_non_sys_path(self, tmp_path):
        fake = tmp_path / "evil"
        fake.touch()
        with pytest.raises(PermissionError, match="/sys/"):
            validate_led_path(str(fake))

    def test_rejects_nonexistent(self):
        with pytest.raises(PermissionError):
            validate_led_path("/tmp/nonexistent_led_path_xyz")
