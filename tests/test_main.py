"""Tests for casper_keyboard_rgb.main – _find_user_config_dir()."""

import json
from pathlib import Path
from unittest.mock import patch

from casper_keyboard_rgb.main import _find_user_config_dir


APP_NAME = "casper-keyboard-rgb"


class TestFindUserConfigDir:
    """Unit tests for _find_user_config_dir()."""

    def test_non_root_returns_default(self):
        """When running as a normal user (UID != 0), return CONFIG_DIR."""
        from casper_keyboard_rgb.core.config import CONFIG_DIR

        with patch("os.getuid", return_value=1000):
            result = _find_user_config_dir()

        assert result == CONFIG_DIR

    def test_root_finds_human_user_profile(self, tmp_path: Path):
        """When root, return the first human user's config dir that has profiles.json."""
        # Set up a fake user home with a profiles.json
        fake_home = tmp_path / "home" / "alice"
        config_dir = fake_home / ".config" / APP_NAME
        config_dir.mkdir(parents=True)
        profiles_file = config_dir / "profiles.json"
        profiles_file.write_text(
            json.dumps({"profiles": {}, "last_used": "Kırmızı"}),
            encoding="utf-8",
        )

        import pwd as _pwd

        fake_entries = [
            _pwd.struct_passwd(("root", "x", 0, 0, "", "/root", "/bin/bash")),
            _pwd.struct_passwd(("daemon", "x", 1, 1, "", "/usr/sbin", "/bin/sh")),
            _pwd.struct_passwd(("alice", "x", 1000, 1000, "", str(fake_home), "/bin/bash")),
        ]

        with patch("os.getuid", return_value=0), \
             patch("pwd.getpwall", return_value=fake_entries):
            result = _find_user_config_dir()

        assert result == config_dir

    def test_root_skips_users_without_profile(self, tmp_path: Path):
        """When root, skip human users who don't have profiles.json yet."""
        fake_home_alice = tmp_path / "home" / "alice"
        fake_home_alice.mkdir(parents=True)
        # alice has NO profiles.json

        fake_home_bob = tmp_path / "home" / "bob"
        config_dir = fake_home_bob / ".config" / APP_NAME
        config_dir.mkdir(parents=True)
        (config_dir / "profiles.json").write_text("{}", encoding="utf-8")

        import pwd as _pwd

        fake_entries = [
            _pwd.struct_passwd(("alice", "x", 1000, 1000, "", str(fake_home_alice), "/bin/bash")),
            _pwd.struct_passwd(("bob", "x", 1001, 1001, "", str(fake_home_bob), "/bin/bash")),
        ]

        with patch("os.getuid", return_value=0), \
             patch("pwd.getpwall", return_value=fake_entries):
            result = _find_user_config_dir()

        assert result == config_dir

    def test_root_falls_back_when_no_profile_found(self):
        """When root and no human user has profiles.json, fall back to CONFIG_DIR."""
        from casper_keyboard_rgb.core.config import CONFIG_DIR

        import pwd as _pwd

        fake_entries = [
            _pwd.struct_passwd(("root", "x", 0, 0, "", "/root", "/bin/bash")),
            _pwd.struct_passwd(("nobody", "x", 65534, 65534, "", "/nonexistent", "/sbin/nologin")),
        ]

        with patch("os.getuid", return_value=0), \
             patch("pwd.getpwall", return_value=fake_entries):
            result = _find_user_config_dir()

        assert result == CONFIG_DIR

    def test_root_picks_lowest_uid_first(self, tmp_path: Path):
        """When root, the user with the lowest UID ≥ 1000 is preferred."""
        home_a = tmp_path / "home" / "a"
        home_b = tmp_path / "home" / "b"
        for home in (home_a, home_b):
            cfg = home / ".config" / APP_NAME
            cfg.mkdir(parents=True)
            (cfg / "profiles.json").write_text("{}", encoding="utf-8")

        import pwd as _pwd

        # Deliberately shuffle the list order to confirm sort-by-uid logic
        fake_entries = [
            _pwd.struct_passwd(("b", "x", 1002, 1002, "", str(home_b), "/bin/bash")),
            _pwd.struct_passwd(("a", "x", 1001, 1001, "", str(home_a), "/bin/bash")),
        ]

        with patch("os.getuid", return_value=0), \
             patch("pwd.getpwall", return_value=fake_entries):
            result = _find_user_config_dir()

        assert result == home_a / ".config" / APP_NAME
