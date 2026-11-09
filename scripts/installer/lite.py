"""OpenRC-specific target configuration and validation (never run on the host)."""
import configparser
from pathlib import Path
import re
import shutil

from runtime import chroot, output, put

SERVICES = {
    'sysinit': ('starch-banner', 'udev', 'udev-trigger', 'cgroups'),
    'boot': ('sysctl', 'esysusers', 'etmpfiles-setup', 'elogind', 'agetty.tty2'),
    'default': ('dbus', 'NetworkManager', 'nftables', 'bluetoothd', 'starch-zram',
                'syslog-ng', 'sddm', 'iio-sensor-proxy'),
}


def enabled_services(xfce=False, cosmic=False):
    # Both desktops need a recovery console started before the display manager.
    services = dict(SERVICES)
    if cosmic:
        services['default'] = tuple(s for s in services['default'] if s != 'sddm')
    if xfce:
        services['default'] = tuple('lightdm' if s == 'sddm' else s
                                    for s in services['default'])
    return services


def efi_stub(root):
    # egummiboot 262 uses the upstream directory; retain older Artix layouts.
    candidates = (
        '/usr/lib/systemd/boot/efi/linuxx64.efi.stub',
        '/usr/lib/esys-utils/boot/efi/linuxx64.efi.stub',
    )
    for name in candidates:
        if (root / name.lstrip('/')).is_file():
            return name
    raise RuntimeError('Missing Lite EFI stub from egummiboot; checked: '
                       + ', '.join(candidates))


