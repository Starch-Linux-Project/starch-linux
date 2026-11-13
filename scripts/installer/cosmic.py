"""COSMIC target-only greeter, authenticated login and session configuration."""
import re
import tomllib

from profiles import COSMIC_PACKAGES
from runtime import chroot, put
from media_defaults import validate_defaults

SESSION_DIR = 'usr/share/wayland-sessions'
PINS = ('firefox', 'com.system76.CosmicFiles', 'com.system76.CosmicTerm',
        'com.system76.CosmicSettings', 'linux-update-utility')
GREETER_COMMAND = '/usr/lib/starch-cosmic/greeter'


def configure(root, lite=False):
    # Package hooks can defer sysusers/tmpfiles setup in a chroot. The greeter
    # account and its owned directories must exist before validation and login,
    # rather than waiting for OpenRC's first-boot setup services.
    chroot(root, 'esysusers' if lite else 'systemd-sysusers',
           '/usr/lib/sysusers.d/cosmic-greeter.conf')
    chroot(root, 'etmpfiles' if lite else 'systemd-tmpfiles', '--create',
           '/usr/lib/tmpfiles.d/cosmic-greeter.conf')
    source = root / SESSION_DIR / 'cosmic.desktop'
    session = source.read_text()
    if not re.search(r'^Exec=/usr/bin/start-cosmic\s*$', session, re.M):
        raise RuntimeError('The packaged COSMIC launcher changed; review session integration.')
    if lite:
        # COSMIC Greeter discovers sessions through the standard XDG directory.
        session = session.replace('Exec=/usr/bin/start-cosmic', 'Exec=/usr/lib/starch-cosmic/session')
        source.write_text(session)
    for name in ('etc/sddm.conf', 'etc/sddm.conf.d/10-starch.conf',
                 'etc/sddm.conf.d/20-starch-lite.conf'):
        (root / name).unlink(missing_ok=True)
    put(root, 'etc/greetd/cosmic-greeter.toml',
        '[terminal]\nvt = 1\n\n[general]\nservice = "starch-greetd"\n'
        '\n[default_session]\ncommand = "' + GREETER_COMMAND + '"\nuser = "cosmic-greeter"\n')
    # Separate login PAM from the lock-screen service. system-local-login retains
    # faillock/access policies and registers the session with systemd/elogind.
    put(root, 'etc/pam.d/starch-greetd',
        'auth include system-local-login\nauth optional pam_gnome_keyring.so\n'
        'account include system-local-login\npassword include system-local-login\n'
        'session include system-local-login\nsession optional pam_gnome_keyring.so auto_start\n')
    # Calamares may use a restrictive umask. greetd executes this as its
    # unprivileged account, so the directory must also permit traversal.
    launcher_dir = root / 'usr/lib/starch-cosmic'
    launcher_dir.mkdir(parents=True, exist_ok=True)
    launcher_dir.chmod(0o755)
    put(root, GREETER_COMMAND.lstrip('/'),
        '#!/bin/sh\nset -eu\n'
        'export XDG_CURRENT_DESKTOP=COSMIC XDG_SESSION_DESKTOP=COSMIC XDG_SESSION_TYPE=wayland\n'
        'exec /usr/bin/dbus-run-session -- /usr/bin/cosmic-comp /usr/bin/cosmic-greeter\n', mode=0o755)
    if lite:
        for manager in ('sddm', 'lightdm', 'greetd'):
            for link in (root / 'etc/runlevels').glob('*/' + manager):
                chroot(root, 'rc-update', 'del', manager, link.parent.name)
        for name, executable, args, needs in (
                ('cosmic-greeter-daemon', '/usr/bin/cosmic-greeter-daemon', '', 'dbus'),
                ('cosmic-greeter', '/usr/bin/greetd', '--config /etc/greetd/cosmic-greeter.toml',
                 'dbus elogind cosmic-greeter-daemon')):
            put(root, 'etc/init.d/' + name,
                '#!/usr/bin/openrc-run\n'
                'supervisor="supervise-daemon"\n'
                f'command="{executable}"\ncommand_args="{args}"\n'
                f'pidfile="/run/{name}.pid"\nrespawn_delay=3\n'
                'depend() {\n    need ' + needs + '\n    after bootmisc\n}\n', mode=0o755)
            chroot(root, 'rc-update', 'add', name, 'default')
    else:
        put(root, 'etc/systemd/system/cosmic-greeter-daemon.service',
            '[Unit]\nDescription=COSMIC Greeter user helper\nAfter=dbus.service\n'
            '\n[Service]\nType=dbus\nBusName=com.system76.CosmicGreeter\n'
            'ExecStart=/usr/bin/cosmic-greeter-daemon\nRestart=on-failure\n')
        put(root, 'etc/systemd/system/cosmic-greeter.service',
            '[Unit]\nDescription=COSMIC Greeter\n'
            'After=systemd-user-sessions.service plymouth-quit-wait.service cosmic-greeter-daemon.service\n'
            'Requires=cosmic-greeter-daemon.service\nAfter=getty@tty1.service\nConflicts=getty@tty1.service\n'
            '\n[Service]\nExecStart=/usr/bin/greetd --config /etc/greetd/cosmic-greeter.toml\n'
            'Restart=always\nRestartSec=3\nIgnoreSIGPIPE=no\nSendSIGHUP=yes\n'
            'TimeoutStopSec=30\nKeyringMode=shared\n'
            '\n[Install]\nAlias=display-manager.service\n')
        # Only our configured greetd instance owns the seat.
        chroot(root, 'systemctl', 'mask', 'greetd.service', 'sddm.service', 'lightdm.service')
        chroot(root, 'systemctl', 'enable', '--force', 'cosmic-greeter.service')
        chroot(root, 'systemctl', '--global', 'enable', 'pipewire.socket',
               'pipewire-pulse.socket', 'wireplumber.service')


