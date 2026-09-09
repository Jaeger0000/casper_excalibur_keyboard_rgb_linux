"""Tests for src.core.profiles – ProfileManager."""

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
        # The unreadable file is set aside and the built-in profiles come
        # back, so the user is left with a working app rather than nothing.
        assert "Kırmızı" in profiles

    def test_corrupt_file_is_backed_up_not_destroyed(self, pm: ProfileManager):
        """A corrupt file must be preserved instead of silently overwritten."""
        pm._profiles_file.write_text("NOT VALID JSON {{{")
        pm.set_last_used("Mavi")  # triggers a read-modify-write cycle

        backup = pm._profiles_file.with_suffix(".json.bak")
        assert backup.exists()
        assert backup.read_text() == "NOT VALID JSON {{{"

    def test_save_survives_missing_profiles_key(self, pm: ProfileManager):
        """A file without a 'profiles' key must not raise KeyError."""
        pm._profiles_file.write_text("{}")
        pm.save_profile("Test", zone="all", brightness=1, color=RGBColor(1, 2, 3))
        assert "Test" in pm.get_profiles()

    def test_delete_survives_missing_profiles_key(self, pm: ProfileManager):
        pm._profiles_file.write_text('{"last_used": null}')
        assert pm.delete_profile("Yok") is False

    def test_non_dict_json_handled(self, pm: ProfileManager):
        """A JSON document that is not an object must be rejected safely."""
        pm._profiles_file.write_text("[1, 2, 3]")
        assert "Kırmızı" in pm.get_profiles()
        assert pm._profiles_file.with_suffix(".json.bak").exists()


class TestLastState:
    """The colour state that ``--restore`` puts back at boot."""

    def test_roundtrip(self, pm: ProfileManager):
        pm.set_last_state("left", 1, RGBColor(10, 20, 30))
        state = pm.get_last_state()
        assert state == Profile(zone="left", brightness=1, r=10, g=20, b=30)

    def test_none_when_never_set(self, pm: ProfileManager):
        assert pm.get_last_state() is None

    def test_survives_a_second_write(self, pm: ProfileManager):
        pm.set_last_state("all", 2, RGBColor(1, 1, 1))
        pm.save_profile("Baska", zone="right", brightness=0, color=RGBColor(9, 9, 9))
        assert pm.get_last_state() == Profile(zone="all", brightness=2, r=1, g=1, b=1)

    def test_ad_hoc_colour_needs_no_saved_profile(self, pm: ProfileManager):
        """The whole point: a colour that was never saved is still restorable."""
        pm.set_last_state("center", 2, RGBColor(123, 45, 67))
        assert pm.get_last_used() is None
        assert pm.get_last_state() is not None

    def test_invalid_stored_state_ignored(self, pm: ProfileManager):
        pm._profiles_file.write_text(
            '{"profiles": {}, "last_used": null,'
            ' "last_state": {"zone": "top", "brightness": 9, "r": 0, "g": 0, "b": 0}}'
        )
        assert pm.get_last_state() is None

    def test_rejects_invalid_input(self, pm: ProfileManager):
        with pytest.raises(ValueError):
            pm.set_last_state("top", 1, RGBColor(0, 0, 0))

    def test_overwrite_existing_profile(self, pm: ProfileManager):
        pm.save_profile("Kırmızı", zone="right", brightness=0, color=RGBColor(1, 2, 3))
        p = pm.get_profiles()["Kırmızı"]
        assert p.zone == "right"
        assert p.r == 1
