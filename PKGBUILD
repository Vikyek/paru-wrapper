# Maintainer: Vikyek

pkgname=paru-wrapper
pkgver=1.1.1
pkgrel=1
pkgdesc="Custom paru wrapper providing automatic local AUR repo management and --gittinator VCS migrations"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL-3.0-only')
depends=(
    'paru'
    'bash'
    'sudo'
    'python'
    'jq'
    'curl'
    'git'
)
install=paru-wrapper.install

source=(
    "${pkgname}-${pkgver}.tar.gz::${url}/archive/refs/tags/v${pkgver}.tar.gz"
)

sha256sums=(
    'SKIP'
)

package() {
    cd "${srcdir}/${pkgname}-${pkgver}"

    install -Dm755 paru-wrapper "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 paru-wrapper-gittinator "${pkgdir}/usr/lib/paru-wrapper/paru-wrapper-gittinator"
    install -Dm755 pacman-wrapper "${pkgdir}/usr/bin/pacman-wrapper"
    install -Dm755 update_mkvpkg_aur.py "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm644 LICENSE "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
