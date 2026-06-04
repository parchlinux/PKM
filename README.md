# Parch Kernel Manager

Parch Kernel Manager is a GTK4 and LibAdwaita application for browsing, installing, and removing Linux kernels on Parch GNU/Linux and Arch-based distributions. It discovers kernels dynamically from your pacman repositories, shows you which ones are installed and which one is currently booted, and lets you install or remove them with a single click. Privileged operations run through pkexec with a live terminal feed so you can see exactly what pacman is doing.

## Requirements

You need an Arch-based system with Python 3.9 or newer, GTK4, LibAdwaita, the VTE terminal widget for GTK4, and PyGObject. For privilege escalation you also need pkexec from polkit. On Arch you can install everything with a single pacman command:

```
sudo pacman -S python python-gobject gtk4 libadwaita vte4 polkit
```

## Installation

Clone the repository and install with pip:

```
git clone https://github.com/parchlinux/pkm.git
cd pkm
pip install -e .
parch-kernel-manager
```

You can also run it directly without installing:

```
python3 main.py
```

Arch users can install the PKGBUILD included in the repository:

```
makepkg -si
```

## Usage

When you launch the application, it scans your repositories for all available Linux kernel packages and shows them in a list. Each row shows the kernel name, version, and description, along with an Install or Remove button. The currently booted kernel is marked with an Active badge and cannot be removed. The app will also prevent you from removing your last remaining kernel so you never end up without a bootable system.

Install and remove operations open a terminal dialog that shows the full pacman output in real time. You can cancel an ongoing operation by clicking the Cancel button in the dialog header.

## License

AGPL-3.0 or later. See [LICENSE](LICENSE).
