"""Smoke tests for the PyQt6 widgets.

The GUI carries the state-persistence logic that ``--restore`` depends on,
so it needs at least enough coverage to catch a broken wiring.

Dialogs are stubbed by replacing the *module-level* names in
``gui.main_window`` rather than by setting attributes on the Qt classes
themselves, which sip does not allow.
"""

import pytest

pytest.importorskip("PyQt6", reason="PyQt6 kurulu değil")

from PyQt6.QtGui import QColor  # noqa: E402
from PyQt6.QtWidgets import QMessageBox  # noqa: E402

from casper_keyboard_rgb.core.config import RGBColor  # noqa: E402
from casper_keyboard_rgb.core.led_controller import LEDControllerError  # noqa: E402
from casper_keyboard_rgb.core.profiles import ProfileManager  # noqa: E402
from casper_keyboard_rgb.gui.brightness_slider import BrightnessSlider  # noqa: E402
from casper_keyboard_rgb.gui.color_picker import ColorPicker  # noqa: E402
from casper_keyboard_rgb.gui.main_window import MainWindow  # noqa: E402
from casper_keyboard_rgb.gui.zone_selector import ZoneSelector  # noqa: E402

_MODULE = "casper_keyboard_rgb.gui.main_window"


class _FakeController:
    def __init__(self) -> None:
        self.calls: list[tuple] = []
        self.error: Exception | None = None

    def set_color(self, zone, brightness, color):
        if self.error:
            raise self.error
        self.calls.append((zone, brightness, color.to_hex()))

    def turn_off(self):
        if self.error:
            raise self.error
        self.calls.append(("all", 0, "000000"))


class _Dialogs:
    """Stand-in for QMessageBox / QInputDialog that records what was shown."""

    StandardButton = QMessageBox.StandardButton

    def __init__(self) -> None:
        self.critical_messages: list[str] = []
        self.warning_messages: list[str] = []
        self.answer_yes = True
        self.text_reply: tuple[str, bool] = ("", False)

    # QMessageBox surface
    def critical(self, _parent, _title, text, *args, **kwargs):
        self.critical_messages.append(text)

    def warning(self, _parent, _title, text, *args, **kwargs):
        self.warning_messages.append(text)

    def question(self, *_args, **_kwargs):
        return (QMessageBox.StandardButton.Yes if self.answer_yes
                else QMessageBox.StandardButton.No)

    # QInputDialog surface
    def getText(self, *_args, **_kwargs):
        return self.text_reply


@pytest.fixture
def window(qtbot, tmp_path, monkeypatch):
    """A MainWindow with an isolated profile store and no real hardware."""
    controller = _FakeController()
    dialogs = _Dialogs()

    monkeypatch.setattr(f"{_MODULE}.describe_blocking_problems", lambda: [])
    monkeypatch.setattr(f"{_MODULE}.LEDController", lambda *a, **kw: controller)
    monkeypatch.setattr(
        f"{_MODULE}.ProfileManager",
        lambda *a, **kw: ProfileManager(config_dir=tmp_path),
    )
    monkeypatch.setattr(f"{_MODULE}.QMessageBox", dialogs)
    monkeypatch.setattr(f"{_MODULE}.QInputDialog", dialogs)

    win = MainWindow()
    qtbot.addWidget(win)
    return win, controller, dialogs, tmp_path


class TestWidgets:
    def test_zone_selector_defaults_to_all(self, qtbot):
        w = ZoneSelector()
        qtbot.addWidget(w)
        assert w.zone == "all"

    def test_zone_selector_roundtrip(self, qtbot):
        w = ZoneSelector()
        qtbot.addWidget(w)
        for key in ("left", "center", "right", "all"):
            w.zone = key
            assert w.zone == key

    def test_brightness_slider_clamps(self, qtbot):
        w = BrightnessSlider()
        qtbot.addWidget(w)
        w.brightness = 99
        assert w.brightness == 2
        w.brightness = -5
        assert w.brightness == 0

    def test_color_picker_emits_on_change(self, qtbot):
        w = ColorPicker(QColor(255, 0, 0))
        qtbot.addWidget(w)
        with qtbot.waitSignal(w.color_changed):
            w.color = QColor(0, 128, 255)
        assert w.color.getRgb()[:3] == (0, 128, 255)

    def test_color_picker_getter_returns_a_copy(self, qtbot):
        w = ColorPicker(QColor(0, 128, 255))
        qtbot.addWidget(w)
        borrowed = w.color
        borrowed.setRed(200)
        assert w.color.red() == 0


