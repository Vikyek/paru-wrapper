pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=2
pkgdesc="A wrapper around paru that implements dependency-aware orphan cleaning and automatic local repository DB updates"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL')
depends=('paru' 'bash' 'sudo')
install=paru-wrapper.install
source=(
    "paru-wrapper"
)
sha256sums=('07527d9231622cd0d7686beeebd89a61ae95da3e18b49ff292851c946e5f38bc')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
}
