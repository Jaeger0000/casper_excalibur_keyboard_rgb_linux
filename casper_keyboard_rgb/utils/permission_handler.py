"""
Permission handler – checks runtime prerequisites and driver availability.
"""

from __future__ import annotations

import logging
import os
import shutil

from casper_keyboard_rgb.core.config import HELPER_SCRIPT_PATH, LED_CONTROL_PATH

logger = logging.getLogger(__name__)


def check_driver_loaded() -> tuple[bool, str]:
    """
    Check whether the casper-wmi kernel module is loaded and the
    sysfs LED control file exists.

    Returns
    -------
    (ok, message)
        *ok* is True when everything looks good.
    """
    led_dir = os.path.dirname(LED_CONTROL_PATH)

    if not os.path.isdir(led_dir):
        return False, (
            "casper-wmi sürücüsü yüklü değil.\n"
            "Kurulum: https://github.com/Mustafa-eksi/casper-wmi\n"
            f"Beklenen dizin: {led_dir}"
        )

    if not os.path.exists(LED_CONTROL_PATH):
        return False, (
            f"LED kontrol dosyası bulunamadı: {LED_CONTROL_PATH}\n"
            "casper-wmi modülü düzgün yüklenmemiş olabilir."
        )

    return True, "Sürücü hazır."


def check_pkexec_available() -> tuple[bool, str]:
    """Check that pkexec (polkit) is available on the system."""
    if shutil.which("pkexec") is None:
        return False, (
            "pkexec bulunamadı.\n"
            "polkit paketini yükleyin: sudo pacman -S polkit"
        )
    return True, "pkexec mevcut."


def check_helper_installed() -> tuple[bool, str]:
    """Check that the privilege-escalation helper script is installed."""
    if not os.path.isfile(HELPER_SCRIPT_PATH):
        return False, (
            f"Yardımcı betik bulunamadı: {HELPER_SCRIPT_PATH}\n"
            "Paketi yeniden kurmayı deneyin."
        )

    st = os.stat(HELPER_SCRIPT_PATH)
    if st.st_uid != 0:
        return False, (
            f"{HELPER_SCRIPT_PATH} root'a ait değil (uid={st.st_uid}).\n"
            "Güvenlik riski – paketi yeniden kurun."
        )

    return True, "Yardımcı betik kurulu."


def run_preflight_checks() -> list[tuple[bool, str]]:
    """Run all preflight checks and return results."""
    return [
        check_driver_loaded(),
        check_pkexec_available(),
        check_helper_installed(),
    ]
