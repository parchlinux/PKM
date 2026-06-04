# Maintainer: Parch Linux Developers
# Contributor: Sohrab

pkgname=parch-kernel-manager
pkgver=0.1.0
pkgrel=1
pkgdesc='Manage Linux kernels on Parch GNU/Linux and Arch-based distributions'
arch=('any')
url='https://github.com/parchlinux/pkm'
license=('AGPL3')
depends=(
  'python'
  'python-gobject'
  'gtk4'
  'libadwaita'
  'vte4'
  'polkit'
)
makedepends=(
  'python-build'
  'python-installer'
  'python-wheel'
  'python-setuptools'
  'git'
)
source=("$pkgname::git+https://github.com/parchlinux/pkm.git")
sha256sums=('SKIP')

build() {
  cd "$srcdir/$pkgname"
  python -m build --wheel --no-isolation
}

package() {
  cd "$srcdir/$pkgname"
  python -m installer --destdir="$pkgdir" dist/*.whl

  install -Dm644 data/com.parchlinux.kernelmanager.desktop \
    "$pkgdir/usr/share/applications/com.parchlinux.kernelmanager.desktop"
  install -Dm644 data/com.parchlinux.kernelmanager.svg \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/com.parchlinux.kernelmanager.svg"
}
