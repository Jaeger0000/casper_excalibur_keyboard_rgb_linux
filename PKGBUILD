# Maintainer: jaeger
pkgname=casper-keyboard-rgb
pkgver=1.0.0
pkgrel=1
pkgdesc="Casper Excalibur Klavye RGB LED Kontrol Aracı (GUI + CLI)"
arch=('any')
url="https://github.com/jaeger/casper_excalibur_keyboard_rgb_linux"
license=('GPL-3.0-or-later')
depends=(
    'python>=3.10'
    'python-pyqt6'
    'polkit'
)
optdepends=(
    'casper-wmi-dkms: Casper WMI kernel module (required for LED control)'
)
makedepends=(
    'python-build'
    'python-installer'
    'python-wheel'
    'python-setuptools'
)
source=("${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz")
sha256sums=('SKIP')
install="${pkgname}.install"

build() {
    cd "${srcdir}/casper_excalibur_keyboard_rgb_linux-${pkgver}"
    python -m build --wheel --no-isolation
}

package() {
    cd "${srcdir}/casper_excalibur_keyboard_rgb_linux-${pkgver}"

    # Install Python package
    python -m installer --destdir="${pkgdir}" dist/*.whl

    # Helper script (root-owned, 0755)
    install -Dm755 data/led-write-helper \
        "${pkgdir}/usr/lib/${pkgname}/led-write-helper"

    # Polkit policy
    install -Dm644 data/org.casper.keyboard.rgb.policy \
        "${pkgdir}/usr/share/polkit-1/actions/org.casper.keyboard.rgb.policy"

    # Desktop file
    install -Dm644 data/casper-keyboard-rgb.desktop \
        "${pkgdir}/usr/share/applications/${pkgname}.desktop"

    # Systemd service
    install -Dm644 systemd/casper-keyboard-rgb-restore.service \
        "${pkgdir}/usr/lib/systemd/system/${pkgname}-restore.service"

    # License
    install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
