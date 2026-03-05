#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Casper Keyboard RGB – Kaldırma Betiği
# ──────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info() { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()   { echo -e "${GREEN}[  OK]${NC} $*"; }

if [[ $EUID -eq 0 ]]; then
    echo -e "${RED}[FAIL]${NC} Bu betiği root olarak çalıştırmayın."
    exit 1
fi

echo ""
echo -e "${BOLD}Casper Keyboard RGB kaldırılıyor...${NC}"
echo ""

# Systemd servisi
sudo systemctl disable casper-keyboard-rgb-restore.service 2>/dev/null || true
sudo rm -f /usr/lib/systemd/system/casper-keyboard-rgb-restore.service
ok "Systemd servisi kaldırıldı."

# Sistem dosyaları
sudo rm -f /usr/lib/udev/rules.d/99-casper-kbd-backlight.rules
sudo rm -f /usr/share/polkit-1/actions/org.casper.keyboard.rgb.policy
sudo rm -f /usr/share/applications/casper-keyboard-rgb.desktop
sudo rm -rf /usr/lib/casper-keyboard-rgb/
sudo rm -f /usr/local/bin/casper-keyboard-rgb
ok "Sistem dosyaları kaldırıldı."

# Udev yeniden yükle
sudo udevadm control --reload-rules 2>/dev/null || true

# Uygulama dizini
sudo rm -rf /opt/casper-keyboard-rgb
ok "Uygulama dizini kaldırıldı."

# casper-wmi kernel modülü (isteğe bağlı)
echo ""
read -rp "casper-wmi kernel modülünü de kaldırmak ister misiniz? [e/H] " remove_driver
if [[ "${remove_driver,,}" == "e" ]]; then
    DRIVER_VER="1.0.0"
    sudo modprobe -r casper-wmi 2>/dev/null || true
    sudo dkms remove -m casper-wmi -v "$DRIVER_VER" --all 2>/dev/null || true
    sudo rm -rf "/usr/src/casper-wmi-${DRIVER_VER}"
    sudo rm -f /etc/modules-load.d/casper-wmi.conf
    ok "casper-wmi kernel modülü kaldırıldı."
else
    info "casper-wmi kernel modülü korundu."
fi

echo ""
echo -e "${GREEN}Kaldırma tamamlandı.${NC}"
echo -e "Kullanıcı ayarları korundu: ${CYAN}~/.config/casper-keyboard-rgb/${NC}"
echo -e "Silmek için: rm -rf ~/.config/casper-keyboard-rgb/"
echo ""
