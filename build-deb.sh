#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Casper Keyboard RGB – Debian Paketi Oluşturma Betiği
#
# Kullanım:
#   ./build-deb.sh
#
# Çıktı:
#   casper-keyboard-rgb_1.0.1-1_amd64.deb
# ──────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_NAME="casper-keyboard-rgb"
PKG_VERSION="1.0.1"
PKG_REL="1"
ARCH="amd64"
DEB_NAME="${PKG_NAME}_${PKG_VERSION}-${PKG_REL}_${ARCH}"
BUILD_DIR="${SCRIPT_DIR}/deb-build/${DEB_NAME}"

echo ""
echo -e "${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${BOLD}║   Casper Keyboard RGB – Debian Paketi Oluşturucu    ║${NC}"
echo -e "${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""

# ── Temizle ──────────────────────────────────────────────────
info "Önceki build temizleniyor..."
rm -rf "${SCRIPT_DIR}/deb-build"
mkdir -p "${BUILD_DIR}"

# ── DEBIAN kontrol dosyaları ─────────────────────────────────
info "DEBIAN kontrol dosyaları oluşturuluyor..."

mkdir -p "${BUILD_DIR}/DEBIAN"

cat > "${BUILD_DIR}/DEBIAN/control" << EOF
Package: ${PKG_NAME}
Version: ${PKG_VERSION}-${PKG_REL}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3 (>= 3.10), python3-pyqt6, dkms, policykit-1
Recommends: linux-headers-generic
Maintainer: Jaeger <https://github.com/Jaeger0000>
Homepage: https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux
Description: Casper Excalibur Keyboard RGB LED Control Tool
 A GUI application to control keyboard RGB LEDs on Casper Excalibur
 laptops under Linux. Supports per-zone color control, brightness
 levels, profile saving, and automatic restore on boot.
 .
 Features:
  - GUI color picker with per-zone control (left/center/right/all)
  - 3-level brightness control (off/medium/maximum)
  - Profile saving and loading
  - Automatic color restore on boot via systemd service
  - Secure design: never runs as root, uses udev + Polkit
EOF

# ── postinst (kurulum sonrası) ───────────────────────────────
cat > "${BUILD_DIR}/DEBIAN/postinst" << 'EOF'
#!/bin/bash
set -e

# DKMS: casper-wmi kernel modülünü kur
DRIVER_VER="1.0.0"
if command -v dkms &>/dev/null; then
    dkms add -m casper-wmi -v "$DRIVER_VER" 2>/dev/null || true
    dkms build -m casper-wmi -v "$DRIVER_VER" 2>/dev/null || true
    dkms install -m casper-wmi -v "$DRIVER_VER" 2>/dev/null || true
fi

# Modülü yükle
modprobe casper-wmi 2>/dev/null || true

# Udev kurallarını yeniden yükle
udevadm control --reload-rules 2>/dev/null || true
udevadm trigger 2>/dev/null || true

# Systemd servisini etkinleştir
systemctl daemon-reload 2>/dev/null || true
systemctl enable casper-keyboard-rgb-restore.service 2>/dev/null || true

exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postinst"

# ── prerm (kaldırma öncesi) ──────────────────────────────────
cat > "${BUILD_DIR}/DEBIAN/prerm" << 'EOF'
#!/bin/bash
set -e

# Systemd servisini durdur ve devre dışı bırak
systemctl stop casper-keyboard-rgb-restore.service 2>/dev/null || true
systemctl disable casper-keyboard-rgb-restore.service 2>/dev/null || true

exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/prerm"

# ── postrm (kaldırma sonrası) ────────────────────────────────
cat > "${BUILD_DIR}/DEBIAN/postrm" << 'EOF'
#!/bin/bash
set -e

if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    # DKMS modülünü kaldır
    DRIVER_VER="1.0.0"
    if command -v dkms &>/dev/null; then
        dkms remove casper-wmi/"$DRIVER_VER" --all 2>/dev/null || true
    fi

    # Modülü unload et
    modprobe -r casper-wmi 2>/dev/null || true

    # Modules-load konfigürasyonunu kaldır
    rm -f /etc/modules-load.d/casper-wmi.conf 2>/dev/null || true

    # Udev yeniden yükle
    udevadm control --reload-rules 2>/dev/null || true

    # Systemd reload
    systemctl daemon-reload 2>/dev/null || true
