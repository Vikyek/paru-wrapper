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
sha256sums=('dcf01f73de094f9fc3a69263b3b39520db531606e5cf4ec2b096e89783271c16'
            'c234fbb4457e50d32f2ee16db5482d35fd506e644edd7a8f2a8b3869e38735aa'
            '7ddb593fb7ac474f1a613ff74857a8ff7c7670a83d520d668eaaca1497d8b5e8')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
}
