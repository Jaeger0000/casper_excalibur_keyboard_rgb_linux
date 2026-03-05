"""Tests for src.core.profiles – ProfileManager."""

import json
from pathlib import Path

import pytest

from casper_keyboard_rgb.core.config import RGBColor
from casper_keyboard_rgb.core.profiles import Profile, ProfileManager


@pytest.fixture
def pm(tmp_path: Path) -> ProfileManager:
    """Create a ProfileManager with an isolated config directory."""
    return ProfileManager(config_dir=tmp_path)


class TestProfile:
    def test_valid(self):
        p = Profile(zone="all", brightness=2, r=255, g=0, b=0)
        assert p.color == RGBColor(255, 0, 0)

    def test_invalid_zone(self):
        with pytest.raises(ValueError, match="Geçersiz bölge"):
            Profile(zone="top", brightness=2, r=255, g=0, b=0)

    def test_invalid_brightness(self):
        with pytest.raises(ValueError, match="Geçersiz parlaklık"):
            Profile(zone="all", brightness=5, r=255, g=0, b=0)

    def test_invalid_color(self):
        with pytest.raises(ValueError):
            Profile(zone="all", brightness=2, r=999, g=0, b=0)


class TestProfileManager:
    def test_defaults_created(self, pm: ProfileManager):
        profiles = pm.get_profiles()
        assert "Kırmızı" in profiles
        assert "Mavi" in profiles
        assert "Kapalı" in profiles

    def test_save_and_load(self, pm: ProfileManager):
        pm.save_profile("Test", zone="left", brightness=1, color=RGBColor(10, 20, 30))
        profiles = pm.get_profiles()
        assert "Test" in profiles
        p = profiles["Test"]
        assert p.zone == "left"
        assert p.brightness == 1
        assert p.r == 10

    def test_delete(self, pm: ProfileManager):
        assert pm.delete_profile("Kırmızı") is True
        assert "Kırmızı" not in pm.get_profiles()

    def test_delete_nonexistent(self, pm: ProfileManager):
        assert pm.delete_profile("NoSuchProfile") is False

    def test_last_used(self, pm: ProfileManager):
        pm.set_last_used("Mavi")
        p = pm.get_last_used()
        assert p is not None
        assert p.b == 255

    def test_last_used_none(self, pm: ProfileManager):
        assert pm.get_last_used() is None

    def test_file_permissions(self, pm: ProfileManager):
        """Profile file should be readable only by the owner."""
        profiles_file = pm._profiles_file
        mode = profiles_file.stat().st_mode & 0o777
        assert mode == 0o600, f"Expected 0600, got {oct(mode)}"

    def test_corrupt_file_handled(self, pm: ProfileManager):
        """A corrupt JSON file should not crash the app."""
        pm._profiles_file.write_text("NOT VALID JSON {{{")
        profiles = pm.get_profiles()
        assert profiles == {}

    def test_overwrite_existing_profile(self, pm: ProfileManager):
        pm.save_profile("Kırmızı", zone="right", brightness=0, color=RGBColor(1, 2, 3))
        p = pm.get_profiles()["Kırmızı"]
        assert p.zone == "right"
        assert p.r == 1
