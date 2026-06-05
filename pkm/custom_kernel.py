# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import subprocess
from pathlib import Path


def get_kernel_sources_dir():
    common_dirs = [
        Path.home() / 'kernel',
        Path.home() / 'linux',
        Path('/usr/src/linux'),
        Path('/usr/src'),
    ]
    
    for d in common_dirs:
        if d.exists() and d.is_dir():
            makefiles = list(d.glob('**/Makefile'))
            if makefiles:
                for makefile in makefiles:
                    if is_kernel_source(makefile.parent):
                        return makefile.parent
    return None


def detect_bootloader():
    """
    Detect which bootloader is currently in use.
    Returns: 'grub', 'systemd-boot', or None
    """
    if Path('/boot/grub/grub.cfg').exists() or Path('/boot/grub2/grub.cfg').exists():
        try:
            result = subprocess.run(
                ['grub-mkconfig', '--version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return 'grub'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    if Path('/boot/loader/loader.conf').exists() or Path('/boot/efi/loader/loader.conf').exists():
        try:
            result = subprocess.run(
                ['bootctl', 'status'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return 'systemd-boot'
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
    
    return None


def is_kernel_source(path):
    path = Path(path)
    required_files = ['Makefile', 'Kconfig', 'MAINTAINERS']
    required_dirs = ['kernel', 'mm', 'fs', 'drivers']
    
    for f in required_files:
        if not (path / f).exists():
            return False
    
    for d in required_dirs:
        if not (path / d).is_dir():
            return False
    
    return True


def get_kernel_version_from_source(source_dir):
    makefile = Path(source_dir) / 'Makefile'
    if not makefile.exists():
        return None
    
    version_info = {}
    try:
        with open(makefile, 'r') as f:
            for line in f:
                line = line.strip()
                if line.startswith('VERSION ='):
                    version_info['VERSION'] = line.split('=')[1].strip()
                elif line.startswith('PATCHLEVEL ='):
                    version_info['PATCHLEVEL'] = line.split('=')[1].strip()
                elif line.startswith('SUBLEVEL ='):
                    version_info['SUBLEVEL'] = line.split('=')[1].strip()
                elif line.startswith('EXTRAVERSION ='):
                    version_info['EXTRAVERSION'] = line.split('=')[1].strip()
                
                if len(version_info) >= 4:
                    break
    except Exception:
        return None
    
    if 'VERSION' in version_info and 'PATCHLEVEL' in version_info:
        ver = f"{version_info['VERSION']}.{version_info['PATCHLEVEL']}"
        if version_info.get('SUBLEVEL'):
            ver += f".{version_info['SUBLEVEL']}"
        if version_info.get('EXTRAVERSION'):
            ver += version_info['EXTRAVERSION']
        return ver
    
    return None


def validate_kernel_source(source_dir):
    source_dir = Path(source_dir)
    
    if not source_dir.exists():
        return False, "Directory does not exist"
    
    if not source_dir.is_dir():
        return False, "Path is not a directory"
    
    if not is_kernel_source(source_dir):
        return False, "Not a valid kernel source directory"
    
    version = get_kernel_version_from_source(source_dir)
    if not version:
        return False, "Could not determine kernel version"
    
    return True, version


def check_build_dependencies():
    required_packages = [
        'base-devel',
        'bc',
        'cpio',
        'kmod',
        'libelf',
        'pahole',
    ]
    
    missing = []
    for pkg in required_packages:
        try:
            subprocess.check_output(
                ['pacman', '-Q', pkg],
                stderr=subprocess.DEVNULL,
                timeout=5
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
            missing.append(pkg)
    
    return missing


def create_build_script(source_dir, config_file=None, localversion='', bootloader='auto'):
    source_dir = Path(source_dir).resolve()
    
    script_lines = [
        '#!/bin/bash',
        'set -e',
        '',
        'echo "================================================"',
        'echo "  Custom Kernel Compilation Script"',
        'echo "================================================"',
        'echo ""',
        '',
        f'cd "{source_dir}"',
        '',
        'echo "==> Step 1/6: Configuring kernel..."',
    ]
    
    if config_file and Path(config_file).exists():
        script_lines.extend([
            f'if [ -f "{config_file}" ]; then',
            f'    cp "{config_file}" .config',
            '    echo "Using custom config file"',
            'else',
            '    make defconfig',
            '    echo "Using default config"',
            'fi',
        ])
    else:
        script_lines.append('make defconfig')
    
    if localversion:
        script_lines.extend([
            '',
            f'sed -i "s/CONFIG_LOCALVERSION=.*/CONFIG_LOCALVERSION=\\"-{localversion}\\"/" .config || true',
            f'echo "CONFIG_LOCALVERSION=\\"-{localversion}\\"" >> .config',
        ])
    
    script_lines.extend([
        '',
        'KERNEL_VERSION=$(make kernelversion)',
        'echo "Building kernel version: $KERNEL_VERSION"',
        'echo ""',
        '',
        'echo "==> Step 2/6: Building kernel (this will take 30-90 minutes)..."',
        'echo "    Using $(nproc) CPU cores"',
        'make -j$(nproc) 2>&1 | tee /tmp/kernel-build.log || {',
        '    echo "ERROR: Kernel compilation failed!"',
        '    echo "Check /tmp/kernel-build.log for details"',
        '    exit 1',
        '}',
        '',
        'echo ""',
        'echo "==> Step 3/6: Installing kernel modules..."',
        'make modules_install || {',
        '    echo "ERROR: Module installation failed!"',
        '    exit 1',
        '}',
        '',
        'echo ""',
        'echo "==> Step 4/6: Installing kernel image..."',
        '',
        'KERNEL_IMAGE="arch/x86/boot/bzImage"',
        'if [ ! -f "$KERNEL_IMAGE" ]; then',
        '    echo "ERROR: Kernel image not found at $KERNEL_IMAGE"',
        '    exit 1',
        'fi',
        '',
        'INSTALL_VERSION="${KERNEL_VERSION}' + (f'-{localversion}' if localversion else '') + '"',
        'cp -v "$KERNEL_IMAGE" "/boot/vmlinuz-${INSTALL_VERSION}"',
        'cp -v System.map "/boot/System.map-${INSTALL_VERSION}"',
        'cp -v .config "/boot/config-${INSTALL_VERSION}"',
        '',
        'echo ""',
        'echo "==> Step 5/6: Generating initramfs..."',
        'if command -v mkinitcpio &>/dev/null; then',
        '    mkinitcpio -k "${INSTALL_VERSION}" -g "/boot/initramfs-${INSTALL_VERSION}.img" || {',
        '        echo "WARNING: mkinitcpio failed, trying fallback..."',
        '        mkinitcpio -p linux || true',
        '    }',
        'elif command -v dracut &>/dev/null; then',
        '    dracut --force --hostonly "/boot/initramfs-${INSTALL_VERSION}.img" "${INSTALL_VERSION}" || {',
        '        echo "ERROR: dracut failed!"',
        '        exit 1',
        '    }',
        'else',
        '    echo "WARNING: No initramfs generator found (mkinitcpio or dracut)"',
        '    echo "You may need to create initramfs manually"',
        'fi',
        '',
        'echo ""',
        'echo "==> Step 6/6: Updating bootloader..."',
        '',
        f'BOOTLOADER="{bootloader}"',
        '',
        'if [ "$BOOTLOADER" = "auto" ]; then',
        '    if command -v grub-mkconfig &>/dev/null && [ -f /boot/grub/grub.cfg ]; then',
        '        BOOTLOADER="grub"',
        '    elif command -v bootctl &>/dev/null && [ -f /boot/loader/loader.conf ]; then',
        '        BOOTLOADER="systemd-boot"',
        '    else',
        '        BOOTLOADER="unknown"',
        '    fi',
        'fi',
        '',
        'case "$BOOTLOADER" in',
        '    grub)',
        '        echo "Updating GRUB configuration..."',
        '        if grub-mkconfig -o /boot/grub/grub.cfg; then',
        '            echo "✓ GRUB updated successfully"',
        '        else',
        '            echo "✗ ERROR: Failed to update GRUB"',
        '            exit 1',
        '        fi',
        '        ;;',
        '    systemd-boot)',
        '        echo "Creating systemd-boot entry..."',
        '        BOOT_ENTRY="/boot/loader/entries/${INSTALL_VERSION}.conf"',
        '        ROOT_PARTUUID=$(blkid -s PARTUUID -o value $(findmnt -n -o SOURCE /) 2>/dev/null)',
        '        if [ -z "$ROOT_PARTUUID" ]; then',
        '            ROOT_DEVICE=$(findmnt -n -o SOURCE /)',
        '            echo "WARNING: Could not detect PARTUUID, using device: $ROOT_DEVICE"',
        '        fi',
        '        cat > "$BOOT_ENTRY" <<EOF',
        'title   Custom Kernel ${INSTALL_VERSION}',
        'linux   /vmlinuz-${INSTALL_VERSION}',
        'initrd  /initramfs-${INSTALL_VERSION}.img',
        'options root=PARTUUID=${ROOT_PARTUUID:-UUID=$(blkid -s UUID -o value $ROOT_DEVICE)} rw',
        'EOF',
        '        if [ -f "$BOOT_ENTRY" ]; then',
        '            echo "✓ systemd-boot entry created: $BOOT_ENTRY"',
        '            cat "$BOOT_ENTRY"',
        '        else',
        '            echo "✗ ERROR: Failed to create boot entry"',
        '            exit 1',
        '        fi',
        '        ;;',
        '    none)',
        '        echo "Skipping bootloader update (manual configuration selected)"',
        '        echo ""',
        '        echo "Kernel files installed:"',
        '        echo "  - Kernel: /boot/vmlinuz-${INSTALL_VERSION}"',
        '        echo "  - Initramfs: /boot/initramfs-${INSTALL_VERSION}.img"',
        '        echo "  - Config: /boot/config-${INSTALL_VERSION}"',
        '        echo ""',
        '        echo "Please update your bootloader configuration manually."',
        '        ;;',
        '    *)',
        '        echo "WARNING: Unknown bootloader or no bootloader detected"',
        '        echo "Installed files:"',
        '        echo "  - Kernel: /boot/vmlinuz-${INSTALL_VERSION}"',
        '        echo "  - Initramfs: /boot/initramfs-${INSTALL_VERSION}.img"',
        '        echo "  - Config: /boot/config-${INSTALL_VERSION}"',
        '        echo ""',
        '        echo "Please update your bootloader manually."',
        '        ;;',
        'esac',
        '',
        'echo ""',
        'echo "================================================"',
        'echo "  Kernel Compilation Complete!"',
        'echo "================================================"',
        'echo ""',
        'echo "Kernel installed: ${INSTALL_VERSION}"',
        'echo "Location: /boot/vmlinuz-${INSTALL_VERSION}"',
        'echo "Modules: /lib/modules/${INSTALL_VERSION}"',
        'echo ""',
        'echo "You can now reboot and select the new kernel from your bootloader menu."',
        'echo ""',
        '',
        'ls -lh /boot/*${INSTALL_VERSION}* 2>/dev/null || true',
    ])
    
    return '\n'.join(script_lines)
