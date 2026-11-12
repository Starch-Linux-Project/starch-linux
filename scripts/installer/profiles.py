"""Installer desktop/init identity, package selection and Lite bundle verification."""
import hashlib
import json
from pathlib import Path
import re


LITE_PACKAGES = ('starch-lite',)
LITE_BUNDLE_PACKAGES = ('starch-lite', 'artix-keyring')
LITE_REPOSITORY_PACKAGES = (
    'openrc', 'elogind', 'elogind-openrc', 'dbus-openrc',
    'networkmanager-openrc', 'nftables-openrc', 'bluez-openrc', 'sddm-openrc',
    'syslog-ng-openrc', 'artix-keyring', 'artix-archlinux-support', 'eukify', 'egummiboot',
)


def is_lite(gs):
    return gs.value('starchLite') is True


def profile_name(gs):
    if desktop_name(gs) == 'cosmic':
        return 'lite-cosmic' if is_lite(gs) else 'standard-cosmic'
    if has_xfce(gs):
        return 'lite-xfce'
    return 'lite' if is_lite(gs) else 'standard'


def has_xfce(gs):
    return is_lite(gs) and desktop_name(gs) == 'xfce'


def desktop_name(gs):
    """Canonical desktop identity; accept state from older installer pages."""
    selected = gs.value('starchDesktop')
    if selected is None:
        return 'xfce' if is_lite(gs) and gs.value('starchLiteXfce') is True else 'plasma'
    if selected not in ('plasma', 'xfce', 'cosmic'):
        raise RuntimeError('Unknown Starch desktop selection.')
    return selected


def has_cosmic(gs):
    return desktop_name(gs) == 'cosmic'


def validate_selection(gs):
    """Reject unsafe/stale state before any disk or repository operations."""
    desktop = desktop_name(gs)
    legacy_xfce = gs.value('starchLiteXfce') is True
    if legacy_xfce and (not is_lite(gs) or desktop != 'xfce'):
        raise RuntimeError('Contradictory Starch Lite Xfce selection.')
    if desktop == 'xfce' and not is_lite(gs):
        raise RuntimeError('Xfce requires Starch Lite.')


def selected_packages(packages, gs):
    """Select the desktop and init profile before resolving dependencies."""
    validate_selection(gs)
    result = lite_packages(packages, xfce=has_xfce(gs)) if is_lite(gs) else list(packages)
    if has_cosmic(gs):
        result = [p for p in result if p not in PLASMA_PACKAGES | {'nautilus', 'blueman', 'sddm', 'sddm-openrc'}]
        result.extend(COSMIC_PACKAGES)
        if is_lite(gs):
            # Satisfy starch-lite's init-displaymanager dependency before its
            # local archive is installed; pacman's default provider uses dinit.
            # cosmic.configure disables the generic service in favor of ours.
            result.append('greetd-openrc')
    return list(dict.fromkeys(result))


XFCE_PACKAGES = (
    'xfce4-session', 'xfce4-panel', 'xfce4-settings', 'xfconf', 'xfdesktop',
    'xfwm4', 'thunar', 'thunar-volman', 'tumbler', 'gvfs', 'gvfs-smb',
    'xfce4-power-manager', 'xfce4-screensaver',
    'xfce4-notifyd', 'xfce4-pulseaudio-plugin', 'xfce4-whiskermenu-plugin',
    'network-manager-applet', 'pavucontrol', 'xorg-server', 'xorg-xinit',
    'xorg-xrandr', 'xorg-xinput', 'python-gobject', 'libnotify', 'adwaita-icon-theme', 'gnome-themes-extra', 'polkit-gnome',
    'xdg-desktop-portal-gtk', 'xdg-user-dirs', 'ristretto', 'xfce4-screenshooter', 'xfce4-taskmanager',
)

# Desktop packages must be removed before dependency resolution, not hidden
# behind the login screen after installation.
PLASMA_PACKAGES = {
    'plasma-desktop', 'plasma-workspace', 'plasma-keyboard', 'qt6-virtualkeyboard',
    'breeze', 'xdg-desktop-portal-kde', 'plasma-nm', 'plasma-pa', 'kscreen', 'qt6-sensors',
    'polkit-kde-agent', 'plasma-systemmonitor', 'spectacle', 'gwenview',
    'kwallet', 'kwallet-pam', 'kwalletmanager',
}


