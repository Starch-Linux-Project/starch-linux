"""Separate signing trust for Lite; never change the live system's repositories."""
from runtime import command


def prepare_lite_keyring(archives, state):
    # Bundle identity and checksums must already have been verified. The Artix
    # bootstrap keyring is pinned in the source tree when building the bundle.
    archive = next(p for p in archives if p.name.startswith('artix-keyring-'))
    extracted = state / 'lite-keyring-source'
    extracted.mkdir(parents=True, exist_ok=True)
    names = [f'usr/share/pacman/keyrings/artix{suffix}'
             for suffix in ('.gpg', '-trusted', '-revoked')]
    command(['bsdtar', '-xf', archive, '-C', extracted, '--', *names])
    keyring = state / 'lite-gnupg'
    keyring.mkdir(mode=0o700, exist_ok=True)
    command(['pacman-key', '--gpgdir', keyring, '--init'])
    command(['pacman-key', '--gpgdir', keyring, '--populate', 'archlinux'])
    command(['pacman-key', '--gpgdir', keyring, '--populate-from',
             extracted / 'usr/share/pacman/keyrings', '--populate', 'artix'])
    return keyring