class TestMainWindow:
    def test_apply_writes_to_the_controller(self, window):
        win, controller, _, _ = window
        win._color_picker.color = QColor(255, 128, 0)
        win._zone_selector.zone = "left"
        win._brightness.brightness = 1

        win._on_apply()

        assert controller.calls == [("left", 1, "FF8000")]

    def test_apply_persists_state_for_restore(self, window):
        """The regression that made --restore a no-op."""
        win, _, _, config_dir = window
        win._color_picker.color = QColor(18, 52, 86)
        win._zone_selector.zone = "center"
        win._brightness.brightness = 2

        win._on_apply()

        state = ProfileManager(config_dir=config_dir).get_last_state()
        assert state is not None
        assert (state.zone, state.brightness, state.color.to_hex()) == (
            "center", 2, "123456",
        )

    def test_failed_apply_does_not_persist_state(self, window):
        win, controller, dialogs, config_dir = window
        controller.error = LEDControllerError("donanım yok")

        win._on_apply()

        assert dialogs.critical_messages == ["donanım yok"]
        assert ProfileManager(config_dir=config_dir).get_last_state() is None

    def test_turn_off_persists_off_state(self, window):
        win, _, _, config_dir = window
        win._on_turn_off()

        state = ProfileManager(config_dir=config_dir).get_last_state()
        assert state is not None
        assert (state.brightness, state.color.to_hex()) == (0, "000000")

    def test_load_profile_records_last_used(self, window):
        win, _, _, config_dir = window
        idx = win._profile_combo.findText("Mavi")
        assert idx >= 0
        win._profile_combo.setCurrentIndex(idx)

        win._on_load_profile()

        assert ProfileManager(config_dir=config_dir).get_last_used_name() == "Mavi"
        assert win._color_picker.color.getRgb()[:3] == (0, 0, 255)

    def test_default_profiles_are_listed(self, window):
        win, _, _, _ = window
        items = [win._profile_combo.itemText(i)
                 for i in range(win._profile_combo.count())]
        assert "Kırmızı" in items and "Kapalı" in items

    def test_save_profile_roundtrip(self, window):
        win, _, dialogs, config_dir = window
        dialogs.text_reply = ("Gece", True)
        win._color_picker.color = QColor(1, 2, 3)
        win._zone_selector.zone = "right"
        win._brightness.brightness = 1

        win._on_save_profile()

        saved = ProfileManager(config_dir=config_dir).get_profiles()["Gece"]
        assert saved.color == RGBColor(1, 2, 3)
        assert saved.zone == "right"
        assert win._profile_combo.currentText() == "Gece"

    def test_save_profile_rejects_bad_name(self, window):
        win, _, dialogs, config_dir = window
        dialogs.text_reply = ("kötü;ad", True)

        win._on_save_profile()

        assert dialogs.warning_messages
        assert "kötü;ad" not in ProfileManager(config_dir=config_dir).get_profiles()

    def test_save_profile_reports_storage_errors(self, window, monkeypatch):
        """A failing store must show a dialog, not raise out of the slot."""
        win, _, dialogs, _ = window
        dialogs.text_reply = ("Yeni", True)

        def boom(**_kwargs):
            raise OSError("disk dolu")

        monkeypatch.setattr(win._profile_mgr, "save_profile", boom)
        win._on_save_profile()

        assert dialogs.critical_messages
        assert "disk dolu" in dialogs.critical_messages[0]

    def test_delete_profile_removes_it(self, window):
        win, _, dialogs, config_dir = window
        dialogs.answer_yes = True
        idx = win._profile_combo.findText("Mor")
        win._profile_combo.setCurrentIndex(idx)

        win._on_delete_profile()

        assert "Mor" not in ProfileManager(config_dir=config_dir).get_profiles()

    def test_delete_profile_respects_no(self, window):
        win, _, dialogs, config_dir = window
        dialogs.answer_yes = False
        idx = win._profile_combo.findText("Mor")
        win._profile_combo.setCurrentIndex(idx)

        win._on_delete_profile()

        assert "Mor" in ProfileManager(config_dir=config_dir).get_profiles()
