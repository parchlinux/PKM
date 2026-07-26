# SPDX-License-Identifier: AGPL-3.0-or-later
import os
import subprocess
from pathlib import Path

_PACMAN_ENV = {**os.environ, 'LC_ALL': 'C'}


# Known kernel flavors always included when available
STD_KERNELS = frozenset({
    'linux', 'linux-lts', 'linux-zen', 'linux-hardened',
    'linux-rt', 'linux-rt-lts',
})

# Packages starting with 'linux' that are definitely NOT kernels
EXPLICIT_EXCLUDE = frozenset({
    'linux-atm',
    'linux-tools-meta',
    'linux-wifi-hotspot',
    'linux-wifi-hotspot-debug',
    'linux-wifi-hotspot-git',
    'linux-wifi-hotspot-git-debug',
})


class KernelInfo:
    def __init__(self, name, version, description, installed=False):
        self.name = name
        self.version = version
        self.description = description
        self.installed = installed


def discover_kernels():
    installed = _get_installed_packages()
    available = _get_available_packages()
    pkgbase_kernels = _get_pkgbase_kernels()

    all_names = set(installed.keys()) | set(available.keys())
    candidates = [n for n in all_names if _is_kernel_candidate(n)]

    # Batch descriptions once (avoids per-package pacman calls)
    descriptions = _batch_get_descriptions(candidates, installed)

    # Start with pkgbase-confirmed kernels
    kernel_set = set(pkgbase_kernels)

    # Always include standard kernels if available
    kernel_set.update(n for n in candidates if n in STD_KERNELS)

    # Filter remaining candidates by description
    for name in candidates:
        if name in kernel_set:
            continue
        desc = descriptions.get(name, '').lower()
        if 'kernel' in desc:
            kernel_set.add(name)

    # Build final list
    kernels = []
    for name in sorted(kernel_set):
        version = installed.get(name) or available.get(name) or 'Unknown'
        is_installed = name in installed
        desc = descriptions.get(name) or _get_description(name, is_installed)
        if not desc:
            desc = f'{name} kernel'
        kernels.append(KernelInfo(name, version, desc, is_installed))

    return kernels


def _is_kernel_candidate(name):
    """Check if a package name could be a kernel package."""
    if not name.startswith('linux'):
        return False

    if name in EXPLICIT_EXCLUDE:
        return False

    # Exclude companion packages
    if name.endswith('-headers') or name.endswith('-docs'):
        return False

    # Exclude firmware and DKMS modules
    if '-firmware' in name or '-dkms' in name:
        return False

    # After 'linux', must have '-' or be exactly 'linux'
    # (excludes linuxsampler, linuxwave, linuxconsole, linuxdoc-tools, ...)
    rest = name[5:]
    return not rest or rest.startswith('-')


def _get_pkgbase_kernels():
    """Get kernel package names from /usr/lib/modules/*/pkgbase."""
    kernels = set()
    try:
        modules_dir = Path('/usr/lib/modules')
        if modules_dir.is_dir():
            for entry in modules_dir.iterdir():
                if entry.is_dir():
                    pkgbase_file = entry / 'pkgbase'
                    if pkgbase_file.is_file():
                        name = pkgbase_file.read_text().strip()
                        if name.startswith('linux'):
                            kernels.add(name)
    except (OSError, IOError):
        pass
    return kernels


def _batch_get_descriptions(names, installed):
    """Get descriptions for packages in batch (at most 2 pacman calls)."""
    descs = {}

    installed_names = [n for n in names if n in installed]
    if installed_names:
        try:
            output = subprocess.check_output(
                ['pacman', '-Qi'] + installed_names,
                stderr=subprocess.DEVNULL, timeout=30, env=_PACMAN_ENV,
            ).decode()
            _parse_desc_batch(output, descs)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    avail_names = [n for n in names if n not in installed]
    if avail_names:
        try:
            output = subprocess.check_output(
                ['pacman', '-Si'] + avail_names,
                stderr=subprocess.DEVNULL, timeout=30, env=_PACMAN_ENV,
            ).decode()
            _parse_desc_batch(output, descs)
        except Exception:
            pass

    return descs


def _parse_desc_batch(output, descs):
    """Parse batch pacman -Qi/-Si output into descs dict."""
    current = None
    for line in output.splitlines():
        if line.startswith('Name '):
            current = line.split(':', 1)[1].strip()
        elif line.startswith('Description ') and current:
            desc = line.split(':', 1)[1].strip()
            if current not in descs:
                descs[current] = desc


def _get_description(name, installed):
    desc = ''
    try:
        cmd = ['pacman', '-Qi' if installed else '-Si', name]
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10, env=_PACMAN_ENV).decode()
        for line in output.splitlines():
            if line.startswith('Description '):
                desc = line.split(':', 1)[1].strip()
                break
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass
    return desc


def _get_installed_packages():
    try:
        output = subprocess.check_output(
            ['pacman', '-Q'], stderr=subprocess.DEVNULL, timeout=15, env=_PACMAN_ENV,
        ).decode()
        result = {}
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                result[parts[0]] = parts[1]
        return result
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return {}


