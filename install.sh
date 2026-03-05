#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Casper Keyboard RGB – Tek Komutla Kurulum Betiği
#
#   curl -sL <repo-url>/install.sh | bash
#   veya
#   ./install.sh
# ──────────────────────────────────────────────────────────────

set -euo pipefail

# ── Renkli çıktı ─────────────────────────────────────────────
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

# ── Root kontrolü ────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ $EUID -eq 0 ]]; then
    fail "Bu betiği root olarak çalıştırmayın. Gerektiğinde sudo isteyecek."
fi

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Casper Excalibur Keyboard RGB – Kurulum Betiği    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── 1. Sistem kontrolü ───────────────────────────────────────
info "Sistem kontrol ediliyor..."

if ! command -v pacman &>/dev/null; then
    fail "Bu betik yalnızca Arch Linux (pacman) için hazırlanmıştır."
fi

# ── 2. Bağımlılıkları kur ────────────────────────────────────
info "Bağımlılıklar kontrol ediliyor..."

DEPS=(
    python
    python-pyqt6
    dkms
    linux-headers
    base-devel
    polkit
)

MISSING=()
for dep in "${DEPS[@]}"; do
    if ! pacman -Qi "$dep" &>/dev/null; then
        MISSING+=("$dep")
    fi
done

if [[ ${#MISSING[@]} -gt 0 ]]; then
    info "Eksik paketler kuruluyor: ${MISSING[*]}"
    sudo pacman -S --needed --noconfirm "${MISSING[@]}"
    ok "Bağımlılıklar kuruldu."
else
    ok "Tüm bağımlılıklar mevcut."
fi

# ── 3. casper-wmi kernel modülü ──────────────────────────────
info "casper-wmi kernel modülü kontrol ediliyor..."

DRIVER_VER="1.0.0"
DRIVER_SRC="${SCRIPT_DIR}/driver"

if lsmod | grep -q casper_wmi; then
    ok "casper-wmi zaten yüklü."
elif [[ -d /usr/src/casper-wmi-* ]]; then
    info "DKMS kaynağı mevcut, modül yükleniyor..."
    sudo modprobe casper-wmi || warn "modprobe başarısız – DKMS build gerekebilir."
else
    info "casper-wmi kuruluyor (gömülü kaynak kodundan)..."

    if [[ ! -f "${DRIVER_SRC}/casper-wmi.c" ]]; then
        fail "driver/casper-wmi.c bulunamadı. Depoyu bütün olarak indirdiğinizden emin olun."
    fi

    # DKMS kaynak dizinini oluştur ve dosyaları kopyala
    sudo mkdir -p "/usr/src/casper-wmi-${DRIVER_VER}"
    sudo cp "${DRIVER_SRC}/casper-wmi.c" "/usr/src/casper-wmi-${DRIVER_VER}/"
    sudo cp "${DRIVER_SRC}/Makefile"     "/usr/src/casper-wmi-${DRIVER_VER}/"
    sudo cp "${DRIVER_SRC}/dkms.conf"    "/usr/src/casper-wmi-${DRIVER_VER}/"

    sudo dkms add -m casper-wmi -v "$DRIVER_VER" 2>/dev/null || true
    sudo dkms build -m casper-wmi -v "$DRIVER_VER"
    sudo dkms install -m casper-wmi -v "$DRIVER_VER"

    sudo modprobe casper-wmi

    ok "casper-wmi kuruldu ve yüklendi (DKMS)."
fi

# Modülün açılışta yüklenmesini sağla
if [[ ! -f /etc/modules-load.d/casper-wmi.conf ]]; then
    echo "casper-wmi" | sudo tee /etc/modules-load.d/casper-wmi.conf >/dev/null
    ok "casper-wmi açılışta otomatik yüklenecek."
fi

# ── 4. LED kontrol dosyasını doğrula ─────────────────────────
LED_CONTROL="/sys/class/leds/casper::kbd_backlight/led_control"

if [[ ! -e "$LED_CONTROL" ]]; then
    fail "LED kontrol dosyası bulunamadı: $LED_CONTROL\nBu bilgisayar Casper Excalibur olmayabilir."
fi

ok "LED kontrol dosyası mevcut."

# ── 5. casper-keyboard-rgb uygulamasını kur ──────────────────
info "Casper Keyboard RGB uygulaması kuruluyor..."

INSTALL_DIR="/opt/casper-keyboard-rgb"

if [[ -d "$INSTALL_DIR" ]]; then
    info "Mevcut kurulum güncelleniyor..."
    sudo rm -rf "$INSTALL_DIR"
fi

sudo mkdir -p "$INSTALL_DIR"
sudo cp -r "${SCRIPT_DIR}/casper_keyboard_rgb" "$INSTALL_DIR/"
sudo cp -r "${SCRIPT_DIR}/data"    "$INSTALL_DIR/"
sudo cp -r "${SCRIPT_DIR}/systemd" "$INSTALL_DIR/"
sudo cp -r "${SCRIPT_DIR}/driver"  "$INSTALL_DIR/"
sudo cp    "${SCRIPT_DIR}/pyproject.toml" "$INSTALL_DIR/" 2>/dev/null || true

# ── 6. Sistem dosyalarını kur ────────────────────────────────
info "Sistem dosyaları kuruluyor..."

# Udev kuralı (şifresiz LED yazma)
sudo install -Dm644 "$INSTALL_DIR/data/99-casper-kbd-backlight.rules" \
    /usr/lib/udev/rules.d/99-casper-kbd-backlight.rules

# Polkit policy (fallback için)
sudo install -Dm644 "$INSTALL_DIR/data/org.casper.keyboard.rgb.policy" \
    /usr/share/polkit-1/actions/org.casper.keyboard.rgb.policy

# Helper script (fallback için)
sudo install -Dm755 "$INSTALL_DIR/data/led-write-helper" \
    /usr/lib/casper-keyboard-rgb/led-write-helper

# Desktop entry
sudo install -Dm644 "$INSTALL_DIR/data/casper-keyboard-rgb.desktop" \
    /usr/share/applications/casper-keyboard-rgb.desktop

# Systemd service
sudo install -Dm644 "$INSTALL_DIR/systemd/casper-keyboard-rgb-restore.service" \
    /usr/lib/systemd/system/casper-keyboard-rgb-restore.service

# Udev kurallarını yeniden yükle
sudo udevadm control --reload-rules
sudo udevadm trigger

ok "Sistem dosyaları kuruldu."

# ── 7. Launcher script oluştur ───────────────────────────────
sudo tee /usr/local/bin/casper-keyboard-rgb >/dev/null << 'LAUNCHER'
#!/bin/bash
cd /opt/casper-keyboard-rgb
exec python -m casper_keyboard_rgb.main "$@"
LAUNCHER
sudo chmod 755 /usr/local/bin/casper-keyboard-rgb

ok "casper-keyboard-rgb komutu oluşturuldu."

# ── 8. Systemd servisini etkinleştir ─────────────────────────
sudo systemctl enable casper-keyboard-rgb-restore.service 2>/dev/null
ok "Açılışta renk geri yükleme servisi etkinleştirildi."

# ── 9. LED izinlerini hemen uygula ───────────────────────────
sudo chgrp video "$LED_CONTROL" 2>/dev/null || true
sudo chmod 0660 "$LED_CONTROL" 2>/dev/null || true

# ── Bitti ─────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║          Kurulum başarıyla tamamlandı!               ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║  Kullanım:                                           ║${NC}"
echo -e "${GREEN}${BOLD}║    casper-keyboard-rgb           → GUI başlat        ║${NC}"
echo -e "${GREEN}${BOLD}║    casper-keyboard-rgb --restore  → Son rengi yükle  ║${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║  Veya uygulama menüsünden:                           ║${NC}"
echo -e "${GREEN}${BOLD}║    'Casper Keyboard RGB' arayın                      ║${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
