"""Tests for casper_keyboard_rgb.main._restore().

The boot-time restore path had no coverage at all, which is how it stayed
broken: nothing ever recorded a state for it to restore.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from casper_keyboard_rgb.core.config import RGBColor
from casper_keyboard_rgb.core.led_controller import LEDControllerError
from casper_keyboard_rgb.core.profiles import ProfileManager
from casper_keyboard_rgb.main import _restore


class _FakeController:
    """Records what would have been written to the keyboard."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[tuple] = []
        self._fail = fail

    def set_color(self, zone, brightness, color):
        if self._fail:
            raise LEDControllerError("sysfs yazılamadı")
        self.calls.append((zone, brightness, color.to_hex()))


@pytest.fixture
def restore_env(tmp_path: Path):
    """Run _restore() against an isolated config dir and a fake controller."""
    controller = _FakeController()

    def run(fail: bool = False) -> tuple[int, _FakeController]:
        ctrl = _FakeController(fail=fail) if fail else controller
        with patch("casper_keyboard_rgb.main._find_user_config_dir", return_value=tmp_path), \
             patch("casper_keyboard_rgb.core.led_controller.LEDController", return_value=ctrl):
            return _restore(), ctrl

    return tmp_path, run


def test_restores_the_last_applied_colour(restore_env):
    """An ad-hoc colour that was never saved as a profile is restored."""
    config_dir, run = restore_env
    ProfileManager(config_dir=config_dir).set_last_state(
        "center", 1, RGBColor(18, 52, 86)
    )

    rc, ctrl = run()

    assert rc == 0
    assert ctrl.calls == [("center", 1, "123456")]


def test_falls_back_to_the_last_used_profile(restore_env):
    """Configs written by older versions only have last_used."""
    config_dir, run = restore_env
    pm = ProfileManager(config_dir=config_dir)
    pm.set_last_used("Mavi")

    rc, ctrl = run()

    assert rc == 0
    assert ctrl.calls == [("all", 2, "0000FF")]


def test_last_state_wins_over_last_used(restore_env):
    config_dir, run = restore_env
    pm = ProfileManager(config_dir=config_dir)
    pm.set_last_used("Mavi")
    pm.set_last_state("left", 0, RGBColor(1, 2, 3))

    rc, ctrl = run()

    assert rc == 0
    assert ctrl.calls == [("left", 0, "010203")]


def test_nothing_saved_is_not_an_error(restore_env):
    """A fresh install must not make the boot service fail."""
    config_dir, run = restore_env
    ProfileManager(config_dir=config_dir)

    rc, ctrl = run()

    assert rc == 0
    assert ctrl.calls == []


def test_write_failure_returns_nonzero(restore_env):
    config_dir, run = restore_env
    ProfileManager(config_dir=config_dir).set_last_state(
        "all", 2, RGBColor(255, 0, 0)
    )

    rc, _ = run(fail=True)

    assert rc == 1
