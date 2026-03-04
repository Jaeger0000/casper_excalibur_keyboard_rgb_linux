"""Tests for src.core.led_controller – command building and validation."""

import re

import pytest

from src.core.config import Brightness, RGBColor, Zone
from src.core.led_controller import LEDController


class TestBuildCommand:
    """Test command string generation."""

    def test_all_zone_max_brightness_red(self):
        cmd = LEDController._build_command(Zone.ALL, 2, RGBColor(255, 0, 0))
        assert cmd == "602FF0000"

    def test_left_zone_mid_brightness_blue(self):
        cmd = LEDController._build_command(Zone.LEFT, 1, RGBColor(0, 0, 255))
        assert cmd == "3010000FF"

    def test_right_zone_off(self):
        cmd = LEDController._build_command(Zone.RIGHT, 0, RGBColor(0, 0, 0))
        assert cmd == "500000000"

    def test_center_zone_green(self):
        cmd = LEDController._build_command(Zone.CENTER, 2, RGBColor(0, 255, 0))
        assert cmd == "40200FF00"

    def test_command_matches_strict_regex(self):
        """Every valid command must match the strict format."""
        pattern = re.compile(r"^[3-6]0[0-2][0-9A-Fa-f]{6}$")
        for zone in Zone:
            for brightness in Brightness:
                cmd = LEDController._build_command(
                    zone, brightness, RGBColor(171, 205, 239)
                )
                assert pattern.match(cmd), f"Command {cmd!r} doesn't match"


class TestResolveZone:
    """Test zone string → enum resolution."""

    def test_valid_keys(self):
        assert LEDController._resolve_zone("all") == Zone.ALL
        assert LEDController._resolve_zone("left") == Zone.LEFT
        assert LEDController._resolve_zone("center") == Zone.CENTER
        assert LEDController._resolve_zone("right") == Zone.RIGHT

    def test_case_insensitive(self):
        assert LEDController._resolve_zone("ALL") == Zone.ALL
        assert LEDController._resolve_zone("Left") == Zone.LEFT

    def test_enum_passthrough(self):
        assert LEDController._resolve_zone(Zone.ALL) == Zone.ALL

    def test_invalid_zone(self):
        with pytest.raises(ValueError, match="Geçersiz bölge"):
            LEDController._resolve_zone("top")


class TestResolveBrightness:
    """Test brightness validation."""

    def test_valid_values(self):
        assert LEDController._resolve_brightness(0) == 0
        assert LEDController._resolve_brightness(1) == 1
        assert LEDController._resolve_brightness(2) == 2

    def test_enum_passthrough(self):
        assert LEDController._resolve_brightness(Brightness.MAX) == 2

    def test_invalid_too_high(self):
        with pytest.raises(ValueError, match="Parlaklık"):
            LEDController._resolve_brightness(3)

    def test_invalid_negative(self):
        with pytest.raises(ValueError, match="Parlaklık"):
            LEDController._resolve_brightness(-1)
