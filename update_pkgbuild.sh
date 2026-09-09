#!/bin/bash
# Bump pkgver in PKGBUILD and refresh its sha256sum from the published
# release tarball.  Called by CI right after semantic-release tags a
# version; a failure here must stop the pipeline rather than commit a
# PKGBUILD with an empty checksum, which would break every AUR install.

set -euo pipefail

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
    echo "Kullanım: $0 <sürüm>" >&2
    exit 1
fi

REPO="https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux"
URL="${REPO}/archive/v${VERSION}.tar.gz"
TARBALL="$(mktemp -t casper-release-XXXXXX.tar.gz)"
trap 'rm -f "$TARBALL"' EXIT

echo "Downloading $URL to calculate sha256sum..."

# The tag is pushed moments before this runs, so give GitHub a little
# time to make the generated tarball available.
downloaded=0
for attempt in {1..6}; do
    if curl -sfL -o "$TARBALL" "$URL" && [[ -s "$TARBALL" ]]; then
        downloaded=1
        break
    fi
    echo "Release tarball hazır değil, tekrar denenecek (${attempt}/6)..."
    sleep 10
done

if [[ "$downloaded" -ne 1 ]]; then
    echo "HATA: Release tarball indirilemedi: $URL" >&2
    exit 1
fi

# Reject anything that is not a real gzip archive (e.g. an HTML error page).
if ! tar -tzf "$TARBALL" >/dev/null 2>&1; then
    echo "HATA: İndirilen dosya geçerli bir tar.gz değil: $URL" >&2
    exit 1
fi

SHA256="$(sha256sum "$TARBALL" | awk '{print $1}')"
if [[ ! "$SHA256" =~ ^[0-9a-f]{64}$ ]]; then
    echo "HATA: Geçersiz sha256 hesaplandı: '$SHA256'" >&2
    exit 1
fi
echo "New SHA256: $SHA256"

sed -i "s/^pkgver=.*/pkgver=${VERSION}/" PKGBUILD
sed -i "s/^pkgrel=.*/pkgrel=1/" PKGBUILD
sed -i "s/^sha256sums=('.*')/sha256sums=('${SHA256}')/" PKGBUILD

# Fail loudly if either substitution silently did not apply.
grep -q "^pkgver=${VERSION}$" PKGBUILD || { echo "HATA: pkgver güncellenemedi" >&2; exit 1; }
grep -q "^sha256sums=('${SHA256}')$" PKGBUILD || { echo "HATA: sha256sums güncellenemedi" >&2; exit 1; }

echo "PKGBUILD güncellendi: v${VERSION}"
