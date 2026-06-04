# SPDX-License-Identifier: AGPL-3.0-or-later
import subprocess
from pathlib import Path


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
                stderr=subprocess.DEVNULL, timeout=30,
            ).decode()
            _parse_desc_batch(output, descs)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass

    avail_names = [n for n in names if n not in installed]
    if avail_names:
        try:
            output = subprocess.check_output(
                ['pacman', '-Si'] + avail_names,
                stderr=subprocess.DEVNULL, timeout=30,
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
        output = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=10).decode()
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
            ['pacman', '-Q'], stderr=subprocess.DEVNULL, timeout=15
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
            ['pacman', '-Sl'], stderr=subprocess.DEVNULL, timeout=15
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
