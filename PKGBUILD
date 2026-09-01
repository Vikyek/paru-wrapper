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
sha256sums=('ad5548175c07ce89f945ba0229a0bd4f0c9b13f1f9fc33531a1947c6a8c7a300'
            'ccb987a3c8c297db2433e1ad3ad68f4e1867f96e3974ae110393fd448f1f9638'
            'a43d5f5b55b065aa070bef0f3774770f0a3fa19477eb099f1b191f80ea36fe18'
            '3972dc9744f6499f0f9b2dbf76696f2ae7ad8af9b23dde66d6af86c9dfb36986')

package() {
    # Install paru wrapper
    install -Dm755 "${srcdir}/paru-wrapper" "${pkgdir}/usr/bin/paru-wrapper"
    install -Dm755 "${srcdir}/update_mkvpkg_aur.py" "${pkgdir}/usr/bin/update_mkvpkg_aur.py"
    install -Dm755 "${srcdir}/pacman-wrapper" "${pkgdir}/usr/bin/pacman-wrapper"
    install -Dm644 "${srcdir}/LICENSE" "${pkgdir}/usr/share/licenses/${pkgname}/LICENSE"
}
