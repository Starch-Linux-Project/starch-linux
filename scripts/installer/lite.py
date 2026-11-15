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
                'syslog-ng', 'sddm'),
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
    if not cosmic and not xfce:
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
                 'usr/bin/pipewire',
                 'usr/bin/pipewire-pulse', 'usr/bin/wireplumber', 'usr/bin/pw-cli',
                 'usr/bin/pactl',
                 'etc/sysctl.d/99-low-ram.conf'):
        if not (root / name).is_file():
            raise RuntimeError(f'Missing Lite component: {name}')
    for runlevel, services in enabled_services(xfce, cosmic).items():
        for service in services:
            link = root / 'etc/runlevels' / runlevel / service
            if not link.is_symlink():
                raise RuntimeError(f'OpenRC service is not enabled: {service}')
            chroot(root, 'test', '-x', f'/etc/runlevels/{runlevel}/{service}')
    if xfce:
        validate_user_services(root)
    if not xfce and not cosmic:
        for name in ("usr/lib/starch-lite/plasma-session", "usr/lib/starch-lite/plasma-session-inner"):
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


USER_SERVICES = {'boot': ('dbus',), 'default': ('pipewire', 'pipewire-pulse', 'wireplumber')}


def seed_user_services(root):
    """Fresh-install defaults only; Calamares copies these before first login."""
    for runlevel, services in USER_SERVICES.items():
        directory = root / 'etc/skel/.config/rc/runlevels' / runlevel
        directory.mkdir(parents=True, exist_ok=True)
        for service in services:
            link = directory / service
            destination = f'/etc/user/init.d/{service}'
            if link.is_symlink() and str(link.readlink()) == destination:
                continue
            if link.exists() or link.is_symlink():
                raise RuntimeError(f'Unexpected user-service default: {link}')
            link.symlink_to(destination)


def validate_user_runlevels(root, home, uid=None, gid=None):
    if uid is not None and uid < 1000:
        raise RuntimeError('Lite user services require an ordinary user with UID >= 1000.')
    if uid is not None:
        for relative in ('.config', '.config/rc', '.config/rc/runlevels',
                         '.config/rc/runlevels/boot', '.config/rc/runlevels/default'):
            directory = home / relative
            info = directory.lstat()
            if directory.is_symlink() or (info.st_uid, info.st_gid) != (uid, gid) or info.st_mode & 0o022:
                raise RuntimeError(f'Unsafe user-service directory: {directory}')
    for runlevel, services in USER_SERVICES.items():
        for service in services:
            link = home / '.config/rc/runlevels' / runlevel / service
            if not link.is_symlink() or str(link.readlink()) != f'/etc/user/init.d/{service}':
                raise RuntimeError(f'Missing upstream user runlevel: {link}')
            if uid is not None and (link.lstat().st_uid, link.lstat().st_gid) != (uid, gid):
                raise RuntimeError(f'Incorrect user-service ownership: {link}')
    # Include per-user overrides: stale copied launchers can survive package removal.
    for directory in (home / '.config/autostart', home / '.config/rc'):
        for path in directory.rglob('*'):
            if path.name == 'starch-audio.desktop':
                raise RuntimeError(f'Retired audio startup: {path}')
            if path.is_file() and not path.is_symlink():
                text = path.read_text(errors='replace')
                if 'starch-lite/audio-session' in text or competing_audio_autostart(path, text):
                    raise RuntimeError(f'Retired audio startup: {path}')
                if re.search(r'^\s*rc_autostart_user=[\"\']?(?:NO|no|false|0)', text, re.M):
                    raise RuntimeError(f'OpenRC user autostart disabled: {path}')


