# Maintainer: Parch Linux Developers
# Contributor: Sohrab

pkgname=parch-kernel-manager
pkgver=1.1.0
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
  'gettext'
  'git'
)
source=("$pkgname::git+https://github.com/parchlinux/pkm.git#tag=v$pkgver")
sha256sums=('SKIP')


build() {
  cd "$srcdir/$pkgname"
  python -m build --wheel --no-isolation

  for po in po/*.po; do
    [ -f "$po" ] || continue
    lang=$(basename "$po" .po)
    mkdir -p "locales/$lang/LC_MESSAGES"
    msgfmt "$po" -o "locales/$lang/LC_MESSAGES/parch-kernel-manager.mo"
  done
}

package() {
  cd "$srcdir/$pkgname"
  python -m installer --destdir="$pkgdir" dist/*.whl

  install -Dm644 data/com.parchlinux.kernelmanager.desktop \
    "$pkgdir/usr/share/applications/com.parchlinux.kernelmanager.desktop"
  install -Dm644 data/com.parchlinux.kernelmanager.svg \
    "$pkgdir/usr/share/icons/hicolor/scalable/apps/com.parchlinux.kernelmanager.svg"

  for mo in locales/*/LC_MESSAGES/*.mo; do
    [ -f "$mo" ] || continue
    lang=$(echo "$mo" | cut -d'/' -f2)
    install -Dm644 "$mo" "$pkgdir/usr/share/locale/$lang/LC_MESSAGES/parch-kernel-manager.mo"
  done
}

