#!/bin/bash
VERSION=$1
# Update pkgver in PKGBUILD
sed -i "s/^pkgver=.*/pkgver=${VERSION}/" PKGBUILD

# Calculate new sha256sum for the release tarball
# Wait a bit to ensure the tag and tarball are available on GitHub,
# although semantic release pushes them just before this.
sleep 5

URL="https://github.com/Jaeger0000/casper_excalibur_keyboard_rgb_linux/archive/v${VERSION}.tar.gz"
echo "Downloading $URL to calculate sha256sum..."

# We might need to retry a few times if the tarball isn't ready instantly
for i in {1..5}; do
    if curl -sfL -o release.tar.gz "$URL"; then
        if [ -s release.tar.gz ]; then
            break
        fi
    fi
    echo "Wait for release tarball..."
    sleep 5
done

SHA256=$(sha256sum release.tar.gz | awk '{print $1}')
echo "New SHA256: $SHA256"

# Update sha256sums in PKGBUILD
sed -i "s/^sha256sums=('.*')/sha256sums=('${SHA256}')/" PKGBUILD
rm release.tar.gz
