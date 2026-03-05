# Code Citations

## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.set
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.set
```


## License: unknown
https://github.com/gregkh/usbview/blob/cfbe10e874a576146a2b54ddafcc17022672ab75/org.freedesktop.pkexec.usbview.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled
```


## License: unknown
https://github.com/nkpro2000/my-exr/blob/2a19931f13808c6262ae01b558b8f6b7bcc58131/data/polkit-org.freedesktop.Flatpak.policy

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${src
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${src
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${src
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${src
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${src
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${src
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.w
```


## License: unknown
https://github.com/archlinuxcn/repo/blob/f5daf9488b1a06ddebf1ab05ff8a3aaf15424e38/archlinuxcn/ocrmypdf/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.whl
```


## License: unknown
https://github.com/acxz/pkgbuilds/blob/ae292dc3b0986fa3e303f94d12a3107d2a5b1cf1/python-linear-operator/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.whl
```


## License: unknown
https://github.com/Derrick-L98/study_rust/blob/6adabba8e875db5a4dd750997596ab4bbd73534c/git_demo/RustyTube-master/PKGBUILD

```
# Casper Excalibur Keyboard RGB Linux - Proje Planı

## 1. Proje Dizin Yapısı

````
casper_excalibur_keyboard_rgb_linux/
├── PKGBUILD                          # AUR paketi build dosyası
├── casper-keyboard-rgb.install        # AUR post-install scriptleri
├── LICENSE
├── README.md
├── Makefile
├── setup.py
├── requirements.txt
├── src/
│   ├── __init__.py
│   ├── main.py                       # GUI uygulaması giriş noktası
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py            # Ana pencere (PyQt/GTK)
│   │   ├── color_picker.py           # Renk seçici widget
│   │   ├── zone_selector.py          # Bölge seçici (sol/orta/sağ/tümü)
│   │   ├── brightness_slider.py      # Parlaklık kontrolü
│   │   └── assets/
│   │       ├── icon.png
│   │       ├── keyboard_layout.png
│   │       └── style.qss
│   ├── core/
│   │   ├── __init__.py
│   │   ├── led_controller.py         # LED kontrol mantığı (echo komutu)
│   │   ├── config.py                 # Sabitler (zone kodları, max brightness vb.)
│   │   └── profiles.py              # Renk profili kaydetme/yükleme
│   └── utils/
│       ├── __init__.py
│       ├── permission_handler.py     # pkexec/polkit ile root yetki yönetimi
│       └── validator.py              # Renk kodu doğrulama
├── data/
│   ├── casper-keyboard-rgb.desktop   # .desktop dosyası (uygulama menüsü)
│   ├── casper-keyboard-rgb.svg       # Uygulama ikonu
│   └── org.casper.keyboard.rgb.policy  # Polkit policy (root yetkisi için)
├── systemd/
│   ├── casper-keyboard-rgb-restore.service  # Açılışta son rengi geri yükle
│   └── casper-keyboard-rgb.conf             # Ayar dosyası
├── config/
│   └── profiles.json                 # Varsayılan renk profilleri
└── tests/
    ├── __init__.py
    ├── test_led_controller.py
    ├── test_config.py
    └── test_validator.py
````

---

## 2. Adım Adım Geliştirme Planı

### Adım 1 — Temel LED Kontrol Modülü

````python
# filepath: src/core/config.py

# Zone tanımları (casper-wmi driver'dan)
ZONE_RIGHT = 0x03
ZONE_LEFT = 0x04
ZONE_CENTER = 0x05
ZONE_ALL = 0x06

ZONES = {
    "right": ZONE_RIGHT,
    "left": ZONE_LEFT,
    "center": ZONE_CENTER,
    "all": ZONE_ALL,
}

# Parlaklık seviyeleri
BRIGHTNESS_OFF = 0x00
BRIGHTNESS_MID = 0x01
BRIGHTNESS_MAX = 0x02

MAX_BRIGHTNESS = 2

# LED kontrol dosyası yolu
LED_CONTROL_PATH = "/sys/class/leds/casper::kbd_backlight/led_control"
````

````python
# filepath: src/core/led_controller.py

import subprocess
from src.core.config import LED_CONTROL_PATH, ZONES, MAX_BRIGHTNESS


class LEDController:
    """Casper klavye LED'lerini kontrol eden sınıf."""

    def __init__(self, led_path: str = LED_CONTROL_PATH):
        self.led_path = led_path

    def set_color(self, zone: str, brightness: int, r: int, g: int, b: int) -> bool:
        """
        LED rengini ayarlar.

        Args:
            zone: "all", "left", "center", "right"
            brightness: 0 (kapalı), 1 (orta), 2 (maksimum)
            r, g, b: 0-255 arası renk değerleri

        Returns:
            Başarılı ise True
        """
        if zone not in ZONES:
            raise ValueError(f"Geçersiz bölge: {zone}. Geçerli: {list(ZONES.keys())}")

        if not (0 <= brightness <= MAX_BRIGHTNESS):
            raise ValueError(f"Parlaklık 0-{MAX_BRIGHTNESS} arasında olmalı")

        for val, name in [(r, "R"), (g, "G"), (b, "B")]:
            if not (0 <= val <= 255):
                raise ValueError(f"{name} değeri 0-255 arasında olmalı")

        zone_code = ZONES[zone]
        hex_color = f"{r:02X}{g:02X}{b:02X}"
        command = f"{zone_code}{brightness:02d}{hex_color}"

        try:
            subprocess.run(
                ["pkexec", "tee", self.led_path],
                input=command.encode(),
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            print(f"LED ayarlama hatası: {e}")
            return False

    def turn_off(self) -> bool:
        """Tüm LED'leri kapatır."""
        return self.set_color("all", 0, 0, 0, 0)
````

### Adım 2 — Profil Yönetimi

````python
# filepath: src/core/profiles.py

import json
import os
from pathlib import Path
from typing import Optional

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "casper-keyboard-rgb"
PROFILES_FILE = DEFAULT_CONFIG_DIR / "profiles.json"


class ProfileManager:
    """Renk profillerini kaydetme ve yükleme."""

    def __init__(self, config_dir: Path = DEFAULT_CONFIG_DIR):
        self.config_dir = config_dir
        self.profiles_file = config_dir / "profiles.json"
        self.config_dir.mkdir(parents=True, exist_ok=True)

        if not self.profiles_file.exists():
            self._save_defaults()

    def _save_defaults(self):
        defaults = {
            "profiles": {
                "Kırmızı": {"zone": "all", "brightness": 2, "r": 255, "g": 0, "b": 0},
                "Mavi": {"zone": "all", "brightness": 2, "r": 0, "g": 0, "b": 255},
                "Yeşil": {"zone": "all", "brightness": 2, "r": 0, "g": 255, "b": 0},
                "Beyaz": {"zone": "all", "brightness": 2, "r": 255, "g": 255, "b": 255},
                "Kapalı": {"zone": "all", "brightness": 0, "r": 0, "g": 0, "b": 0},
            },
            "last_used": None,
        }
        self._write(defaults)

    def _read(self) -> dict:
        with open(self.profiles_file, "r") as f:
            return json.load(f)

    def _write(self, data: dict):
        with open(self.profiles_file, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def get_profiles(self) -> dict:
        return self._read()["profiles"]

    def save_profile(self, name: str, zone: str, brightness: int, r: int, g: int, b: int):
        data = self._read()
        data["profiles"][name] = {
            "zone": zone, "brightness": brightness,
            "r": r, "g": g, "b": b,
        }
        self._write(data)

    def delete_profile(self, name: str):
        data = self._read()
        data["profiles"].pop(name, None)
        self._write(data)

    def set_last_used(self, name: str):
        data = self._read()
        data["last_used"] = name
        self._write(data)

    def get_last_used(self) -> Optional[dict]:
        data = self._read()
        last = data.get("last_used")
        if last and last in data["profiles"]:
            return data["profiles"][last]
        return None
````

### Adım 3 — Polkit Policy (Root Yetkisi)

````xml
<!-- filepath: data/org.casper.keyboard.rgb.policy -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE policyconfig PUBLIC
 "-//freedesktop//DTD PolicyKit Policy Configuration 1.0//EN"
 "http://www.freedesktop.org/standards/PolicyKit/1/policyconfig.dtd">
<policyconfig>
  <action id="org.casper.keyboard.rgb.setled">
    <description>Casper Klavye LED Kontrolü</description>
    <message>Klavye LED rengini değiştirmek için yetki gerekli</message>
    <defaults>
      <allow_any>auth_admin</allow_any>
      <allow_inactive>auth_admin</allow_inactive>
      <allow_active>auth_admin_keep</allow_active>
    </defaults>
    <annotate key="org.freedesktop.policykit.exec.path">/usr/bin/tee</annotate>
  </action>
</policyconfig>
````

### Adım 4 — GUI (PyQt6)

````python
# filepath: src/gui/main_window.py

import sys
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QComboBox, QSlider, QLabel, QColorDialog,
    QGroupBox, QMessageBox, QInputDialog,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QIcon

from src.core.led_controller import LEDController
from src.core.profiles import ProfileManager


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.controller = LEDController()
        self.profile_manager = ProfileManager()
        self.current_color = QColor(255, 0, 0)

        self.setWindowTitle("Casper Excalibur Klavye RGB")
        self.setFixedSize(450, 500)

        self._build_ui()
        self._load_profiles()

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # --- Renk Önizleme ---
        self.color_preview = QLabel()
        self.color_preview.setFixedHeight(80)
        self.color_preview.setStyleSheet(
            f"background-color: {self.current_color.name()}; border-radius: 10px;"
        )
        layout.addWidget(self.color_preview)

        # --- Renk Seçici Butonu ---
        pick_btn = QPushButton("🎨 Renk Seç")
        pick_btn.clicked.connect(self._pick_color)
        layout.addWidget(pick_btn)

        # --- Bölge Seçimi ---
        zone_group = QGroupBox("Klavye Bölgesi")
        zone_layout = QHBoxLayout()
        self.zone_combo = QComboBox()
        self.zone_combo.addItems(["Tümü", "Sol", "Orta", "Sağ"])
        zone_layout.addWidget(self.zone_combo)
        zone_group.setLayout(zone_layout)
        layout.addWidget(zone_group)

        # --- Parlaklık ---
        brightness_group = QGroupBox("Parlaklık")
        brightness_layout = QVBoxLayout()
        self.brightness_slider = QSlider(Qt.Orientation.Horizontal)
        self.brightness_slider.setMinimum(0)
        self.brightness_slider.setMaximum(2)
        self.brightness_slider.setValue(2)
        self.brightness_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.brightness_label = QLabel("Maksimum")
        self.brightness_slider.valueChanged.connect(self._on_brightness_change)
        brightness_layout.addWidget(self.brightness_slider)
        brightness_layout.addWidget(self.brightness_label)
        brightness_group.setLayout(brightness_layout)
        layout.addWidget(brightness_group)

        # --- Profiller ---
        profile_group = QGroupBox("Profiller")
        profile_layout = QHBoxLayout()
        self.profile_combo = QComboBox()
        profile_layout.addWidget(self.profile_combo)

        load_btn = QPushButton("Yükle")
        load_btn.clicked.connect(self._load_profile)
        profile_layout.addWidget(load_btn)

        save_btn = QPushButton("Kaydet")
        save_btn.clicked.connect(self._save_profile)
        profile_layout.addWidget(save_btn)

        profile_group.setLayout(profile_layout)
        layout.addWidget(profile_group)

        # --- Uygula / Kapat ---
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("✅ Uygula")
        apply_btn.setStyleSheet("background-color: #4CAF50; color: white; padding: 10px;")
        apply_btn.clicked.connect(self._apply_color)
        btn_layout.addWidget(apply_btn)

        off_btn = QPushButton("⬛ Kapat")
        off_btn.setStyleSheet("background-color: #f44336; color: white; padding: 10px;")
        off_btn.clicked.connect(self._turn_off)
        btn_layout.addWidget(off_btn)

        layout.addLayout(btn_layout)

    def _zone_map(self) -> str:
        mapping = {"Tümü": "all", "Sol": "left", "Orta": "center", "Sağ": "right"}
        return mapping[self.zone_combo.currentText()]

    def _pick_color(self):
        color = QColorDialog.getColor(self.current_color, self, "Renk Seçin")
        if color.isValid():
            self.current_color = color
            self.color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 10px;"
            )

    def _on_brightness_change(self, value):
        labels = {0: "Kapalı", 1: "Orta", 2: "Maksimum"}
        self.brightness_label.setText(labels[value])

    def _apply_color(self):
        success = self.controller.set_color(
            zone=self._zone_map(),
            brightness=self.brightness_slider.value(),
            r=self.current_color.red(),
            g=self.current_color.green(),
            b=self.current_color.blue(),
        )
        if not success:
            QMessageBox.warning(self, "Hata", "LED rengi ayarlanamadı!")

    def _turn_off(self):
        self.controller.turn_off()

    def _load_profiles(self):
        self.profile_combo.clear()
        profiles = self.profile_manager.get_profiles()
        self.profile_combo.addItems(profiles.keys())

    def _load_profile(self):
        name = self.profile_combo.currentText()
        profiles = self.profile_manager.get_profiles()
        if name in profiles:
            p = profiles[name]
            self.current_color = QColor(p["r"], p["g"], p["b"])
            self.color_preview.setStyleSheet(
                f"background-color: {self.current_color.name()}; border-radius: 10px;"
            )
            self.brightness_slider.setValue(p["brightness"])
            zone_reverse = {"all": 0, "left": 1, "center": 2, "right": 3}
            self.zone_combo.setCurrentIndex(zone_reverse.get(p["zone"], 0))

    def _save_profile(self):
        name, ok = QInputDialog.getText(self, "Profil Kaydet", "Profil adı:")
        if ok and name:
            self.profile_manager.save_profile(
                name=name,
                zone=self._zone_map(),
                brightness=self.brightness_slider.value(),
                r=self.current_color.red(),
                g=self.current_color.green(),
                b=self.current_color.blue(),
            )
            self._load_profiles()
````

````python
# filepath: src/main.py

import sys
from PyQt6.QtWidgets import QApplication
from src.gui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Casper Keyboard RGB")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
````

### Adım 5 — Systemd Servisi (Açılışta Renk Geri Yükleme)

````ini
# filepath: systemd/casper-keyboard-rgb-restore.service
[Unit]
Description=Casper Keyboard RGB - Restore last color on boot
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/usr/bin/casper-keyboard-rgb --restore
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
````

### Adım 6 — Desktop Entry

````ini
# filepath: data/casper-keyboard-rgb.desktop
[Desktop Entry]
Name=Casper Keyboard RGB
Comment=Casper Excalibur klavye RGB kontrolü
Exec=casper-keyboard-rgb
Icon=casper-keyboard-rgb
Type=Application
Categories=Utility;Settings;HardwareSettings;
Keywords=keyboard;rgb;led;casper;excalibur;
````

### Adım 7 — Setup & Requirements

````
# filepath: requirements.txt
PyQt6>=6.5.0
````

````python
# filepath: setup.py
from setuptools import setup, find_packages

setup(
    name="casper-keyboard-rgb",
    version="1.0.0",
    description="Casper Excalibur Klavye RGB LED Kontrol Aracı",
    author="jaeger",
    license="GPL-3.0",
    packages=find_packages(),
    install_requires=["PyQt6"],
    entry_points={
        "console_scripts": [
            "casper-keyboard-rgb=src.main:main",
        ],
    },
    data_files=[
        ("/usr/share/applications", ["data/casper-keyboard-rgb.desktop"]),
        ("/usr/share/polkit-1/actions", ["data/org.casper.keyboard.rgb.policy"]),
    ],
    python_requires=">=3.10",
)
````

### Adım 8 — PKGBUILD (AUR Paketi)

````bash
# filepath: PKGBUILD
# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL3')
depends=(
    'python'
    'python-pyqt6'
    'casper-wmi-dkms'
    'polkit'
)
makedepends=('python-setuptools' 'python-build' 'python-installer' 'python-wheel')
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')

build() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"
    python -m installer --destdir="${pkgdir}" dist/*.whl
```

