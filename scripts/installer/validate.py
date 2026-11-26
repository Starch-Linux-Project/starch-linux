import re
from runtime import chroot, output, preserve_logs, read_manifest, target
from profiles import KERNEL, COSMIC_FORBIDDEN, COSMIC_PACKAGES
import cosmic


def validate_machine_id(root):
    machine_id = (root / 'etc/machine-id').read_text().strip()
    if not re.fullmatch(r'[0-9a-f]{32}', machine_id) or machine_id == '0' * 32:
        raise RuntimeError('Installed machine ID is missing or invalid.')
    # Check through the target chroot below; absolute symlinks must not resolve
    # against the live host while examining the offline filesystem.
    if not (root / 'var/lib/dbus/machine-id').is_symlink() or (root / 'var/lib/dbus/machine-id').readlink().as_posix() != '/etc/machine-id':
        raise RuntimeError('D-Bus machine ID must link to /etc/machine-id.')


def run(gs):
    root = target(gs)
    kernel = KERNEL
    validate_machine_id(root)
    chroot(root, 'cmp', '/etc/machine-id', '/var/lib/dbus/machine-id')
    chroot(root, 'pacman', '-Qk', 'dbus', 'dbus-broker', 'dbus-broker-units')
    chroot(root, 'getent', 'passwd', 'dbus')
    chroot(root, 'getent', 'group', 'dbus')
    chroot(root, 'test', '-x', '/usr/lib/iio-sensor-proxy')
    chroot(root, 'test', '-x', '/usr/bin/monitor-sensor')
    chroot(root, 'pacman', '-Qk', 'iio-sensor-proxy')
    chroot(root, 'python3', '-c', 'from gi.repository import Gio, GLib')
    for path in ('/usr/lib/starch/rotation.py', '/etc/xdg/autostart/starch-rotation.desktop'):
        chroot(root, 'test', '-r', path)
    for path in ('/usr/bin/dbus-broker-launch', '/usr/bin/dbus-broker'):
        chroot(root, 'test', '-x', path)
    for unit in ('dbus.service', 'sockets.target.wants/dbus.socket'):
        chroot(root, 'test', '-f', '/usr/lib/systemd/system/' + unit)
    chroot(root, 'systemctl', 'is-enabled', 'dbus.socket')
    username = gs.value('username')
    users = {p[0]: p for p in (line.split(':') for line in (root / 'etc/passwd').read_text().splitlines())}
    if not isinstance(username, str) or username not in users or users[username][6] != '/usr/bin/fish':
        raise RuntimeError('The installed user is missing or has the wrong shell.')
    if 'liveuser' in users or users['root'][6] != '/usr/bin/bash':
        raise RuntimeError('Unexpected live account or root shell in the installed system.')
    home = root / users[username][5].lstrip('/')
    if not home.is_dir() or home.stat().st_uid != int(users[username][2]):
        raise RuntimeError('Installed home ownership is incorrect.')
    cosmic.validate(root, home)
    shadow = {p[0]: p[1] for p in (line.split(':') for line in (root / 'etc/shadow').read_text().splitlines())}
    if not shadow.get(username) or shadow[username][0] in '!*' or not shadow['root'].startswith(('!', '*')):
        raise RuntimeError('Installed account password state is incorrect.')
    for name in (f'boot/vmlinuz-{kernel}', 'etc/locale.conf', 'etc/hostname',
                 'usr/share/wayland-sessions/cosmic.desktop'):
        if not (root / name).is_file() or not (root / name).stat().st_size:
            raise RuntimeError(f'Missing installed file: {name}')
    for name, mode in {
        'usr/local/bin/linux-update-utility.AppImage': 0o755,
        'usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg': 0o644,
        'usr/share/applications/linux-update-utility.desktop': 0o644,
    }.items():
        artifact = root / name
        if not artifact.is_file() or artifact.stat().st_mode & 0o777 != mode:
            raise RuntimeError(f'Missing or incorrectly installed Linux Update Utility file: {name}')
    if (root / 'etc/starch-live').exists() or (root / 'etc/sudoers.d/10-starch-live').exists():
        raise RuntimeError('Live-only configuration leaked into the target.')
    if 'NOPASSWD' in (root / 'etc/sudoers.d/10-installer').read_text():
        raise RuntimeError('Installed sudo must require authentication.')
    chroot(root, 'visudo', '-c')
    chroot(root, 'pacman', '-Qk', 'base', kernel, 'limine', 'fish', 'greetd', 'networkmanager')
    locales = output(['arch-chroot', root, 'locale', '-a'])
    lang = re.search(r'^LANG=(.+)$', (root / 'etc/locale.conf').read_text(), re.M)
    normalize = lambda value: value.strip('"').lower().replace('-', '')
    if not lang or normalize(lang[1]) not in {normalize(value) for value in locales.splitlines()}:
        raise RuntimeError('The chosen locale was not generated.')
    if not (root / 'etc/localtime').is_symlink():
        raise RuntimeError('The selected timezone was not configured.')
    chroot(root, 'nft', '--check', '--file', '/etc/nftables.conf')
    for service in ('cosmic-greeter.service', 'NetworkManager.service', 'nftables.service',
                    'bluetooth.service', 'power-profiles-daemon.service'):
        chroot(root, 'systemctl', 'is-enabled', service)
    fstab = (root / 'etc/fstab').read_text()
    if not re.search(r'^UUID=\S+\s+/\s+ext4\s', fstab, re.M):
        raise RuntimeError('fstab does not identify the ext4 root by UUID.')
    if gs.value('firmwareType') == 'efi':
        if not re.search(r'^UUID=\S+\s+/boot/efi\s+vfat\s', fstab, re.M):
            raise RuntimeError('EFI mount is missing from fstab.')
        for name in ('boot/efi/EFI/Limine/BOOTX64.EFI', 'boot/efi/EFI/Limine/limine.conf',
                     'boot/efi/EFI/BOOT/BOOTX64.EFI', 'boot/efi/EFI/BOOT/limine.conf',
                     f'boot/efi/EFI/Linux/starch-{kernel}.efi'):
            if not (root / name).is_file() or not (root / name).stat().st_size:
                raise RuntimeError(f'Missing Limine EFI file: {name}')
        limine = (root / 'boot/efi/EFI/Limine/limine.conf').read_text()
        if 'protocol: efi' not in limine or f'EFI/Linux/starch-{kernel}.efi' not in limine:
            raise RuntimeError('Limine has no Starch UKI entry.')
    else:
        if not re.search(r'^UUID=\S+\s+/boot\s+vfat\s', fstab, re.M):
            raise RuntimeError('FAT32 BIOS /boot mount is missing from fstab.')
        for name in (f'boot/initramfs-{kernel}.img', 'boot/limine/limine-bios.sys',
                     'boot/limine/limine.conf'):
            if not (root / name).is_file() or not (root / name).stat().st_size:
                raise RuntimeError(f'Missing Limine BIOS file: {name}')
        config = (root / 'boot/limine/limine.conf').read_text()
        if (f'path: boot():/vmlinuz-{kernel}' not in config or
                f'module_path: boot():/initramfs-{kernel}.img' not in config):
            raise RuntimeError('Limine BIOS must load the kernel and initramfs from FAT32 /boot.')
    versions = output(['arch-chroot', root, 'pacman', '-Q'])
    requested = read_manifest(root / 'var/log/starch-installer/requested-packages.txt')
    missing = set(requested) - {line.split()[0] for line in versions.splitlines()}
    if missing:
        raise RuntimeError('Requested target packages are missing: ' + ', '.join(sorted(missing)))
    forbidden = {'calamares', 'grub', 'mkinitcpio-archiso', 'archinstall', 'linux'}
    forbidden.update(COSMIC_FORBIDDEN)
    resolved = (root / 'var/log/starch-installer/resolved-packages.txt').read_text()
    audited = {name: version for repo, name, version in (line.split() for line in resolved.splitlines())}
    installed = dict(line.split() for line in versions.splitlines())
    if any(installed.get(name) != audited.get(name) for name in COSMIC_PACKAGES):
        raise RuntimeError('COSMIC packages changed after preflight; review defaults and session compatibility.')
    if any(line.split()[0] in forbidden for line in versions.splitlines()):
        raise RuntimeError('Installer/live-only packages leaked into the target.')
    preserve_logs(root)
    (root / 'var/log/starch-installer/installed-packages.txt').write_text(versions + '\n')
    (root / 'var/log/starch-installer/result.txt').write_text('Target validation passed. First boot remains to be tested.\n')
    gs.insert('starchEssentialComplete', True)
