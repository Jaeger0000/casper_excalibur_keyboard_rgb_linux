"""
LED Controller – writes colour commands to the casper-wmi sysfs interface.

Write strategy (in order of preference)
───────────────────────────────────────
1. **Direct write** – works when a udev rule (``99-casper-kbd-backlight.rules``)
   grants the logged-in user write access to the sysfs LED control file.
   No privilege escalation needed.

2. **Polkit helper** – fallback when the udev rule is not installed.
   A dedicated helper script at a fixed path is called via ``pkexec``.
   The helper validates the data format with a strict regex and only
   writes to the one hard-coded LED control file.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
from typing import Final

from casper_keyboard_rgb.core.config import (
    HELPER_SCRIPT_PATH,
    LED_CONTROL_PATH,
    MAX_BRIGHTNESS,
    MIN_BRIGHTNESS,
    Brightness,
    RGBColor,
    Zone,
    ZONE_LABELS,
    validate_led_path,
)

logger = logging.getLogger(__name__)

# Strict pattern: <zone 1 digit><brightness 2 digits><RRGGBB 6 hex chars>
_COMMAND_RE: Final[re.Pattern[str]] = re.compile(r"^[3-6](0[0-2])[0-9A-Fa-f]{6}$")


class LEDControllerError(Exception):
    """Base exception for LED control failures."""


class LEDController:
    """
    Controls Casper keyboard LEDs via the casper-wmi sysfs interface.

    Tries direct write first (works with udev rule or root).
    Falls back to Polkit helper if direct write fails with PermissionError.

    Parameters
    ----------
    led_path : str
        Sysfs path to the ``led_control`` file.
        Defaults to the standard casper-wmi path.
    """

    def __init__(
        self,
        led_path: str = LED_CONTROL_PATH,
    ) -> None:
        self._led_path = led_path

    # ── public API ────────────────────────────

    def set_color(
        self,
        zone: str | Zone,
        brightness: int | Brightness,
        color: RGBColor,
    ) -> None:
        """
        Set the keyboard LED colour.

        Parameters
        ----------
        zone : str or Zone
            ``"all"``, ``"left"``, ``"center"``, ``"right"`` or a Zone enum.
        brightness : int or Brightness
            0 (off) / 1 (mid) / 2 (max).
        color : RGBColor
            Validated RGB colour.

        Raises
        ------
        ValueError
            On invalid zone or brightness.
        LEDControllerError
            On write failure.
        """
        zone_enum = self._resolve_zone(zone)
        brightness_int = self._resolve_brightness(brightness)
        command = self._build_command(zone_enum, brightness_int, color)
        self._write(command)
        logger.info(
            "LED set: zone=%s brightness=%d color=#%s",
            zone_enum.name,
            brightness_int,
            color.to_hex(),
        )

    def turn_off(self) -> None:
        """Turn off all keyboard LEDs."""
        self.set_color(Zone.ALL, Brightness.OFF, RGBColor(0, 0, 0))

    # ── private helpers ───────────────────────

    @staticmethod
    def _resolve_zone(zone: str | Zone) -> Zone:
        if isinstance(zone, Zone):
            return zone
        key = str(zone).lower().strip()
        if key not in ZONE_LABELS:
            raise ValueError(
                f"Geçersiz bölge: {zone!r}. Geçerli: {list(ZONE_LABELS)}"
            )
        return ZONE_LABELS[key]

    @staticmethod
    def _resolve_brightness(brightness: int | Brightness) -> int:
        val = int(brightness)
        if not (MIN_BRIGHTNESS <= val <= MAX_BRIGHTNESS):
            raise ValueError(
                f"Parlaklık {MIN_BRIGHTNESS}-{MAX_BRIGHTNESS} arasında olmalı, "
                f"verilen: {val}"
            )
        return val

    @staticmethod
    def _build_command(zone: Zone, brightness: int, color: RGBColor) -> str:
        """Build the raw command string and validate it."""
        cmd = f"{zone.value}{brightness:02d}{color.to_hex()}"
        if not _COMMAND_RE.match(cmd):
            # Should never happen if inputs passed validation above,
            # but defence-in-depth is good practice.
            raise LEDControllerError(f"Oluşturulan komut doğrulanamadı: {cmd!r}")
        return cmd

    def _write(self, command: str) -> None:
        """Write the command string to the LED control file.

        Strategy: try direct write first (fast, no popup).
        If permission denied, fall back to the Polkit helper.
        """
        try:
            self._write_direct(command)
            return
        except LEDControllerError as direct_err:
            if "yazma yetkisi" not in str(direct_err):
                raise  # not a permission issue – re-raise immediately
            logger.debug("Doğrudan yazma başarısız, helper deneniyor: %s", direct_err)

        self._write_via_helper(command)

    def _write_via_helper(self, command: str) -> None:
        """Use the Polkit-authorised helper for privilege escalation."""
        helper = HELPER_SCRIPT_PATH

        if not os.path.isfile(helper):
            raise LEDControllerError(
                f"Yardımcı betik bulunamadı: {helper}\n"
                "Paket düzgün kurulmamış olabilir."
            )

        # Verify the helper is owned by root and not world-writable
        st = os.stat(helper)
        if st.st_uid != 0:
            raise LEDControllerError(
                f"Güvenlik hatası: {helper} root'a ait değil (uid={st.st_uid})"
            )
        if st.st_mode & 0o002:
            raise LEDControllerError(
                f"Güvenlik hatası: {helper} herkes tarafından yazılabilir"
            )

        pkexec = shutil.which("pkexec")
        if pkexec is None:
            raise LEDControllerError(
                "pkexec bulunamadı. polkit paketi yüklü mü?"
            )

        try:
            result = subprocess.run(
                [pkexec, helper, command],
                capture_output=True,
                timeout=30,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise LEDControllerError("pkexec zaman aşımına uğradı") from exc

        if result.returncode != 0:
            stderr = result.stderr.decode(errors="replace").strip()
            raise LEDControllerError(
                f"LED yazma başarısız (exit {result.returncode}): {stderr}"
            )

    def _write_direct(self, command: str) -> None:
        """Write directly – works with udev rule or when running as root."""
        try:
            path = validate_led_path(self._led_path)
        except (FileNotFoundError, PermissionError) as exc:
            raise LEDControllerError(str(exc)) from exc

        try:
            with open(path, "w") as fp:
                fp.write(command)
        except PermissionError as exc:
            raise LEDControllerError(
                "Doğrudan yazma yetkisi yok. "
                "Programı root olarak çalıştırın veya helper modunu kullanın."
            ) from exc
        except OSError as exc:
            raise LEDControllerError(f"LED dosyasına yazılamadı: {exc}") from exc
