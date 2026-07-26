# Changelog

All notable changes to **Parch Kernel Manager** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [1.1.0] - 2026-07-26

### 🚀 Added
- **Default Bootloader Kernel Selector**: Set default boot kernel for GRUB or systemd-boot with a single click.
- **Kernel Specifications Inspector**: Detailed inspector dialog showing installed size, build date, header status, module path, and DKMS drivers.
- **DKMS Out-of-Tree Driver Status**: Detect and display build status for DKMS modules (e.g., `nvidia`, `broadcom-wl`, `virtualbox-host-modules`).
- **Orphaned System Module Cleaner**: Scan and clean leftover `/usr/lib/modules/` directories from uninstalled kernels.
- **Search & Category Filtering**: Instant live search entry and category filter buttons (`All`, `Installed`, `Available`, `LTS`, `Performance`).
- **Custom Kernel Compilation Presets**: One-click configuration presets for **Gaming & Low-Latency** (1000Hz timer, preemptive kernel, BBR) and **Battery Saver** (250Hz timer).
- **Native Gettext Localization**: Added internationalization infrastructure with complete, natural **Persian (fa)** translation.

### 🎨 UI & UX Revamp
- **Strict GNOME HIG & LibAdwaita Compliance**: Converted all layout elements to native `Adw.PreferencesGroup`, `Adw.ActionRow`, `Adw.WindowTitle`, and `Adw.StatusPage` components.
- **Freedesktop Standard Icon Alignment**: Standardized symbolic icons to Freedesktop Spec names compatible across both GNOME and KDE Plasma desktops.
- **Clean Label Badging**: Replaced custom CSS overrides with clean native LibAdwaita badge styling (`accent`, `dim-label`), eliminating background square artifacts.

### 🔒 Security & Stability Fixes
- **Shell Injection Remediation**: Applied `shlex.quote()` on all path and string interpolations in privileged custom kernel build scripts.
- **Predictable `/tmp` File Fix**: Replaced static `/tmp/kernel-compile.sh` path with `tempfile.NamedTemporaryFile` created with restricted `0o700` permissions.
- **Multi-Architecture Build Logic**: Replaced hardcoded `x86_64` kernel image path (`arch/x86/boot/bzImage`) with dynamic multi-arch detection (`aarch64`, `riscv64`, `x86_64`).
- **Pango Markup Escaping**: Fixed unescaped ampersand entity parsing errors in dialog titles.
- **GTK Scroll Preservation**: Maintained vertical scroll adjustment value across kernel list refreshes to eliminate UI jumping.

---

## [1.0.0] - 2026-06-15

### 🚀 Initial Release
- Kernel discovery from pacman repositories and `/usr/lib/modules/*/pkgbase`.
- Live VTE terminal output for `pkexec` operations.
- Custom kernel compilation wizard.