def _get_available_packages():
    try:
        output = subprocess.check_output(
            ['pacman', '-Sl'], stderr=subprocess.DEVNULL, timeout=15, env=_PACMAN_ENV,
        ).decode()
        result = {}
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3:
                result[parts[1]] = parts[2]
        return result
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError):
        return {}



def get_active_kernel_pkg():
    try:
        version = subprocess.check_output(['uname', '-r'], timeout=5).decode().strip()
        pkgbase_path = Path(f'/usr/lib/modules/{version}/pkgbase')
        if pkgbase_path.exists():
            return pkgbase_path.read_text().strip()
        return ''
    except Exception:
        return ''


def get_active_kernel_version():
    try:
        return subprocess.check_output(['uname', '-r'], timeout=5).decode().strip()
    except Exception:
        return 'Unknown'


def get_dkms_status():
    """Return a dict mapping kernel_version -> list of installed/building DKMS modules."""
    dkms_map = {}
    try:
        output = subprocess.check_output(['dkms', 'status'], stderr=subprocess.DEVNULL, timeout=5, env=_PACMAN_ENV).decode()
        for line in output.splitlines():
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                mod_name = parts[0]
                kver_arch = parts[1]
                status_str = parts[2]
                kver = kver_arch.split()[0]
                if kver not in dkms_map:
                    dkms_map[kver] = []
                dkms_map[kver].append({
                    'module': mod_name,
                    'status': status_str,
                })
    except Exception:
        pass
    return dkms_map


def get_default_boot_kernel():
    """Detect default booted kernel from bootloader config (systemd-boot or GRUB)."""
    try:
        # systemd-boot check
        loader_conf = Path('/boot/loader/loader.conf')
        if not loader_conf.exists():
            loader_conf = Path('/boot/efi/loader/loader.conf')
        if loader_conf.exists():
            for line in loader_conf.read_text().splitlines():
                if line.strip().startswith('default'):
                    entry = line.split(maxsplit=1)[1].strip().replace('.conf', '')
                    return entry
        
        # GRUB check
        grub_default = Path('/etc/default/grub')
        if grub_default.exists():
            for line in grub_default.read_text().splitlines():
                if line.startswith('GRUB_DEFAULT='):
                    val = line.split('=', 1)[1].strip('"\': ')
                    return val
    except Exception:
        pass
    return ''


def get_kernel_details(kernel_info):
    """Retrieve extended information for a specific kernel."""
    details = {
        'name': kernel_info.name,
        'version': kernel_info.version,
        'installed': kernel_info.installed,
        'headers_installed': False,
        'installed_size': 'Unknown',
        'build_date': 'Unknown',
        'modules_dir': '',
        'modules_size': 'Unknown',
        'cmdline': '',
    }
    
    headers_pkg = f"{kernel_info.name}-headers"
    try:
        subprocess.check_output(['pacman', '-Q', headers_pkg], stderr=subprocess.DEVNULL, timeout=3, env=_PACMAN_ENV)
        details['headers_installed'] = True
    except Exception:
        details['headers_installed'] = False

    if kernel_info.installed:
        try:
            out = subprocess.check_output(['pacman', '-Qi', kernel_info.name], stderr=subprocess.DEVNULL, timeout=5, env=_PACMAN_ENV).decode()
            for line in out.splitlines():
                if line.startswith('Installed Size '):
                    details['installed_size'] = line.split(':', 1)[1].strip()
                elif line.startswith('Build Date '):
                    details['build_date'] = line.split(':', 1)[1].strip()
        except Exception:
            pass

        # Find module directory
        try:
            modules_base = Path('/usr/lib/modules')
            if modules_base.exists():
                for d in modules_base.iterdir():
                    if d.is_dir():
                        pkgbase = d / 'pkgbase'
                        if pkgbase.exists() and pkgbase.read_text().strip() == kernel_info.name:
                            details['modules_dir'] = str(d)
                            # Get size
                            du_out = subprocess.check_output(['du', '-sh', str(d)], stderr=subprocess.DEVNULL, timeout=5).decode()
                            details['modules_size'] = du_out.split()[0]
                            break
        except Exception:
            pass

    # Read current cmdline if active
    cmdline_file = Path('/proc/cmdline')
    if cmdline_file.exists():
        details['cmdline'] = cmdline_file.read_text().strip()

    return details


def get_orphaned_modules(installed_kernels):
    """Return list of module directories in /usr/lib/modules/ that do not match installed kernels."""
    orphans = []
    modules_dir = Path('/usr/lib/modules')
    if not modules_dir.exists():
        return orphans
    
    installed_pkgbases = {k.name for k in installed_kernels if k.installed}
    
    try:
        for entry in modules_dir.iterdir():
            if entry.is_dir():
                pkgbase_file = entry / 'pkgbase'
                if pkgbase_file.exists():
                    pkg_name = pkgbase_file.read_text().strip()
                    if pkg_name not in installed_pkgbases:
                        orphans.append({'path': str(entry), 'name': pkg_name, 'dir_name': entry.name})
                else:
                    orphans.append({'path': str(entry), 'name': 'Unknown / Orphaned', 'dir_name': entry.name})
    except Exception:
        pass
    return orphans