def configure(root, xfce=False, cosmic=False):
    if xfce and cosmic:
        raise RuntimeError("Xfce and COSMIC are mutually exclusive.")
    if not cosmic:
        shutil.copytree(root / "usr/share/starch-lite/legacy-desktop-config",
                        root / "etc/xdg", dirs_exist_ok=True)
        shutil.copytree(root / "usr/share/starch-lite/legacy-wayland-sessions",
                        root / "usr/share/wayland-sessions", dirs_exist_ok=True)
    # Calamares has already written the hostname and keyboard/locale files.
    hostname = (root / 'etc/hostname').read_text().strip()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9.-]*', hostname):
        raise RuntimeError('Invalid target hostname for OpenRC.')
    vconsole = (root / 'etc/vconsole.conf').read_text()
    keymap = re.search(r'^KEYMAP=["\']?([A-Za-z0-9_+./-]+)', vconsole, re.M)
    if not keymap:
        raise RuntimeError('Missing console keymap for OpenRC.')
    put(root, 'etc/conf.d/keymaps', f'keymap="{keymap[1]}"\n')
    put(root, 'etc/conf.d/hwclock', 'clock="UTC"\n')
    if xfce:
        # Keep the native Xfce launcher and Artix LightDM session wrapper.
        shutil.copyfile(root / 'usr/share/xsessions/xfce.desktop',
                        root / 'usr/share/starch-lite/xsessions/starch-xfce.desktop')
        shutil.copytree(root / 'usr/share/starch-lite/xfce-config', root / 'etc/xdg',
                        dirs_exist_ok=True)
        put(root, 'etc/lightdm/lightdm.conf',
            '[LightDM]\nsessions-directory=/usr/share/starch-lite/xsessions\n'
            '\n[Seat:*]\ngreeter-session=lightdm-slick-greeter\n'
            'user-session=starch-xfce\nsession-wrapper=/etc/lightdm/Xsession\n'
            'autologin-user=\nallow-guest=false\n')
        put(root, 'etc/lightdm/slick-greeter.conf',
            '[Greeter]\nbackground=/usr/share/wallpapers/Starch-Evergreen/contents/images/3840x2160.jpg\n'
            'draw-user-backgrounds=false\n')
        for link in (root / 'etc/runlevels').glob('*/sddm'):
            chroot(root, 'rc-update', 'del', 'sddm', link.parent.name)
    elif not cosmic:
        # Only offer the wrapper that establishes a private Plasma session bus.
        put(root, 'usr/share/starch-lite/wayland-sessions/starch-lite.desktop',
            (root / 'usr/share/wayland-sessions/starch-lite.desktop').read_text())
        put(root, 'etc/sddm.conf.d/20-starch-lite.conf',
            '[Wayland]\nSessionDir=/usr/share/starch-lite/wayland-sessions\n')
        put(root, 'var/lib/sddm/state.conf', '[Last]\nSession=starch-lite.desktop\n', mode=0o600)
        chroot(root, 'chown', 'sddm:sddm', '/var/lib/sddm/state.conf')
    # Use Artix's maintained firewall service with Starch's existing rules.
    put(root, 'etc/conf.d/nftables',
        'NFTABLES_SAVE="/etc/nftables.conf"\nSAVE_ON_STOP="no"\n')
    manager = 'greetd' if cosmic else 'lightdm' if xfce else 'sddm'
    put(root, f'etc/conf.d/{manager}', 'rc_need="elogind dbus"\n')
    chroot(root, '/usr/lib/starch-lite/configure-pam')
    # Artix ships the daemon and sensor udev rules, but no OpenRC service.
    # Starting it without a sensor is harmless; it waits for device discovery.
    put(root, 'etc/init.d/iio-sensor-proxy',
        '#!/usr/bin/openrc-run\n'
        'description="Sensor orientation and ambient light proxy"\n'
        'supervisor="supervise-daemon"\n'
        'command="/usr/lib/iio-sensor-proxy"\n'
        'respawn_delay=5\n'
        'depend() {\n    need dbus\n    after udev-trigger\n}\n', mode=0o755)
    # Claim tty2 before the display manager starts; do not race a getty against it on tty1.
    console = 2
    for number in range(1, 7):
        for link in (root / 'etc/runlevels').glob(f'*/agetty.tty{number}'):
            if number == console and link.parent.name == 'boot':
                continue
            chroot(root, 'rc-update', 'del', link.name, link.parent.name)
    for tty in (f'tty{console}',):
        path = root / f'etc/init.d/agetty.{tty}'
        if not path.exists() and not path.is_symlink():
            path.symlink_to('agetty')
        conf = root / f'etc/conf.d/agetty.{tty}'
        if not conf.exists():
            shutil.copyfile(root / 'etc/conf.d/agetty', conf)
    for runlevel, services in enabled_services(xfce, cosmic).items():
        for service in services:
            chroot(root, 'rc-update', 'add', service, runlevel)


def validate_openrc_files(root, xfce=False):
    # OpenRC owns these default runlevel links, but disabling the extra
    # consoles intentionally removes them. Check every other packaged path.
    # The retained console is moved to boot; validate() checks its new link.
    optional = {f'/etc/runlevels/default/agetty.tty{number}'
                for number in range(1, 7)}
    paths = output(['arch-chroot', root, 'pacman', '-Qlq', 'openrc']).splitlines()
    if not paths:
        raise RuntimeError('OpenRC package file list is empty.')
    for name in paths:
        if name in optional:
            continue
        path = root / name.lstrip('/')
        if not path.exists() and not path.is_symlink():
            raise RuntimeError(f'Missing OpenRC package file: {name}')


