"""Profile identity and verification of ISO-carried Starch Lite packages."""
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
    if has_xfce(gs):
        return 'lite-xfce'
    return 'lite' if is_lite(gs) else 'standard'


def has_xfce(gs):
    return is_lite(gs) and gs.value('starchLiteXfce') is True


XFCE_PACKAGES = (
    'xfce4-session', 'xfce4-panel', 'xfce4-settings', 'xfconf', 'xfdesktop',
    'xfwm4', 'thunar', 'thunar-volman', 'tumbler', 'gvfs', 'gvfs-smb',
    'xfce4-power-manager', 'xfce4-screensaver',
    'xfce4-notifyd', 'xfce4-pulseaudio-plugin', 'xfce4-whiskermenu-plugin',
    'network-manager-applet', 'pavucontrol', 'xorg-server', 'xorg-xinit',
    'xorg-xrandr', 'adwaita-icon-theme', 'gnome-themes-extra', 'polkit-gnome',
    'xdg-desktop-portal-gtk', 'ristretto', 'xfce4-screenshooter', 'xfce4-taskmanager',
)

# Desktop packages must be removed before dependency resolution, not hidden
# behind the login screen after installation.
PLASMA_PACKAGES = {
    'plasma-desktop', 'plasma-workspace', 'plasma-keyboard', 'qt6-virtualkeyboard',
    'breeze', 'xdg-desktop-portal-kde', 'plasma-nm', 'plasma-pa', 'kscreen',
    'polkit-kde-agent', 'plasma-systemmonitor', 'spectacle', 'gwenview',
    'kwallet', 'kwallet-pam', 'kwalletmanager',
}


def kernel_name(gs):
    return 'linux-zen' if is_lite(gs) else 'linux-lts'


def lite_packages(packages, xfce=False):
    replacements = {'linux-lts': 'linux-zen', 'dbus-broker-units': 'dbus'}
    result = [replacements.get(p, p) for p in packages if p != 'zram-generator']
    if xfce:
        result = [p for p in result if p not in PLASMA_PACKAGES and p != 'nautilus']
    return list(dict.fromkeys(result + list(LITE_REPOSITORY_PACKAGES)
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
