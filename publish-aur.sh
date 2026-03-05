#!/bin/bash
# ──────────────────────────────────────────────────────────────
# Casper Keyboard RGB – AUR'a Yayınlama Betiği
#
# Kullanım:
#   ./publish-aur.sh
#
# Ön koşullar:
#   1. AUR hesabınızda SSH key ayarlı olmalı
#      → https://aur.archlinux.org/account
#   2. 'casper-keyboard-rgb' paketi AUR'da oluşturulmuş olmalı
#      → Yoksa bu betik otomatik oluşturur
# ──────────────────────────────────────────────────────────────

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'
BOLD='\033[1m'

info()  { echo -e "${CYAN}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[  OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; exit 1; }

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKGNAME="casper-keyboard-rgb"
AUR_DIR="${SCRIPT_DIR}/.aur-repo"

# ── 1. Gerekli araçları kontrol et ───────────────────────────
info "Gerekli araçlar kontrol ediliyor..."

for cmd in git makepkg ssh; do
    command -v "$cmd" &>/dev/null || fail "'$cmd' bulunamadı. Lütfen kurun."
done

if ! ssh -T aur@aur.archlinux.org 2>&1 | grep -q "authenticated"; then
    echo ""
    warn "AUR SSH bağlantısı kurulamadı."
    echo ""
    echo -e "${BOLD}SSH key ayarlamak için:${NC}"
    echo "  1. ssh-keygen -t ed25519 -C 'aur'"
    echo "  2. Kopyala: cat ~/.ssh/id_ed25519.pub"
    echo "  3. Yapıştır: https://aur.archlinux.org/account → SSH Public Key"
    echo ""
    echo -e "${BOLD}~/.ssh/config dosyanıza ekleyin:${NC}"
    echo "  Host aur.archlinux.org"
    echo "    IdentityFile ~/.ssh/id_ed25519"
    echo "    User aur"
    echo ""
    fail "Önce AUR SSH erişimini ayarlayın."
fi
ok "AUR SSH bağlantısı hazır."

# ── 2. GitHub'da tag kontrolü ────────────────────────────────
PKGVER=$(grep '^pkgver=' "${SCRIPT_DIR}/PKGBUILD" | cut -d'=' -f2)
TAG="v${PKGVER}"

info "GitHub tag kontrolü: ${TAG}"

cd "$SCRIPT_DIR"
if ! git tag -l "$TAG" | grep -q "$TAG"; then
    info "Tag '${TAG}' oluşturuluyor..."
    git tag -a "$TAG" -m "Release ${TAG}"
    git push origin "$TAG"
    ok "Tag '${TAG}' oluşturuldu ve push edildi."
else
    ok "Tag '${TAG}' zaten mevcut."
fi

# ── 3. AUR repo'yu klon/güncelle ────────────────────────────
info "AUR deposu hazırlanıyor..."

if [[ -d "$AUR_DIR" ]]; then
    cd "$AUR_DIR"
    git pull --ff-only 2>/dev/null || {
        warn "AUR repo pull başarısız, yeniden klonlanıyor..."
        rm -rf "$AUR_DIR"
        git clone "ssh://aur@aur.archlinux.org/${PKGNAME}.git" "$AUR_DIR"
        cd "$AUR_DIR"
    }
else
    git clone "ssh://aur@aur.archlinux.org/${PKGNAME}.git" "$AUR_DIR" 2>/dev/null || {
        # Paket henüz AUR'da yok — boş repo oluştur
        info "AUR'da '${PKGNAME}' bulunamadı, yeni paket oluşturuluyor..."
        mkdir -p "$AUR_DIR"
        cd "$AUR_DIR"
        git init
        git remote add origin "ssh://aur@aur.archlinux.org/${PKGNAME}.git"
    }
    cd "$AUR_DIR"
fi

# ── 4. PKGBUILD ve .install dosyalarını kopyala ──────────────
info "Dosyalar kopyalanıyor..."

cp "${SCRIPT_DIR}/PKGBUILD"                 "${AUR_DIR}/PKGBUILD"
cp "${SCRIPT_DIR}/casper-keyboard-rgb.install" "${AUR_DIR}/casper-keyboard-rgb.install"

# ── 5. .SRCINFO oluştur ─────────────────────────────────────
info ".SRCINFO oluşturuluyor..."

cd "$AUR_DIR"
makepkg --printsrcinfo > .SRCINFO
ok ".SRCINFO oluşturuldu."

# ── 6. Commit ve push ───────────────────────────────────────
git add PKGBUILD casper-keyboard-rgb.install .SRCINFO
if git diff --cached --quiet; then
    ok "Değişiklik yok, AUR zaten güncel."
else
    git commit -m "Update to ${PKGVER}"
    git push origin master
    ok "AUR'a push edildi: https://aur.archlinux.org/packages/${PKGNAME}"
fi

echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║          AUR yayınlama tamamlandı!                  ║${NC}"
echo -e "${GREEN}${BOLD}╠══════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}${BOLD}║                                                     ║${NC}"
echo -e "${GREEN}${BOLD}║  Kullanıcılar artık şu komutla kurabilir:           ║${NC}"
echo -e "${GREEN}${BOLD}║    yay -S casper-keyboard-rgb                       ║${NC}"
echo -e "${GREEN}${BOLD}║                                                     ║${NC}"
echo -e "${GREEN}${BOLD}║  AUR sayfası:                                       ║${NC}"
echo -e "${GREEN}${BOLD}║    https://aur.archlinux.org/packages/${PKGNAME}    ║${NC}"
echo -e "${GREEN}${BOLD}║                                                     ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════╝${NC}"
echo ""
