"""One optional transaction, invoked only by the installer's final native job."""
import json
import re
import sys
from types import SimpleNamespace

from runtime import chroot, preserve_logs, target


def install(gs, kind, name):
    patterns = {
        'pacman': r'[a-z0-9][a-z0-9@+_.-]*',
        'flathub': r'[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_-]*){2,}',
    }
    if kind not in patterns or not isinstance(name, str) or not re.fullmatch(patterns[kind], name):
        raise ValueError('Invalid package name or Flathub app ID.')
    root = target(gs)
    if not gs.value('starchEssentialComplete'):
        raise RuntimeError('Essential OS installation has not passed validation.')
    try:
        if kind == 'pacman':
            # Reject groups and use only the target's existing repositories/databases.
            chroot(root, 'pacman', '-Si', '--', name)
            chroot(root, 'pacman', '-S', '--needed', '--noconfirm', '--', name)
        else:
            chroot(root, 'flatpak', 'remote-add', '--system', '--if-not-exists',
                   'flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo')
            chroot(root, 'flatpak', 'install', '--system', '--noninteractive',
                   '--assumeyes', '--or-update', 'flathub', 'app/' + name)
    finally:
        preserve_logs(root)


def main():
    try:
        request = json.load(sys.stdin)
        install(SimpleNamespace(value=request['state'].get), request['kind'], request['name'])
    except Exception as error:
        print(f'Warning: {error}', flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
