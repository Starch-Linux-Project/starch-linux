"""One optional transaction, invoked only by the installer's final native job."""
import json
import re
import sys
from types import SimpleNamespace

from runtime import LOG, chroot, preserve_logs, require_live, target


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
            chroot(root, 'pacman', '-Q', '--', name)
        else:
            chroot(root, 'flatpak', 'remote-add', '--system', '--if-not-exists',
                   'flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo')
            chroot(root, 'flatpak', 'install', '--system', '--noninteractive',
                   '--assumeyes', '--or-update', 'flathub', 'app/' + name)
            chroot(root, 'flatpak', 'info', '--system', 'app/' + name)
    finally:
        preserve_logs(root)


def record_result(request, status, detail):
    """Keep optional outcomes even when the UI is closed or the target check fails."""
    require_live()
    result = {'optionalSoftware': status, 'kind': request.get('kind'),
              'name': request.get('name'), 'detail': detail}
    with LOG.open('a') as log:
        LOG.chmod(0o600)
        log.write(json.dumps(result) + '\n')
    # Never copy diagnostics into a target whose identity cannot be established.
    root = target(SimpleNamespace(value=request.get('state', {}).get))
    preserve_logs(root)


def main():
    request = {}
    status, detail = 'installed', ''
    try:
        request = json.load(sys.stdin)
        install(SimpleNamespace(value=request['state'].get), request['kind'], request['name'])
    except Exception as error:
        status, detail = 'warning', str(error)
        print(f'Warning: {detail}', flush=True)
    try:
        record_result(request, status, detail)
    except Exception as error:
        print(f'Warning: could not preserve optional software result: {error}', flush=True)
        status = 'warning'
    return 0 if status == 'installed' else 1


if __name__ == '__main__':
    sys.exit(main())
