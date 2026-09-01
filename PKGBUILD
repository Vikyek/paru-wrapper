pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=6
pkgdesc="A wrapper around paru that implements dependency-aware orphan cleaning and automatic local repository DB updates"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL')
depends=('paru' 'bash' 'sudo' 'python')
install=paru-wrapper.install
source=(
    "paru-wrapper"
    "update_mkvpkg_aur.py"
    "pacman-wrapper"
)
sha256sums=('95a819cb5abebc490899bb8eb5682210c34c5b970e51b1822c20ec1b1e73b871'
            '070b62af43f97060cb40bc7f7e6575c5c1fab174ab643a5408c008d95b2faabe'
            '502cfb8c5338c36d20fadfb02838f2d82ee41b3c4bdecb69251098cc42171aa6')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
