"""
Profile manager – persists user colour profiles to a JSON file.

Security notes
──────────────
- Profile data is stored in ``~/.config/casper-keyboard-rgb/profiles.json``.
- File permissions are set to 0600 on creation (user-only read/write).
- All values loaded from disk are re-validated before use.
- An ``fcntl`` advisory lock prevents concurrent writes from multiple
  GUI instances or the systemd restore service.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterator, Optional

from casper_keyboard_rgb.core.config import (
    BRIGHTNESS_LABELS,
    CONFIG_DIR,
    MAX_BRIGHTNESS,
    MIN_BRIGHTNESS,
    PROFILES_FILE,
    RGBColor,
    ZONE_LABELS,
)

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Data model
# ──────────────────────────────────────────────

@dataclass(frozen=True, slots=True)
class Profile:
    """A single LED colour profile."""

    zone: str
    brightness: int
    r: int
    g: int
    b: int

    def __post_init__(self) -> None:
        if self.zone not in ZONE_LABELS:
            raise ValueError(f"Geçersiz bölge: {self.zone!r}")
        if not (MIN_BRIGHTNESS <= self.brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Geçersiz parlaklık: {self.brightness}")
        # Delegate channel validation to RGBColor
        RGBColor(self.r, self.g, self.b)

    @property
    def color(self) -> RGBColor:
        return RGBColor(self.r, self.g, self.b)


# ──────────────────────────────────────────────
# Default profiles shipped with the application
# ──────────────────────────────────────────────
_DEFAULTS: dict[str, dict] = {
    "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
    "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
    "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
    "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
    "Mor": {"zone": "all", "brightness": 2, "r": 128, "g": 0, "b": 255},
    "Turuncu": {"zone": "all", "brightness": 2, "r": 255, "g": 165, "b": 0},
    "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
}


# ──────────────────────────────────────────────
# Profile manager
# ──────────────────────────────────────────────

class ProfileManager:
    """
    Thread-safe, file-locked profile store.

    Parameters
    ----------
    config_dir : Path
        Directory where ``profiles.json`` is stored.
    """

    def __init__(self, config_dir: Path = CONFIG_DIR) -> None:
        self._config_dir = config_dir
        self._profiles_file = config_dir / "profiles.json"
        self._ensure_storage()

    # ── public API ────────────────────────────

    def get_profiles(self) -> dict[str, Profile]:
        """Return all saved profiles."""
        data = self._read()
        out: dict[str, Profile] = {}
        for name, raw in data.get("profiles", {}).items():
            try:
                out[name] = Profile(**raw)
            except (TypeError, ValueError) as exc:
                logger.warning("Profil '%s' atlandı (geçersiz): %s", name, exc)
        return out

    def save_profile(
        self,
        name: str,
        zone: str,
        brightness: int,
        color: RGBColor,
    ) -> None:
        """Create or overwrite a named profile."""
        # Validate by constructing a Profile – raises on bad input
        profile = Profile(
            zone=zone,
            brightness=brightness,
            r=color.r,
            g=color.g,
            b=color.b,
        )
        with self._locked_update() as data:
            data["profiles"][name] = asdict(profile)

    def delete_profile(self, name: str) -> bool:
        """Delete a profile by name.  Returns True if it existed."""
        with self._locked_update() as data:
            return data["profiles"].pop(name, None) is not None

    def set_last_used(self, name: str) -> None:
        """Record the name of the last-applied profile."""
        with self._locked_update() as data:
            data["last_used"] = name

    def get_last_used(self) -> Optional[Profile]:
        """Return the last-applied profile, or None."""
        data = self._read()
        last = data.get("last_used")
        if last and last in data.get("profiles", {}):
            try:
                return Profile(**data["profiles"][last])
            except (TypeError, ValueError):
                return None
        return None

    def get_last_used_name(self) -> Optional[str]:
        """Return the name of the last-applied profile, or None."""
        data = self._read()
        return data.get("last_used")

    # ── private helpers ───────────────────────

    def _ensure_storage(self) -> None:
        """Create config dir and seed defaults if needed."""
        self._config_dir.mkdir(parents=True, exist_ok=True)

        if not self._profiles_file.exists():
            initial = {"profiles": _DEFAULTS, "last_used": None}
            self._write_atomic(initial)
            logger.info("Varsayılan profiller oluşturuldu: %s", self._profiles_file)

    def _read(self) -> dict:
        """Read and parse the JSON file."""
        try:
            text = self._profiles_file.read_text(encoding="utf-8")
            return json.loads(text)
        except (json.JSONDecodeError, OSError) as exc:
            logger.error("Profil dosyası okunamadı: %s", exc)
            return {"profiles": {}, "last_used": None}

    def _write_atomic(self, data: dict) -> None:
        """
        Write JSON data atomically.

        Writes to a temporary file and renames, so readers never see
        a partially-written file.  File permissions are 0600.
        """
        tmp_path = self._profiles_file.with_suffix(".tmp")
        try:
            with open(tmp_path, "w", encoding="utf-8") as fp:
                json.dump(data, fp, indent=2, ensure_ascii=False)
            os.chmod(tmp_path, 0o600)
            os.replace(tmp_path, self._profiles_file)
        except OSError as exc:
            logger.error("Profil dosyası yazılamadı: %s", exc)
            # Clean up temp file if rename failed
            tmp_path.unlink(missing_ok=True)
            raise

    @contextmanager
    def _locked_update(self) -> Iterator[dict]:
        """
        Context manager that reads data, yields it for mutation,
        then writes it back under an advisory file lock.
        """
        lock_path = self._profiles_file.with_suffix(".lock")
        lock_path.touch(exist_ok=True)

        with open(lock_path, "w") as lock_fp:
            fcntl.flock(lock_fp, fcntl.LOCK_EX)
            try:
                data = self._read()
                yield data
                self._write_atomic(data)
            finally:
                fcntl.flock(lock_fp, fcntl.LOCK_UN)
