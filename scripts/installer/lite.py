"""OpenRC-specific target configuration and validation (never run on the host)."""
import configparser
from pathlib import Path
import re
import shutil

from runtime import chroot, output, put

SERVICES = {
    'sysinit': ('starch-banner', 'udev', 'udev-trigger', 'cgroups'),
    'boot': ('sysctl', 'esysusers', 'etmpfiles-setup', 'elogind'),
    'default': ('dbus', 'NetworkManager', 'nftables', 'bluetoothd', 'starch-zram',
                'syslog-ng', 'sddm', 'agetty.tty1'),
}


def enabled_services(xfce=False):
    services = dict(SERVICES)
    if xfce:
        services['boot'] = (*services['boot'], 'agetty.tty2')
        services['default'] = tuple(s for s in services['default'] if s != 'agetty.tty1')
    return services


def configure(root, xfce=False):
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
    # Only offer the session wrapper that establishes a private session bus.
    sessions = root / 'usr/share/starch-lite/wayland-sessions'
    sessions.mkdir(parents=True, exist_ok=True)
    if not xfce:
        put(root, 'usr/share/starch-lite/wayland-sessions/starch-lite.desktop',
            (root / 'usr/share/wayland-sessions/starch-lite.desktop').read_text())
    put(root, 'etc/sddm.conf.d/20-starch-lite.conf',
        '[Wayland]\nSessionDir=/usr/share/starch-lite/wayland-sessions\n')
    if xfce:
        # Use the distribution's native startxfce4 session entry. Do not replace
        # the session bus established by SDDM and Artix's Xsession scripts.
        shutil.copyfile(root / 'usr/share/xsessions/xfce.desktop',
                        root / 'usr/share/starch-lite/xsessions/starch-xfce.desktop')
        # Override the shared Plasma greeter configuration: Xfce needs no KWin
        # and SDDM's embedded theme needs no plasma-workspace theme assets.
        put(root, 'etc/sddm.conf.d/10-starch.conf',
            '[General]\nDisplayServer=x11\n\n[Theme]\nCurrent=\n')
        shutil.copytree(root / 'usr/share/starch-lite/xfce-config', root / 'etc/xdg',
                        dirs_exist_ok=True)
        put(root, 'etc/sddm.conf.d/30-starch-xfce.conf',
            '[X11]\nSessionDir=/usr/share/starch-lite/xsessions\n')
        # Keep the session restriction in SDDM's highest-priority file too.
        # DisplayServer=x11 only selects the greeter's backend; it does not
        # prevent the greeter from offering installed Wayland sessions.
        (root / 'usr/share/starch-lite/no-wayland-sessions').mkdir(parents=True, exist_ok=True)
        config = configparser.ConfigParser(interpolation=None)
        config.optionxform = str
        config.read(root / 'etc/sddm.conf')
        for section, key, value in (
                ('General', 'DisplayServer', 'x11'),
                ('X11', 'SessionDir', '/usr/share/starch-lite/xsessions'),
                ('Wayland', 'SessionDir', '/usr/share/starch-lite/no-wayland-sessions')):
            if not config.has_section(section):
                config.add_section(section)
            config.set(section, key, value)
        with (root / 'etc/sddm.conf').open('w') as stream:
            config.write(stream)
    # SDDM selects its initial session from saved state, not General/DefaultSession.
    session = 'starch-xfce.desktop' if xfce else 'starch-lite.desktop'
    put(root, 'var/lib/sddm/state.conf', f'[Last]\nSession={session}\n', mode=0o600)
    chroot(root, 'chown', 'sddm:sddm', '/var/lib/sddm/state.conf')
    # Use Artix's maintained firewall service with Starch's existing rules.
    put(root, 'etc/conf.d/nftables',
        'NFTABLES_SAVE="/etc/nftables.conf"\nSAVE_ON_STOP="no"\n')
    put(root, 'etc/conf.d/sddm', 'rc_need="elogind dbus"\n')
    chroot(root, '/usr/lib/starch-lite/configure-pam')
    # Keep one text console; Xfce reserves tty2 for recovery beside the greeter.
    console = 2 if xfce else 1
    for number in range(1, 7):
        for link in (root / 'etc/runlevels').glob(f'*/agetty.tty{number}'):
            if number == console and link.parent.name == ('boot' if xfce else 'default'):
                continue
            chroot(root, 'rc-update', 'del', link.name, link.parent.name)
    for tty in (f'tty{console}',):
        path = root / f'etc/init.d/agetty.{tty}'
        if not path.exists() and not path.is_symlink():
            path.symlink_to('agetty')
        conf = root / f'etc/conf.d/agetty.{tty}'
        if not conf.exists():
            shutil.copyfile(root / 'etc/conf.d/agetty', conf)
    for runlevel, services in enabled_services(xfce).items():
        for service in services:
            chroot(root, 'rc-update', 'add', service, runlevel)


