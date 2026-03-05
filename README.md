# Casper Excalibur Keyboard RGB for Linux

Casper Excalibur dizüstü bilgisayarların klavye RGB LED'lerini Linux üzerinde kontrol etmek için bir GUI uygulaması.

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

### AUR (Önerilen)

```bash
yay -S casper-keyboard-rgb
```

Tek komut. Gerisini paket yöneticisi halleder:
- casper-wmi kernel modülünü DKMS ile derler ve yükler
- Udev kuralını kurar (şifresiz LED kontrolü)
- Uygulama menüsüne kısayol ekler
- Systemd servisini kurar (açılışta son renki geri yükleme)

### Manuel Kurulum

```bash
git clone https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux.git
cd casper_excalibur_keyboard_rgb_linux
./install.sh
```

### Kaldırma

```bash
# AUR ile kuruldu ise:
yay -Rns casper-keyboard-rgb

# Manuel kuruldu ise:
./uninstall.sh
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
```

## Güvenlik Modeli

Uygulama **asla root olarak çalışmaz**. LED dosyasına yazma izni udev kuralı ile sağlanır:

1. Udev kuralı LED kontrol dosyasını `0666` izinli yapar (şifresiz erişim)
2. Fallback olarak Polkit + dedicated helper betik kullanılır
3. Veri formatı strict regex ile doğrulanır
4. Symlink saldırıları `readlink -f` + `/sys/` prefix kontrolü ile önlenir

## Geliştirme

```bash
# Testler
make test

# Çalıştır
make run
```

## AUR'a Yayınlama (Geliştirici İçin)

```bash
# AUR SSH key ayarlı olmalı: https://aur.archlinux.org/account
./publish-aur.sh
```

Bu betik otomatik olarak:
1. GitHub'da `v1.0.1` tag'i oluşturur (yoksa)
2. AUR deposunu klonlar
3. PKGBUILD ve .install dosyalarını kopyalar
4. `.SRCINFO` oluşturur
5. AUR'a push eder

## Lisans

GPL-3.0-or-later
