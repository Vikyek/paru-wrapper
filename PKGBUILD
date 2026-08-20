pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=1
pkgdesc="A wrapper around paru that implements dependency-aware orphan cleaning and automatic local repository DB updates"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL')
depends=('paru' 'bash' 'sudo')
install=paru-wrapper.install
source=(
    "paru-wrapper"
)
sha256sums=('9913dc039d9ac253627c7a17e24fa1cca88ba55ec3c3b94327947b4b7e24fca2')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
}
