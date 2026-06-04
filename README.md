# Parch Kernel Manager

A modern GUI application for managing Linux kernels on
[Parch GNU/Linux](https://parchlinux.com) and Arch-based distributions.
Built with GTK4 and LibAdwaita.

## Features

- Browse all available kernel packages (linux, linux-lts, linux-zen,
  linux-hardened, linux-rt, plus AUR kernels)
- See which kernels are installed and which is currently booted
- Install new kernels with a single click
- Remove installed kernels safely (prevents removing the last kernel)
- Live terminal output during install/remove operations
- Privilege escalation via `pkexec` (PolicyKit)
- Async kernel discovery — UI never blocks

## Requirements

- **Arch Linux / Parch GNU/Linux** (uses `pacman`)
- **Python 3.9+**
- **GTK 4**, **LibAdwaita**, **VTE** (GTK4 variant)
- **PyGObject** (`python-gobject`)
- **pkexec** (PolicyKit)

### Install Dependencies (Arch)

```bash
sudo pacman -S python python-gobject gtk4 libadwaita vte4 polkit
```

## Installation

### From source

```bash
git clone https://github.com/parchlinux/kernel-manager.git
cd kernel-manager
pip install -e .
parch-kernel-manager
```

Or run directly without installing:

```bash
python3 main.py
```

## Screenshots

*TODO — add screenshots*

## Usage

1. Launch **Parch Kernel Manager** from your app menu or terminal
2. Wait for kernel list to load (async — UI stays responsive)
3. Click **Install** next to any available kernel
4. Click **Remove** next to installed kernels (not possible for the
   last remaining kernel or the currently booted one)
5. Click **Refresh** to reload the kernel list

## License

AGPL-3.0-or-later — see [LICENSE](LICENSE).
