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


def check_direct_write_allowed() -> tuple[bool, str]:
    """Check whether the LED control file is writable without escalation."""
    if not os.access(LED_CONTROL_PATH, os.W_OK):
        return False, (
            f"{LED_CONTROL_PATH} dosyasına yazma izniniz yok.\n"
            "Udev kuralı kurulu mu ve kullanıcınız 'video' grubunda mı?\n"
            "Eklemek için: sudo usermod -aG video $USER (ardından yeniden oturum açın)"
        )
    return True, "LED dosyasına doğrudan yazılabiliyor."


def describe_blocking_problems() -> list[str]:
    """
    Return only the problems that actually prevent LED control.

    The driver must be present.  Beyond that there are two independent
    ways to write to the LED file – a udev rule that makes it directly
    writable, or pkexec plus the helper script – and one of them is
    enough, so a missing helper is not reported while direct writes work.
    """
    problems: list[str] = []

    driver_ok, driver_msg = check_driver_loaded()
    if not driver_ok:
        return [driver_msg]

    direct_ok, direct_msg = check_direct_write_allowed()
    if direct_ok:
        return problems

    helper_ok, helper_msg = check_helper_installed()
    pkexec_ok, pkexec_msg = check_pkexec_available()
    if helper_ok and pkexec_ok:
        return problems

    problems.append(direct_msg)
    if not pkexec_ok:
        problems.append(pkexec_msg)
    if not helper_ok:
        problems.append(helper_msg)
    return problems
