"""Package and session requirements of the Starch Linux desktop."""
import re


PROFILE = "standard-cosmic"
KERNEL = "linux-lts"


def validate_selection(gs):
    """Reject stale non-COSMIC choices before any disk operations."""
    if (gs.value('starchDesktop') not in (None, 'cosmic')
            or gs.value('starchLite') is True or gs.value('starchLiteXfce') is True):
        raise RuntimeError('This installer supports only the Starch Linux COSMIC desktop.')


PLASMA_PACKAGES = {
    'plasma-desktop', 'plasma-workspace', 'plasma-keyboard', 'qt6-virtualkeyboard',
    'breeze', 'xdg-desktop-portal-kde', 'plasma-nm', 'plasma-pa', 'kscreen', 'qt6-sensors',
    'polkit-kde-agent', 'plasma-systemmonitor', 'spectacle', 'gwenview',
    'kwallet', 'kwallet-pam', 'kwalletmanager',
}


# Explicit roots, not the COSMIC group. The greeter is also the lock UI;
# greetd owns login for the live and installed sessions.
COSMIC_PACKAGES = (
    'cosmic-session', 'cosmic-comp', 'cosmic-panel', 'cosmic-applets',
    'cosmic-launcher', 'cosmic-app-library', 'cosmic-workspaces', 'cosmic-settings',
    'cosmic-settings-daemon', 'cosmic-bg', 'cosmic-notifications', 'cosmic-osd',
    'cosmic-idle', 'cosmic-files', 'cosmic-icon-theme', 'cosmic-greeter',
    'cosmic-randr', 'cosmic-screenshot', 'cosmic-osk', 'cosmic-store', 'cosmic-viewer',
    'cosmic-terminal', 'cosmic-text-editor', 'xdg-desktop-portal-cosmic',
    'xdg-desktop-portal', 'xdg-desktop-portal-gtk', 'xorg-xwayland',
    'xorg-server', 'xorg-xauth', 'gnome-keyring', 'xdg-user-dirs',
    # COSMIC replaces Blueman's UI, but configure still enables bluetooth.service.
    # Its battery applet uses power-profiles-daemon for profile selection.
    'bluez', 'power-profiles-daemon', 'greetd', 'python-gobject', 'libnotify',
)
COSMIC_FORBIDDEN = PLASMA_PACKAGES | {
    'kwin', 'kwin-x11', 'plasma-x11-session', 'xfce4-session', 'xfwm4',
    'xfce4-panel', 'sddm', 'sddm-openrc', 'lightdm', 'lightdm-openrc',
}


AUTH_PACKAGES = ('cosmic-greeter', 'cosmic-osd')
COSMIC_SERIES = '1.12'
AUTH_RELEASE = '1:1.12.0-1'


def check_cosmic_closure(resolved, *, live=False):
    """Audit pacman's actual transaction, including transitive dependencies."""
    entries = [line.split() for line in resolved.splitlines() if line.strip()]
    if not entries or any(len(e) != 3 for e in entries):
        raise RuntimeError('Invalid COSMIC dependency-resolution report.')
    check_cosmic_packages({name: version for _, name, version in entries}, live=live)
    for repo, name, version in entries:
        if name in AUTH_PACKAGES and repo != 'extra':
            raise RuntimeError(f'Review Arch COSMIC authentication packaging: {name} {repo}/{version}')


def check_cosmic_packages(versions, *, live=False):
    """Check desktop packages and versions in a resolved or installed manifest."""
    # Calamares keeps Qt Virtual Keyboard and kdialog needs KWallet via KIO.
    forbidden = COSMIC_FORBIDDEN - ({'qt6-virtualkeyboard', 'kwallet'} if live else set())
    unexpected = forbidden & versions.keys()
    if unexpected:
        raise RuntimeError('Incompatible COSMIC dependencies: ' + ', '.join(sorted(unexpected)))
    required = set(COSMIC_PACKAGES)
    missing = required - versions.keys()
    if missing:
        raise RuntimeError('Missing COSMIC packages: ' + ', '.join(sorted(missing)))
    mismatches = []
    for name in ('cosmic-session', 'cosmic-comp', 'cosmic-panel', 'cosmic-applets',
                 'cosmic-bg', 'cosmic-settings', 'cosmic-settings-daemon', 'cosmic-greeter',
                 'cosmic-osk', 'cosmic-randr', 'cosmic-osd',
                 'xdg-desktop-portal-cosmic'):
        version = versions[name]
        if name in AUTH_PACKAGES:
            if version != AUTH_RELEASE:
                mismatches.append(f'{name} {version} (reviewed Arch release {AUTH_RELEASE})')
        else:
            upstream = version.split(':')[-1].rsplit('-', 1)[0]
            if not re.fullmatch(re.escape(COSMIC_SERIES) + r'\.[0-9]+', upstream):
                mismatches.append(f'{name} {version} (expected {COSMIC_SERIES}.x)')
    if mismatches:
        raise RuntimeError('Review COSMIC package changes before installing:\n  ' + '\n  '.join(mismatches))
