"""COSMIC greeter, authenticated login and session configuration."""
import re
import tomllib

from profiles import COSMIC_PACKAGES
from runtime import chroot, put
from media_defaults import validate_defaults

SESSION_DIR = 'usr/share/wayland-sessions'
PINS = ('firefox', 'com.system76.CosmicFiles', 'com.system76.CosmicTerm',
        'io.missioncenter.MissionCenter', 'com.system76.CosmicSettings', 'linux-update-utility')
GREETER_COMMAND = '/usr/lib/starch-cosmic/greeter'


def validate_vendor_units(root):
    """Fresh installs must use pacman's units, not a stale full override.

    This is not an existing-system migration: leave any override untouched and
    fail with a review request instead of deleting administrator configuration.
    """
    for unit in ('cosmic-greeter.service', 'cosmic-greeter-daemon.service'):
        vendor = root / 'usr/lib/systemd/system' / unit
        if not vendor.is_file() or vendor.is_symlink():
            raise RuntimeError('Missing packaged COSMIC unit: ' + unit)
        for directory in ('etc/systemd/system', 'run/systemd/system'):
            override = root / directory / unit
            if override.exists() or override.is_symlink():
                raise RuntimeError('Review existing COSMIC unit override before installation: ' + str(override))


def write_login(root):
    """Write the shared greeter launcher and PAM configuration."""
    put(root, 'etc/greetd/cosmic-greeter.toml',
        '[terminal]\nvt = 1\n\n[general]\nservice = "starch-greetd"\n'
        '\n[default_session]\ncommand = "' + GREETER_COMMAND + '"\nuser = "cosmic-greeter"\n')
    # Separate login PAM from the lock-screen service. system-local-login retains
    # faillock/access policies and registers the session with systemd/elogind.
    put(root, 'etc/pam.d/starch-greetd',
        'auth include system-local-login\nauth optional pam_gnome_keyring.so\n'
        'account include system-local-login\npassword include system-local-login\n'
        'session include system-local-login\nsession optional pam_gnome_keyring.so auto_start\n')
    # Retained provisionally: upstream launcher equivalence for the private
    # bus, greeter environment and diagnostics needs a booted COSMIC test.
    # Calamares may use a restrictive umask. greetd executes this as its
    # unprivileged account, so the directory must also permit traversal.
    launcher_dir = root / 'usr/lib/starch-cosmic'
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_dir.chmod(0o755)
    put(root, GREETER_COMMAND.lstrip('/'),
        '#!/bin/sh\nset -eu\n'
        'export XDG_CURRENT_DESKTOP=COSMIC XDG_SESSION_DESKTOP=COSMIC XDG_SESSION_TYPE=wayland\n'
        'exec /usr/bin/dbus-run-session -- /usr/bin/cosmic-comp /usr/bin/cosmic-greeter\n', mode=0o755)


def configure(root):
    validate_vendor_units(root)
    # Repeat the scoped package hooks before validating the offline target.
    chroot(root, 'systemd-sysusers', '/usr/lib/sysusers.d/cosmic-greeter.conf')
    chroot(root, 'systemd-tmpfiles', '--create', '/usr/lib/tmpfiles.d/cosmic-greeter.conf')
    session = (root / SESSION_DIR / 'cosmic.desktop').read_text()
    if not re.search(r'^Exec=/usr/bin/start-cosmic\s*$', session, re.M):
        raise RuntimeError('The packaged COSMIC launcher changed; review session integration.')
    write_login(root)
    # Only our configured greetd instance owns the seat.
    chroot(root, 'systemctl', 'mask', 'greetd.service', 'sddm.service', 'lightdm.service')
    chroot(root, 'systemctl', 'enable', '--force', 'cosmic-greeter.service')
    chroot(root, 'systemctl', '--global', 'enable', 'pipewire.socket',
           'pipewire-pulse.socket', 'wireplumber.service')


