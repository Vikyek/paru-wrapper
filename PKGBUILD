pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=5
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
sha256sums=('7a90b770d9af1ee53d20c2e76c0791ce19d4ab7bb9882af9aa0c0f0a95883950'
            '3dba8118b598ad2be090bd45e954eb81f1c00665de524cb3366da0ff6c34b75f'
            'a2a3704ed1b72b9cb5a07fca38562e945eee9c1a4290fab5c2202a77bddcba8d')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