def validate(root, xfce=False, cosmic=False):
    if xfce and cosmic:
        raise RuntimeError("Xfce and COSMIC are mutually exclusive.")
    if xfce:
        for path in ('/usr/bin/startxfce4', '/usr/bin/Xorg', '/usr/bin/Thunar',
                     '/usr/bin/xfce4-screensaver', '/usr/bin/nm-applet',
                     '/usr/bin/xfce4-session',
                     '/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1'):
            chroot(root, 'test', '-x', path)
        config = configparser.ConfigParser()
        config.read(root / 'etc/lightdm/lightdm.conf')
        for section, key, expected in (
                ('LightDM', 'sessions-directory', '/usr/share/starch-lite/xsessions'),
                ('Seat:*', 'greeter-session', 'lightdm-slick-greeter'),
                ('Seat:*', 'user-session', 'starch-xfce'),
                ('Seat:*', 'session-wrapper', '/etc/lightdm/Xsession'),
                ('Seat:*', 'autologin-user', ''),
                ('Seat:*', 'allow-guest', 'false')):
            if config.get(section, key, fallback=None) != expected:
                raise RuntimeError(f'Incorrect Lite Xfce LightDM setting: {key}')
        if list((root / 'etc/runlevels').glob('*/sddm')):
            raise RuntimeError('SDDM must not be enabled for Lite Xfce.')
        chroot(root, 'pacman', '-Qk', 'lightdm', 'lightdm-openrc', 'lightdm-slick-greeter')
        chroot(root, 'test', '-f', '/usr/share/xgreeters/lightdm-slick-greeter.desktop')
        desktop = (root / 'usr/share/starch-lite/xsessions/starch-xfce.desktop').read_text()
        if not re.search(r'^Exec=startxfce4\s*$', desktop, re.M):
            raise RuntimeError('Xfce must use its native session launcher.')
    for number in range(1, 7):
        if number == 2:
            continue
        if list((root / 'etc/runlevels').glob(f'*/agetty.tty{number}')):
            raise RuntimeError(f'Extra Lite console is enabled: tty{number}')
    for name in ('usr/bin/openrc-init', 'usr/bin/openrc-run', 'usr/lib/elogind/elogind',
                 'usr/lib/security/pam_elogind.so', 'usr/bin/dbus-daemon',
                 'usr/lib/starch-lite/audio-session', 'usr/bin/pipewire',
                 'usr/bin/pipewire-pulse', 'usr/bin/wireplumber', 'usr/bin/pw-cli',
                 'usr/bin/pactl', 'usr/bin/flock',
                 'etc/sysctl.d/99-low-ram.conf'):
        if not (root / name).is_file():
            raise RuntimeError(f'Missing Lite component: {name}')
    for runlevel, services in enabled_services(xfce, cosmic).items():
        for service in services:
            link = root / 'etc/runlevels' / runlevel / service
            if not link.is_symlink():
                raise RuntimeError(f'OpenRC service is not enabled: {service}')
            chroot(root, 'test', '-x', f'/etc/runlevels/{runlevel}/{service}')
    for name in (('system-login',) if cosmic else ('system-login', 'lightdm-greeter' if xfce else 'sddm-greeter')):
        pam = (root / 'etc/pam.d' / name).read_text()
        if 'session required pam_elogind.so' not in pam or 'pam_systemd.so' in pam:
            raise RuntimeError(f'Incorrect Lite PAM session configuration: {name}')
    if not xfce and not cosmic:
        for name in ("usr/lib/starch-lite/plasma-session", "usr/lib/starch-lite/plasma-session-inner",
                     "etc/xdg/autostart/starch-audio.desktop"):
            if not (root / name).is_file():
                raise RuntimeError(f"Missing Lite Plasma component: {name}")
        config = configparser.ConfigParser()
        config.read(root / 'etc/xdg/startkderc')
        if config.getboolean('General', 'systemdBoot', fallback=True):
            raise RuntimeError('Lite Plasma must use its non-systemd session startup.')
    hooks = (root / 'etc/mkinitcpio.conf.d/10-starch.conf').read_text()
    if re.search(r'\b(systemd|sd-vconsole)\b', hooks) or 'udev' not in hooks:
        raise RuntimeError('Lite initramfs must use udev hooks without systemd.')
    validate_openrc_files(root, xfce=xfce)
    chroot(root, 'pacman', '-Qk', 'starch-lite', 'elogind', 'artix-archlinux-support', 'linux-zen')
