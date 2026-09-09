# Casper Excalibur Keyboard RGB for Linux

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![AUR](https://img.shields.io/aur/version/casper-keyboard-rgb)](https://aur.archlinux.org/packages/casper-keyboard-rgb)
[![GitHub Release](https://img.shields.io/github/v/release/Jaeger0000/casper_excalibur_keyboard_rgb_linux)](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/releases)
[![CI](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/actions/workflows/ci.yml/badge.svg)](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/actions)

Casper Excalibur dizüstü bilgisayarların klavye RGB LED'lerini Linux üzerinde kontrol etmek için bir GUI uygulaması.

> **English summary:** A GUI application to control keyboard RGB LEDs on Casper Excalibur laptops under Linux. Supports per-zone color control, brightness levels, profile saving, and automatic restore on boot.

## Teşekkürler 

Bu proje, **[Mustafa Ekşi](https://github.com/Mustafa-eksi)** tarafından geliştirilen
[casper-wmi](https://github.com/Mustafa-eksi/casper-wmi) kernel modülünü içerir.
Kernel modülünün kaynak kodu `driver/` dizininde gömülü olarak bulunmaktadır ve
GPL-2.0-or-later lisansı altında dağıtılmaktadır.

## Özellikler

- **GUI renk seçici** – tıkla, seç, uygula
- **Bölge kontrolü** – tüm klavye veya sol / orta / sağ ayrı ayrı
- **3 kademeli parlaklık** – kapalı / orta / maksimum
- **Profil kaydetme** – sık kullandığın renkleri kaydet
- **Açılışta geri yükleme** – systemd servisi ile son rengi hatırla
- **Güvenli** – ayrıcalık yükseltme Polkit + dedicated helper ile

## Kurulum

### Arch Linux – AUR (Önerilen)

```bash
yay -S casper-keyboard-rgb
```

Tek komut. Gerisini paket yöneticisi halleder:
- casper-wmi kernel modülünü DKMS ile derler ve yükler
- Udev kuralını kurar (şifresiz LED kontrolü)
- Uygulama menüsüne kısayol ekler
- Systemd servisini kurar (açılışta son rengi geri yükleme)

### Debian / Ubuntu (.deb)

[Releases](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/releases)
sayfasında bir `.deb` varsa indirip kurabilirsiniz:

```bash
sudo apt install ./casper-keyboard-rgb_<sürüm>-1_amd64.deb
```

Yoksa paketi kendiniz üretin – sürüm `pyproject.toml`'dan okunur:

```bash
git clone https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux.git
cd casper_excalibur_keyboard_rgb_linux
./build-deb.sh
sudo apt install ./casper-keyboard-rgb_*_amd64.deb
```

### Manuel Kurulum (Arch Linux)

```bash
git clone https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux.git
cd casper_excalibur_keyboard_rgb_linux
./install.sh
```

### Kaldırma

```bash
# AUR ile kuruldu ise:
yay -Rns casper-keyboard-rgb

# Debian/Ubuntu ile kuruldu ise:
sudo apt remove casper-keyboard-rgb

# Manuel kuruldu ise:
./uninstall.sh
```

## Kullanım

### GUI

```bash
casper-keyboard-rgb
```

Veya uygulama menüsünden **"Casper Keyboard RGB"** olarak arayın.

### CLI

```bash
# Son kaydedilen renk profilini geri yükle
casper-keyboard-rgb --restore
```

### Açılışta Otomatik Geri Yükleme

```bash
sudo systemctl enable casper-keyboard-rgb-restore.service
```

Uygulamada her "Uygula" işleminde son renk, bölge ve parlaklık kaydedilir;
servis açılışta bunu geri yükler. Kaydedilmiş bir renk yoksa (temiz kurulum)
servis sessizce çıkar.

## Proje Yapısı

```
driver/
├── casper-wmi.c               # Kernel modülü (Mustafa Ekşi, GPL-2.0)
├── Makefile                   # Kernel build dosyası
└── dkms.conf                  # DKMS yapılandırması

casper_keyboard_rgb/
├── main.py                    # Entry point (GUI + --restore CLI)
├── core/
│   ├── config.py              # Sabitler, RGBColor, doğrulama
│   ├── led_controller.py      # LED yazma (direkt + Polkit fallback)
│   └── profiles.py            # JSON profil yönetimi
├── gui/
│   ├── main_window.py         # Ana pencere
│   ├── color_picker.py        # Renk seçici widget
│   ├── zone_selector.py       # Bölge seçici
│   └── brightness_slider.py   # Parlaklık slider
└── utils/
    ├── permission_handler.py  # Ön kontroller
    └── validator.py           # Girdi doğrulama

tests/                         # pytest paketi (çekirdek + GUI + restore)
```

## Güvenlik Modeli

Uygulama **asla root olarak çalışmaz**. LED dosyasına yazma izni udev kuralı ile sağlanır:

1. Udev kuralı LED kontrol dosyasını `video` grubuna atar ve `0660` izinli yapar (gruba dahil kullanıcılar için şifresiz erişim)
2. Fallback olarak Polkit + dedicated helper betik kullanılır
3. Veri formatı strict regex ile doğrulanır
4. Symlink saldırıları `readlink -f` + `/sys/` prefix kontrolü ile önlenir

> **Şifresiz kontrol için:** kullanıcınız `video` grubunda olmalı. Değilse her
> renk değişiminde Polkit parola sorar. Kontrol etmek ve eklemek için:
>
> ```bash
> id -nG | grep -q video || sudo usermod -aG video "$USER"
> ```
>
> Değişiklik oturumu kapatıp açtıktan sonra geçerli olur.

## Katkıda Bulunma

Katkılarınız memnuniyetle karşılanır! Lütfen aşağıdaki adımları izleyin:

1. Bu repoyu **fork** edin
2. Feature branch oluşturun (`git checkout -b feature/amazing-feature`)
3. Değişikliklerinizi commit edin (`git commit -m 'feat: add amazing feature'`)
4. Branch'inizi push edin (`git push origin feature/amazing-feature`)
5. **Pull Request** açın

### Geliştirme Ortamı

```bash
git clone https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux.git
cd casper_excalibur_keyboard_rgb_linux
make install-dev   # pip install -e ".[dev]" – test ve lint araçlarıyla
make test          # Testleri çalıştır
make lint          # flake8 + mypy
make run           # Uygulamayı başlat
make -C driver     # Kernel modülünü derle (linux-headers gerekir)
```

## Sorun Bildirme

Bir hata bulduysanız veya öneriniz varsa [Issues](https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/issues) sayfasından bildirebilirsiniz.

Lütfen şunları ekleyin:
- Linux dağıtımı ve sürümü
- Casper Excalibur model numarası
- `uname -r` çıktısı
- Hatanın nasıl tekrarlanacağı

## Lisans

Bu proje [GPL-3.0-or-later](LICENSE) lisansı ile lisanslanmıştır.

Gömülü `casper-wmi` kernel modülü [GPL-2.0-or-later](https://www.gnu.org/licenses/old-licenses/gpl-2.0.html) lisansı altındadır (© Mustafa Ekşi).
