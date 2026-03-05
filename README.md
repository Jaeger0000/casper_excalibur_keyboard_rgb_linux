# Casper Excalibur Keyboard RGB for Linux

Casper Excalibur dizüstü bilgisayarların klavye RGB LED'lerini Linux üzerinde kontrol etmek için hafif, Rust tabanlı (GTK4/libadwaita) bir GUI uygulaması.

Önceki Python sürümü yerine, daha düşük kaynak tüketimi (yaklaşık 4 MB) ve native görünüm sunması için tamamen Rust ve GTK4 kullanılarak yeniden yazılmıştır.

## Teşekkürler

Bu proje, **[Mustafa Ekşi](https://github.com/Mustafa-eksi)** tarafından geliştirilen
[casper-wmi](https://github.com/Mustafa-eksi/casper-wmi) kernel modülünü içerir.
Kernel modülünün kaynak kodu `driver/` dizininde gömülü olarak bulunmaktadır ve
GPL-2.0-or-later lisansı altında dağıtılmaktadır.

## Özellikler

- **Modern GTK4 GUI** – Native görünümlü, hafif ve hızlı.
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
- Rust (Cargo) ile programı derler
- casper-wmi kernel modülünü DKMS ile derler ve yükler
- Udev kuralını kurar (şifresiz LED kontrolü)
- Uygulama menüsüne kısayol ekler
- Systemd servisini kurar (açılışta son renki geri yükleme)

### Manuel Kurulum (Geliştirici)

Sisteminizde `rust` (`cargo`), `gtk4` ve `libadwaita` geliştirme paketleri yüklü olmalıdır.

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

## Geliştirme ve Derleme (Cargo)

Projeyi kendi ortamınızda test etmek veya derlemek için:

```bash
cd casper-keyboard-rgb
cargo build --release
```

## Lisans

GPL-3.0-or-later