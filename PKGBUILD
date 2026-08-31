pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=6
pkgdesc="A wrapper around paru that implements dependency-aware orphan cleaning and automatic local repository DB updates"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL')
depends=('paru' 'bash' 'sudo')
install=paru-wrapper.install
source=(
    "paru-wrapper"
    "update_mkvpkg_aur.py"
    "pacman-wrapper"
)
sha256sums=('SKIP'
            'SKIP'
            'SKIP')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
