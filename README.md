# Casper Excalibur Keyboard RGB for Linux

Casper Excalibur dizüstü bilgisayarların klavye RGB LED'lerini Linux üzerinde kontrol etmek için bir GUI uygulaması.

[casper-wmi](https://github.com/Mustafa-eksi/casper-wmi) kernel modülünü kullanır.

## Özellikler

- **GUI renk seçici** – tıkla, seç, uygula
- **Bölge kontrolü** – tüm klavye veya sol / orta / sağ ayrı ayrı
- **3 kademeli parlaklık** – kapalı / orta / maksimum
- **Profil kaydetme** – sık kullandığın renkleri kaydet
- **Açılışta geri yükleme** – systemd servisi ile son rengi hatırla
- **Güvenli** – ayrıcalık yükseltme Polkit + dedicated helper ile

## Gereksinimler

- [casper-wmi](https://github.com/Mustafa-eksi/casper-wmi) kernel modülü
- Python 3.10+
- PyQt6
- polkit

## Kurulum

### AUR (Arch Linux)

```bash
# AUR helper ile
yay -S casper-keyboard-rgb

# veya elle
git clone https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux.git
cd casper_excalibur_keyboard_rgb_linux
makepkg -si
```

### Elle Kurulum

```bash
pip install -e .
sudo make install-system
```

## Kullanım

### GUI

```bash
casper-keyboard-rgb
```

### Açılışta Otomatik Geri Yükleme

```bash
sudo systemctl enable casper-keyboard-rgb-restore.service
```

## Mimarisi

```
src/
├── main.py                    # Entry point (GUI + --restore CLI)
├── core/
│   ├── config.py              # Sabitler, RGBColor, doğrulama
│   ├── led_controller.py      # LED yazma (Polkit helper üzerinden)
│   └── profiles.py            # JSON profil yönetimi
├── gui/
│   ├── main_window.py         # Ana pencere
│   ├── color_picker.py        # Renk seçici widget
│   ├── zone_selector.py       # Bölge seçici
│   └── brightness_slider.py   # Parlaklık slider
└── utils/
    ├── permission_handler.py  # Ön kontroller
    └── validator.py           # Girdi doğrulama
```

## Güvenlik Modeli

Uygulama **asla root olarak çalışmaz**. Root yetkisi gerektiren tek işlem – sysfs'e yazma – ayrı bir helper betiği (`/usr/lib/casper-keyboard-rgb/led-write-helper`) üzerinden yapılır:

1. Helper yalnızca sabit `led_control` dosyasına yazar
2. Veri formatı strict regex ile doğrulanır
3. Helper root'a ait, `0755` izinli
4. Polkit policy yalnızca bu helper'ı yetkilendirir
5. Symlink saldırıları `readlink -f` + `/sys/` prefix kontrolü ile önlenir

## Geliştirme

```bash
# Testler
make test

# Çalıştır
make run
```

## Lisans

GPL-3.0-or-later
