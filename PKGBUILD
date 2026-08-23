pkgname=paru-wrapper
pkgver=1.0.0
pkgrel=3
pkgdesc="A wrapper around paru that implements dependency-aware orphan cleaning and automatic local repository DB updates"
arch=('any')
url="https://github.com/Vikyek/paru-wrapper"
license=('GPL')
depends=('paru' 'bash' 'sudo')
install=paru-wrapper.install
source=(
    "paru-wrapper"
    "update_mkvpkg_aur.py"
)
sha256sums=('5f9e8360dbc0a20909a2db88ddea7b4a08cf0f17dd5b62922ef2959f523acc92'
            'a83f6524575cc1ed34e5fa9aabfbb0279cffe67f7c4c7ee098f06b23eb982479')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
}
