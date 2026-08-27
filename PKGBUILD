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
            'c234fbb4457e50d32f2ee16db5482d35fd506e644edd7a8f2a8b3869e38735aa'
            '196ce091d2189a17eb674da84f0b3e5f12fd50d5777547417b6267a8ee2c4f7b')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
