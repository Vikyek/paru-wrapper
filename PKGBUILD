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
sha256sums=('1192c3b8f4196b0ae5074a84d5b93a0fe93ed6bddf4e38e90929a55ece457967'
            '4e0f24eebe0dfbe7bea64dd54c04a92809ba2c539923af85bb4a600bbd55479a'
            '2769d1bf7772a7cc3a95df62c79543c0bfb44d48db901f0a4c169aae23d68f6a')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
