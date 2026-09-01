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
sha256sums=('a1d6049dd6f2a783cd6c0732b9fb8047359d893bdb7a2e2f6431392427ac9c0a'
            'db193efd8fc83f936451bd984a39430417d37703e6be96c26eb7bb377ca5283f'
            '502cfb8c5338c36d20fadfb02838f2d82ee41b3c4bdecb69251098cc42171aa6')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