def validate(root, home):
    validate_defaults(root)
    config = tomllib.loads((root / 'etc/greetd/cosmic-greeter.toml').read_text())
    if (config.get('terminal', {}).get('vt') != 1
            or config.get('general', {}).get('service') != 'starch-greetd'
            or config.get('default_session') != {'command': GREETER_COMMAND, 'user': 'cosmic-greeter'}
            or 'initial_session' in config):
        raise RuntimeError('COSMIC Greeter must own tty1 and require authenticated login.')
    pam = (root / 'etc/pam.d/starch-greetd').read_text()
    required_pam = ('auth include system-local-login', 'account include system-local-login',
                    'password include system-local-login', 'session include system-local-login',
                    'auth optional pam_gnome_keyring.so',
                    'session optional pam_gnome_keyring.so auto_start')
    if any(line not in pam.splitlines() for line in required_pam):
        raise RuntimeError('COSMIC login PAM session/keyring integration is missing.')
    # Check access as the greeter without opening a PAM login session inside
    # the offline target. Lite requires pam_elogind in system-login (also used
    # by runuser), but the target's elogind is not running during installation.
    # Root's executable check alone would miss inaccessible parent directories.
    credentials = ('setpriv', '--reuid=cosmic-greeter', '--regid=cosmic-greeter',
                   '--init-groups', '--')
    chroot(root, 'getent', 'passwd', 'cosmic-greeter')
    chroot(root, 'getent', 'group', 'cosmic-greeter')
    for directory in ('/var/lib/cosmic-greeter', '/run/cosmic-greeter'):
        chroot(root, *credentials, 'test', '-d', directory)
        chroot(root, *credentials, 'test', '-O', directory)
    chroot(root, *credentials, 'test', '-x', GREETER_COMMAND)
    chroot(root, *credentials, 'sh', '-n', GREETER_COMMAND)
    sessions = {p.name for p in (root / SESSION_DIR).glob('*.desktop')}
    if sessions != {'cosmic.desktop'} or list((root / 'usr/share/xsessions').glob('*.desktop')):
        raise RuntimeError('COSMIC Greeter must offer only the installed COSMIC session.')
    desktop = (root / SESSION_DIR / 'cosmic.desktop').read_text()
    launcher = '/usr/bin/start-cosmic'
    if not re.search(r'^Exec=' + re.escape(launcher) + r'\s*$', desktop, re.M):
        raise RuntimeError('Incorrect COSMIC session launcher.')
    for name in ('usr/share/wayland-sessions/cosmic.desktop',
                 'usr/share/xdg-desktop-portal/portals/cosmic.portal',
                 'usr/share/xdg-desktop-portal/cosmic-portals.conf',
                 'usr/share/dbus-1/services/org.freedesktop.secrets.service',
                 'usr/share/dbus-1/system.d/com.system76.CosmicGreeter.conf',
                 'usr/lib/sysusers.d/cosmic-greeter.conf',
                 'usr/lib/tmpfiles.d/cosmic-greeter.conf',
                 'usr/share/dbus-1/services/org.freedesktop.impl.portal.desktop.cosmic.service'):
        if not (root / name).is_file():
            raise RuntimeError(f'Missing COSMIC component: {name}')
    for entry in PINS:
        if not (root / 'usr/share/applications' / (entry + '.desktop')).is_file():
            raise RuntimeError(f'Missing COSMIC dock application: {entry}')
    osk = home / '.local/state/cosmic/com.system76.CosmicOSK/v1/ime_activation'
    if not osk.is_file() or osk.read_text().strip() != 'false':
        raise RuntimeError('COSMIC manual on-screen keyboard default was not seeded.')
    seeded = root / 'etc/skel/.config/cosmic'
    if not seeded.is_dir() or not list(seeded.rglob('*')):
        raise RuntimeError('COSMIC defaults were not staged.')
    for path in seeded.rglob('*'):
        if path.is_file() and (home / '.config/cosmic' / path.relative_to(seeded)).read_bytes() != path.read_bytes():
            raise RuntimeError(f'COSMIC defaults were not applied before user creation: {path.name}')
    for name in ('kdeglobals', 'kwinrc', 'baloofilerc'):
        if (home / '.config' / name).exists() or (root / 'etc/xdg' / name).exists():
            raise RuntimeError('Plasma defaults leaked into the COSMIC target.')
    if (root / 'etc/xdg/startkderc').exists():
        raise RuntimeError('Plasma startup configuration leaked into COSMIC.')
    for executable in ('/usr/bin/start-cosmic', '/usr/bin/cosmic-session', '/usr/bin/cosmic-comp',
                       '/usr/bin/cosmic-greeter', '/usr/bin/cosmic-greeter-daemon', '/usr/bin/greetd', GREETER_COMMAND,
                       '/usr/bin/cosmic-osd', launcher):
        chroot(root, 'test', '-x', executable)
    validate_vendor_units(root)
    if (root / 'etc/xdg/autostart/polkit-gnome-authentication-agent-1.desktop').exists():
        raise RuntimeError('Redundant GNOME polkit autostart in the COSMIC target.')
    # The reviewed Arch greeter reverts the locker PAM change to use login.
    # Do not infer runtime PAM selection from an unused cosmic-greeter file.
    chroot(root, 'test', '-r', '/etc/pam.d/login')
    for service in ('greetd', 'sddm', 'lightdm'):
        mask = root / ('etc/systemd/system/' + service + '.service')
        if not mask.is_symlink() or str(mask.readlink()) != '/dev/null':
            raise RuntimeError('Competing login service must be masked: ' + service)
    chroot(root, 'systemctl', 'is-enabled', 'cosmic-greeter.service')
    chroot(root, 'test', '/etc/systemd/system/display-manager.service', '-ef',
           '/usr/lib/systemd/system/cosmic-greeter.service')
    if (root / 'usr/lib/starch-cosmic/session').exists():
        raise RuntimeError('Lite session supervisor leaked into a systemd target.')
    for service in ('pipewire.socket', 'pipewire-pulse.socket', 'wireplumber.service'):
        chroot(root, 'systemctl', '--global', 'is-enabled', service)
    chroot(root, 'pacman', '-Qk', *COSMIC_PACKAGES)
