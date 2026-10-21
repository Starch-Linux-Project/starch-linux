"""Select target GPU packages from PCI IDs and current signed Arch metadata."""
from pathlib import Path
import re
import tempfile

from runtime import command, output


def display_devices(pci=Path('/sys/bus/pci/devices')):
    devices = []
    for path in sorted(pci.iterdir()):
        alias = (path / 'modalias').read_text().strip()
        match = re.fullmatch(r'pci:v([0-9A-F]{8})d([0-9A-F]{8})sv([0-9A-F]{8})'
                             r'sd([0-9A-F]{8})bc03sc[0-9A-F]{2}i[0-9A-F]{2}', alias, re.I)
        if match:
            devices.append(tuple(int(value, 16) for value in match.groups()))
    return devices


def supported_nvidia_ids(readme):
    # NVIDIA's open-module README lists device IDs, optionally qualified by
    # subsystem vendor/device. Never infer support from numeric ID ranges.
    rows = re.findall(r'^\|[^|]+\|\s*([0-9A-F]{4}(?:\s+[0-9A-F]{4}\s+[0-9A-F]{4})?)\s*\|\s*$',
                      readme, re.M | re.I)
    if not rows:
        raise RuntimeError('The NVIDIA package has no readable supported-GPU table.')
    return {tuple(int(value, 16) for value in row.split()) for row in rows}


def package_selection(devices, supported, kernel='linux-lts'):
    vendors = {device[0] for device in devices}
    packages = []
    if 0x8086 in vendors:
        packages += ['vulkan-intel', 'intel-media-driver', 'libva-intel-driver']
    if 0x1002 in vendors:
        # Mesa in the base manifest also supplies AMD/Nouveau VA-API.
        packages.append('vulkan-radeon')
    nvidia = [device[1:] for device in devices if device[0] == 0x10de]
    if nvidia:
        # nvidia-utils blacklists Nouveau globally. Keep Nouveau available
        # when any NVIDIA GPU requires it, including mixed-generation PCs.
        if all(device in supported or (device[0],) in supported for device in nvidia):
            packages += (['nvidia-open-dkms', 'linux-zen-headers', 'nvidia-utils']
                         if kernel == 'linux-zen' else ['nvidia-open-lts', 'nvidia-utils'])
            if vendors & {0x8086, 0x1002}:
                packages.append('nvidia-prime')
        else:
            packages.append('vulkan-nouveau')
    return list(dict.fromkeys(packages))


def select_packages(pacman, state, kernel='linux-lts'):
    devices = display_devices()
    supported = set()
    if any(device[0] == 0x10de for device in devices):
        # Read the compatibility table from a signed package in the same
        # synchronized Arch repositories used for installation. This source
        # package is downloaded only for metadata, never installed or run.
        with tempfile.TemporaryDirectory(prefix='gpu-', dir=state) as temporary:
            cache = Path(temporary)
            command([*pacman, '--cachedir', cache, '-Swdd', '--noconfirm', 'nvidia-open-dkms'])
            archives = list(cache.glob('nvidia-open-dkms-*.pkg.tar.*'))
            archives = [path for path in archives if not path.name.endswith('.sig')]
            if len(archives) != 1:
                raise RuntimeError('Could not identify the NVIDIA compatibility package.')
            archive = archives[0]
            members = output(['bsdtar', '-tf', archive]).splitlines()
            readmes = [name for name in members
                       if re.fullmatch(r'usr/src/nvidia-[^/]+/README.md', name)]
            if len(readmes) != 1:
                raise RuntimeError('The NVIDIA package is missing its compatibility table.')
            readme = output(['bsdtar', '-xOf', archive, readmes[0]])
            supported = supported_nvidia_ids(readme)
            packages = package_selection(devices, supported, kernel)
            module = 'nvidia-open-dkms' if kernel == 'linux-zen' else 'nvidia-open-lts'
            if module in packages:
                versions = dict(line.split() for line in output([
                    *pacman, '-Sp', '--print-format', '%n %v', module]).splitlines())
                source_version = readmes[0].split('/')[2].removeprefix('nvidia-')
                utils_version = versions.get('nvidia-utils', '').split(':')[-1].rsplit('-', 1)[0]
                if source_version != utils_version:
                    raise RuntimeError('NVIDIA package metadata is out of sync. Retry after the mirror updates.')
    return package_selection(devices, supported, kernel)
