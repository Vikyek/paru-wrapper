pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=6
pkgdesc="A wrapper around paru that implements dependency-aware orphan cleaning and automatic local repository DB updates"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL-3.0-only')
depends=('paru' 'bash' 'sudo' 'python' 'jq' 'curl' 'git' 'pacman-contrib')
install=paru-wrapper.install
source=(
    "paru-wrapper"
    "update_mkvpkg_aur.py"
    "pacman-wrapper"
    "LICENSE"
)
sha256sums=('2091abe3d66f42869de26819793ce06bc9555007cfd262ef5fe6c9fc4b76465a'
            '6f1d55d249e613ee2a4a759f70ca34269c0c54a11184b1669727d78e31fc94bd'
            '502cfb8c5338c36d20fadfb02838f2d82ee41b3c4bdecb69251098cc42171aa6'
            '3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