fi

exit 0
EOF
chmod 755 "${BUILD_DIR}/DEBIAN/postrm"

# ── Python uygulama dosyaları ────────────────────────────────
info "Uygulama dosyaları kopyalanıyor..."

APP_DIR="${BUILD_DIR}/opt/${PKG_NAME}"
mkdir -p "${APP_DIR}"
cp -r "${SCRIPT_DIR}/casper_keyboard_rgb" "${APP_DIR}/"
cp    "${SCRIPT_DIR}/pyproject.toml"      "${APP_DIR}/"

# __pycache__ temizle
find "${APP_DIR}" -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# ── Helper script ────────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/lib/${PKG_NAME}"
install -m755 "${SCRIPT_DIR}/data/led-write-helper" \
    "${BUILD_DIR}/usr/lib/${PKG_NAME}/led-write-helper"

# ── Polkit policy ────────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/share/polkit-1/actions"
install -m644 "${SCRIPT_DIR}/data/org.casper.keyboard.rgb.policy" \
    "${BUILD_DIR}/usr/share/polkit-1/actions/org.casper.keyboard.rgb.policy"

# ── Udev rule ────────────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/lib/udev/rules.d"
install -m644 "${SCRIPT_DIR}/data/99-casper-kbd-backlight.rules" \
    "${BUILD_DIR}/usr/lib/udev/rules.d/99-casper-kbd-backlight.rules"

# ── Desktop file ─────────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/share/applications"
install -m644 "${SCRIPT_DIR}/data/casper-keyboard-rgb.desktop" \
    "${BUILD_DIR}/usr/share/applications/${PKG_NAME}.desktop"

# ── Systemd service ─────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/lib/systemd/system"
install -m644 "${SCRIPT_DIR}/systemd/casper-keyboard-rgb-restore.service" \
    "${BUILD_DIR}/usr/lib/systemd/system/${PKG_NAME}-restore.service"

# ── License ──────────────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/share/doc/${PKG_NAME}"
install -m644 "${SCRIPT_DIR}/LICENSE" \
    "${BUILD_DIR}/usr/share/doc/${PKG_NAME}/copyright"

# ── DKMS kernel module sources ───────────────────────────────
DKMS_DIR="${BUILD_DIR}/usr/src/casper-wmi-1.0.0"
mkdir -p "${DKMS_DIR}"
install -m644 "${SCRIPT_DIR}/driver/casper-wmi.c" "${DKMS_DIR}/casper-wmi.c"
install -m644 "${SCRIPT_DIR}/driver/Makefile"      "${DKMS_DIR}/Makefile"
install -m644 "${SCRIPT_DIR}/driver/dkms.conf"     "${DKMS_DIR}/dkms.conf"

# ── Modules-load config ─────────────────────────────────────
mkdir -p "${BUILD_DIR}/etc/modules-load.d"
echo "casper-wmi" > "${BUILD_DIR}/etc/modules-load.d/casper-wmi.conf"

# ── Launcher script ─────────────────────────────────────────
mkdir -p "${BUILD_DIR}/usr/bin"
cat > "${BUILD_DIR}/usr/bin/${PKG_NAME}" << 'LAUNCHER'
#!/bin/bash
cd /opt/casper-keyboard-rgb
exec python3 -m casper_keyboard_rgb.main "$@"
LAUNCHER
chmod 755 "${BUILD_DIR}/usr/bin/${PKG_NAME}"

# ── Paket oluştur ────────────────────────────────────────────
info "Debian paketi oluşturuluyor..."
cd "${SCRIPT_DIR}/deb-build"
dpkg-deb --build --root-owner-group "${DEB_NAME}"

# Çıktıyı ana dizine taşı
mv "${DEB_NAME}.deb" "${SCRIPT_DIR}/"

# Temizle
rm -rf "${SCRIPT_DIR}/deb-build"

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║   Debian paketi başarıyla oluşturuldu!               ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║   ${DEB_NAME}.deb            ║${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}║   Kurulum:                                           ║${NC}"
echo -e "${GREEN}${BOLD}║     sudo apt install ./${DEB_NAME}.deb   ║${NC}"
echo -e "${GREEN}${BOLD}║                                                      ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