def validate_user_services(root):
    """Offline checks; login, recovery and final-logout behavior still need a VM."""
    for name in ('usr/lib/starch-lite/audio-session', 'usr/lib/starch-lite/configure-pam',
                 'usr/share/libalpm/hooks/95-starch-lite-pam.hook'):
        path = root / name
        if path.exists() or path.is_symlink():
            raise RuntimeError(f'Retired Lite integration remains: {name}')
    for directory in (root / 'etc/xdg', root / 'etc/skel', root / 'usr/share/starch-lite'):
        for path in directory.rglob('*'):
            if path.name == 'starch-audio.desktop' or (
                    path.is_file() and not path.is_symlink() and
                    ('starch-lite/audio-session' in path.read_text(errors='replace') or
                     competing_audio_autostart(path, path.read_text(errors='replace')))):
                raise RuntimeError(f'Retired audio startup: {path}')
    for service, dependencies in {'dbus': (), 'pipewire': ('dbus',),
                                  'pipewire-pulse': ('pipewire', 'dbus'),
                                  'wireplumber': ('pipewire', 'dbus')}.items():
        script = root / 'etc/user/init.d' / service
        text = script.read_text()
        if not script.stat().st_mode & 0o111 or not re.search(
                r'^supervisor=[\"\']?supervise-daemon[\"\']?$', text, re.M):
            raise RuntimeError(f'Missing upstream user supervision: {service}')
        needs = set(' '.join(re.findall(r'^\s*need\s+([^#\n]+)', text, re.M)).split())
        if not set(dependencies) <= needs:
            raise RuntimeError(f'Missing upstream user-service dependencies: {service}')
        if service != 'dbus' and list((root / 'etc/runlevels').glob(f'*/{service}')):
            raise RuntimeError(f'Audio must run as a user service: {service}')
        chroot(root, 'test', '-x', f'/etc/user/init.d/{service}')
    def pam(name, pattern):
        text = (root / 'etc/pam.d' / name).read_text()
        if not re.search(pattern, text, re.M) or re.search(r'^[^#\n]*pam_systemd\.so', text, re.M):
            raise RuntimeError(f'Missing upstream PAM session integration: {name}')
    for phase in ('auth', 'account', 'password'):
        pam('lightdm', rf'^{phase}\s+include\s+system-login\s*$')
        pam('system-login', rf'^{phase}\s+include\s+system-auth\s*$')
    pam('lightdm', r'^session\s+include\s+system-login\s*$')
    pam('system-login', r'^-?session\s+(?:optional|required)\s+pam_elogind\.so(?:\s|$)')
    pam('system-login', r'^session\s+\[default=1 success=ignore\]\s+pam_succeed_if\.so uid >= 1000\n-session\s+optional\s+pam_openrc\.so\s*$')
    pam('openrc-user', r'^session\s+(?:include|substack)\s+system-local-login\s*$')
    pam('system-local-login', r'^session\s+include\s+system-login\s*$')
    pam('lightdm-greeter', r'^session\s+(?:optional|required)\s+pam_elogind\.so(?:\s|$)')
    for name in ('pam_elogind.so', 'pam_openrc.so'):
        chroot(root, 'test', '-f', f'/usr/lib/security/{name}')
    chroot(root, 'test', '-x', '/usr/lib/openrc/bin/openrc-user')
    chroot(root, 'test', '-x', '/etc/init.d/user')
    chroot(root, 'test', '-x', '/etc/X11/xinit/xinitrc.d/80-dbus.sh')
    for config in [root / 'etc/rc.conf', *(root / 'etc/rc.conf.d').glob('*')]:
        if config.is_file() and re.search(r'^\s*rc_autostart_user=[\"\']?(?:NO|no|false|0)', config.read_text(), re.M):
            raise RuntimeError(f'OpenRC PAM autostart disabled: {config}')
    validate_user_runlevels(root, root / 'etc/skel')
    # validate_openrc_files() permits only the getty links deliberately removed
    # by configure(); a blanket -Qk openrc would reject every such install.
    chroot(root, 'pacman', '-Qk', 'pambase', 'dbus-openrc',
           'pipewire-openrc', 'pipewire-pulse-openrc', 'wireplumber-openrc')


def competing_audio_autostart(path, text):
    """Reject direct XDG audio launchers alongside the selected user services."""
    return path.suffix == '.desktop' and re.search(
        r'^Exec=(?:/usr/bin/)?(?:pipewire(?:-pulse)?|wireplumber)(?:\s|$)', text, re.M)