def validate(root, home, lite=False):
    validate_defaults(root)
    config = tomllib.loads((root / 'etc/greetd/cosmic-greeter.toml').read_text())
    if (config.get('terminal', {}).get('vt') != 1
            or config.get('general', {}).get('service') != 'starch-greetd'
            or config.get('default_session') != {'command': GREETER_COMMAND, 'user': 'cosmic-greeter'}
            or 'initial_session' in config):
        raise RuntimeError('COSMIC Greeter must own tty1 and require authenticated login.')
    pam = (root / 'etc/pam.d/starch-greetd').read_text()
    if 'session include system-local-login' not in pam or 'pam_gnome_keyring.so auto_start' not in pam:
        raise RuntimeError('COSMIC login PAM session/keyring integration is missing.')
    # Check access as the greeter without opening a PAM login session inside
    # the offline target. Lite requires pam_elogind in system-login (also used
    # by runuser), but the target's elogind is not running during installation.
    # Root's executable check alone would miss inaccessible parent directories.
    credentials = ('setpriv', '--reuid=cosmic-greeter', '--regid=cosmic-greeter',
                   '--init-groups', '--')
    chroot(root, *credentials, 'test', '-x', GREETER_COMMAND)
    chroot(root, *credentials, 'sh', '-n', GREETER_COMMAND)
    sessions = {p.name for p in (root / SESSION_DIR).glob('*.desktop')}
    if sessions != {'cosmic.desktop'} or list((root / 'usr/share/xsessions').glob('*.desktop')):
        raise RuntimeError('COSMIC Greeter must offer only the installed COSMIC session.')
    desktop = (root / SESSION_DIR / 'cosmic.desktop').read_text()
    launcher = '/usr/lib/starch-cosmic/session' if lite else '/usr/bin/start-cosmic'
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
                       '/usr/lib/polkit-gnome/polkit-gnome-authentication-agent-1', launcher):
        chroot(root, 'test', '-x', executable)
    agent = (root / 'etc/xdg/autostart/polkit-gnome-authentication-agent-1.desktop').read_text()
    if 'OnlyShowIn=COSMIC;' not in agent:
        raise RuntimeError('COSMIC authentication agent is not scoped to its session.')
    lock_pam = (root / 'etc/pam.d/cosmic-greeter').read_text()
    if 'auth include system-auth' not in lock_pam or 'account include system-auth' not in lock_pam:
        raise RuntimeError('COSMIC lock authentication must use the system PAM policy.')
    if lite:
        for manager in ('greetd', 'sddm', 'lightdm'):
            if list((root / 'etc/runlevels').glob('*/' + manager)):
                raise RuntimeError('A second display manager is enabled on Lite.')
        for service in ('cosmic-greeter', 'cosmic-greeter-daemon'):
            if not (root / 'etc/runlevels/default' / service).is_symlink():
                raise RuntimeError('COSMIC Greeter service is not enabled: ' + service)
            chroot(root, 'test', '-x', '/etc/init.d/' + service)
        if (root / 'etc/xdg/autostart/starch-audio.desktop').exists():
            raise RuntimeError('Lite COSMIC must have only one audio startup path.')
    else:
        for service in ('greetd', 'sddm', 'lightdm'):
            mask = root / ('etc/systemd/system/' + service + '.service')
            if not mask.is_symlink() or str(mask.readlink()) != '/dev/null':
                raise RuntimeError('Competing login service must be masked: ' + service)
        chroot(root, 'systemctl', 'is-enabled', 'cosmic-greeter.service')
        chroot(root, 'test', '/etc/systemd/system/display-manager.service', '-ef',
               '/etc/systemd/system/cosmic-greeter.service')
        if (root / 'usr/lib/starch-cosmic/session').exists():
            raise RuntimeError('Lite session supervisor leaked into a systemd target.')
        for service in ('pipewire.socket', 'pipewire-pulse.socket', 'wireplumber.service'):
            chroot(root, 'systemctl', '--global', 'is-enabled', service)
    chroot(root, 'pacman', '-Qk', *COSMIC_PACKAGES)