def validate_openrc_files(root, xfce=False):
    # OpenRC owns these default runlevel links, but disabling the extra
    # consoles intentionally removes them. Check every other packaged path.
    console = 2 if xfce else 1
    optional = {f'/etc/runlevels/default/agetty.tty{number}'
                for number in range(1, 7) if xfce or number != console}
    paths = output(['arch-chroot', root, 'pacman', '-Qlq', 'openrc']).splitlines()
    if not paths:
        raise RuntimeError('OpenRC package file list is empty.')
    for name in paths:
        if name in optional:
            continue
        path = root / name.lstrip('/')
        if not path.exists() and not path.is_symlink():
            raise RuntimeError(f'Missing OpenRC package file: {name}')


def validate(root, xfce=False):
    if xfce:
        for path in ('/usr/bin/startxfce4', '/usr/bin/Xorg', '/usr/bin/Thunar',
                     '/usr/bin/xfce4-screensaver', '/usr/bin/nm-applet',
                     '/usr/bin/xfce4-session',
                     '/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1'):
            chroot(root, 'test', '-x', path)
        config = configparser.ConfigParser()
        config.read(root / 'etc/sddm.conf.d/30-starch-xfce.conf')
        if config.get('X11', 'SessionDir', fallback='') != '/usr/share/starch-lite/xsessions':
            raise RuntimeError('The optional Xfce session is not enabled in SDDM.')
        config.read(root / 'etc/sddm.conf.d/10-starch.conf')
        if config.get('General', 'DisplayServer', fallback='') != 'x11':
            raise RuntimeError('Xfce requires the X11 login greeter.')
        config.read(root / 'etc/sddm.conf')
        if (config.get('Wayland', 'SessionDir', fallback='') !=
                '/usr/share/starch-lite/no-wayland-sessions' or
                list((root / 'usr/share/starch-lite/no-wayland-sessions').glob('*.desktop'))):
            raise RuntimeError('Xfce Lite must not offer Wayland sessions.')
        if config.get('X11', 'SessionDir', fallback='') != '/usr/share/starch-lite/xsessions':
            raise RuntimeError('The Xfce X11 session directory is overridden.')
        desktop = (root / 'usr/share/starch-lite/xsessions/starch-xfce.desktop').read_text()
        if not re.search(r'^Exec=startxfce4\s*$', desktop, re.M):
            raise RuntimeError('Xfce must use its native session launcher.')
    for number in range(1, 7):
        if number == (2 if xfce else 1):
            continue
        if list((root / 'etc/runlevels').glob(f'*/agetty.tty{number}')):
            raise RuntimeError(f'Extra Lite console is enabled: tty{number}')
    for name in ('usr/bin/openrc-init', 'usr/bin/openrc-run', 'usr/lib/elogind/elogind',
                 'usr/lib/security/pam_elogind.so', 'usr/bin/dbus-daemon',
                 'usr/lib/starch-lite/plasma-session', 'usr/lib/starch-lite/plasma-session-inner',
                 'usr/lib/starch-lite/audio-session', 'usr/bin/pipewire',
                 'usr/bin/pipewire-pulse', 'usr/bin/wireplumber', 'usr/bin/pw-cli',
                 'usr/bin/pactl', 'usr/bin/flock',
                 'etc/xdg/autostart/starch-audio.desktop',
                 'etc/sysctl.d/99-low-ram.conf'):
        if not (root / name).is_file():
            raise RuntimeError(f'Missing Lite component: {name}')
    for runlevel, services in enabled_services(xfce).items():
        for service in services:
            link = root / 'etc/runlevels' / runlevel / service
            if not link.is_symlink():
                raise RuntimeError(f'OpenRC service is not enabled: {service}')
            chroot(root, 'test', '-x', f'/etc/runlevels/{runlevel}/{service}')
    for name in ('system-login', 'sddm-greeter'):
        pam = (root / 'etc/pam.d' / name).read_text()
        if 'session required pam_elogind.so' not in pam or 'pam_systemd.so' in pam:
            raise RuntimeError(f'Incorrect Lite PAM session configuration: {name}')
    if not xfce:
        config = configparser.ConfigParser()
        config.read(root / 'etc/xdg/startkderc')
        if config.getboolean('General', 'systemdBoot', fallback=True):
            raise RuntimeError('Lite Plasma must use its non-systemd session startup.')
    hooks = (root / 'etc/mkinitcpio.conf.d/10-starch.conf').read_text()
    if re.search(r'\b(systemd|sd-vconsole)\b', hooks) or 'udev' not in hooks:
        raise RuntimeError('Lite initramfs must use udev hooks without systemd.')
    validate_openrc_files(root, xfce=xfce)
    chroot(root, 'pacman', '-Qk', 'starch-lite', 'elogind', 'artix-archlinux-support', 'linux-zen')