# Explicit roots, not the COSMIC group. The greeter is also the lock UI;
# greetd owns login only on COSMIC targets.
COSMIC_PACKAGES = (
    'cosmic-session', 'cosmic-comp', 'cosmic-panel', 'cosmic-applets',
    'cosmic-launcher', 'cosmic-app-library', 'cosmic-workspaces', 'cosmic-settings',
    'cosmic-settings-daemon', 'cosmic-bg', 'cosmic-notifications', 'cosmic-osd',
    'cosmic-idle', 'cosmic-files', 'cosmic-icon-theme', 'cosmic-greeter',
    'cosmic-randr', 'cosmic-screenshot', 'cosmic-osk',
    'cosmic-terminal', 'cosmic-text-editor', 'xdg-desktop-portal-cosmic',
    'xdg-desktop-portal', 'xdg-desktop-portal-gtk', 'xorg-xwayland',
    'xorg-server', 'xorg-xauth', 'polkit-gnome', 'gnome-keyring', 'xdg-user-dirs',
    # COSMIC replaces Blueman's UI, but configure still enables bluetooth.service.
    'bluez', 'greetd', 'python-gobject', 'libnotify',
)
COSMIC_FORBIDDEN = PLASMA_PACKAGES | {
    'kwin', 'kwin-x11', 'plasma-x11-session', 'xfce4-session', 'xfwm4',
    'xfce4-panel', 'sddm', 'sddm-openrc', 'lightdm', 'lightdm-openrc', 'cosmic-store',
}


def check_cosmic_closure(resolved, lite=False):
    """Audit pacman's actual transaction, including transitive dependencies."""
    entries = [line.split() for line in resolved.splitlines() if line.strip()]
    if not entries or any(len(e) != 3 for e in entries):
        raise RuntimeError('Invalid COSMIC dependency-resolution report.')
    by_name = {name: (repo, version) for repo, name, version in entries}
    forbidden = COSMIC_FORBIDDEN | ({'systemd', 'systemd-libs', 'systemd-sysvcompat'} if lite else set())
    unexpected = forbidden & by_name.keys()
    if unexpected:
        raise RuntimeError('Incompatible COSMIC dependencies: ' + ', '.join(sorted(unexpected)))
    required = set(COSMIC_PACKAGES) | ({'greetd-openrc'} if lite else set())
    missing = required - by_name.keys()
    if missing:
        raise RuntimeError('Missing COSMIC packages: ' + ', '.join(sorted(missing)))
    # These components define the defaults and non-systemd startup we inspected.
    for name in ('cosmic-session', 'cosmic-comp', 'cosmic-panel', 'cosmic-applets',
                 'cosmic-bg', 'cosmic-settings', 'cosmic-settings-daemon', 'cosmic-greeter',
                 'cosmic-osk', 'cosmic-randr',
                 'xdg-desktop-portal-cosmic'):
        repo, version = by_name[name]
        if version.split(':')[-1].rsplit('-', 1)[0] != '1.11.0':
            raise RuntimeError(f'Review COSMIC defaults/startup for {name} {version} before installing.')
        if lite and repo not in ('system', 'world', 'galaxy'):
            raise RuntimeError(f'Lite requires the maintained Artix build of {name}, got {repo}.')


def kernel_name(gs):
    return 'linux-zen' if is_lite(gs) else 'linux-lts'


def lite_packages(packages, xfce=False):
    replacements = {'linux-lts': 'linux-zen', 'dbus-broker-units': 'dbus'}
    result = [replacements.get(p, p) for p in packages if p not in {'zram-generator', 'iio-sensor-proxy', 'qt6-sensors'}]
    repository_packages = list(LITE_REPOSITORY_PACKAGES)
    if xfce:
        replacements = {'sddm': 'lightdm', 'sddm-openrc': 'lightdm-openrc'}
        result = [replacements.get(p, p) for p in result]
        repository_packages = [replacements.get(p, p) for p in repository_packages]
        result.append('lightdm-slick-greeter')
        result = [p for p in result if p not in PLASMA_PACKAGES and p != 'nautilus']
    return list(dict.fromkeys(result + repository_packages
                              + (list(XFCE_PACKAGES) if xfce else [])))


def pacman_config(data, gs):
    return data / ('pacman-lite.conf' if is_lite(gs) else 'pacman.conf')


def verified_bundle(directory):
    """Reject obsolete custom runtimes as well as modified bundle inputs."""
    directory = Path(directory)
    manifest = directory / 'bundle.json'
    if directory.is_symlink() or manifest.is_symlink() or not manifest.is_file():
        raise RuntimeError('The Starch Lite bundle is missing from this ISO. Rebuild the ISO.')
    try:
        bundle = json.loads(manifest.read_text())
        entries = bundle['packages']
        if (bundle['format'] != 2 or bundle['repositories'] != 'artix-arch-extra'
                or [e['name'] for e in entries] != list(LITE_BUNDLE_PACKAGES)):
            raise ValueError('unexpected bundle format or package set')
        result = []
        for entry in entries:
            name, filename, digest = entry['name'], entry['filename'], entry['sha256']
            if (not re.fullmatch(re.escape(name) + r'-[0-9][A-Za-z0-9.+_:-]*-(?:x86_64|any)\.pkg\.tar\.zst', filename)
                    or not re.fullmatch(r'[0-9a-f]{64}', digest)):
                raise ValueError('invalid package filename or checksum')
            path = directory / filename
            if path.is_symlink() or not path.is_file():
                raise ValueError('package must be a regular file')
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise ValueError(f'checksum mismatch: {filename}')
            result.append(path)
        return result
    except (KeyError, TypeError, ValueError) as error:
        raise RuntimeError(f'Invalid Starch Lite bundle: {error}') from error
