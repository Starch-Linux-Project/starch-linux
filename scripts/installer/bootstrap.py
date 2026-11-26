import json
import hashlib
import shutil
from runtime import DATA, LOG, PACKAGE_CACHE, STATE, command, target
from profiles import PROFILE
from media_defaults import write_defaults


def pacstrap(root, config_path, packages, attempts=3):
    """Retry the retained local package transaction."""
    argv = ['pacstrap', '-K', '-M', '-C', config_path, root, *packages]
    for attempt in range(1, attempts + 1):
        try:
            command(argv)
            return
        except RuntimeError:
            if attempt == attempts:
                raise
            with LOG.open('a') as log:
                log.write(f'pacstrap attempt {attempt} failed; retrying with retained packages.\n')


def apply_defaults(root):
    # Seed /etc/skel before Calamares creates the account and home directory.
    shutil.copytree(DATA / 'target-overlay', root, dirs_exist_ok=True)
    shutil.copytree(DATA / 'rotation-overlay', root, dirs_exist_ok=True)
    shutil.copytree(DATA / 'desktop-overlays/cosmic', root, dirs_exist_ok=True)
    write_defaults(root)
    # Archiso defaults nested overlay files to 0644 unless profiledef preserves
    # their mode. Enforce executability here as well before target validation.
    (root / 'usr/local/bin/linux-update-utility.AppImage').chmod(0o755)


def run(gs):
    root = target(gs)
    selection = json.loads((STATE / 'selection.json').read_text())
    packages = selection['packages']
    config_path = DATA / 'pacman.conf'
    if hashlib.sha256(config_path.read_bytes()).hexdigest() != selection['repositories_sha256']:
        raise RuntimeError('The repository configuration changed after preflight.')
    # Fresh root and keyring; never copy the live filesystem or its users.
    pacstrap(root, STATE / 'retained-pacman.conf', packages)
    shutil.copyfile(config_path, root / 'etc/pacman.conf')
    apply_defaults(root)
    manifests = root / 'var/log/starch-installer'
    manifests.mkdir(parents=True, exist_ok=True, mode=0o700)
    (manifests / 'requested-packages.txt').write_text('\n'.join(packages) + '\n')
    shutil.copyfile(STATE / 'cosmic-resolved-packages.txt', manifests / 'resolved-packages.txt')
    (manifests / 'profile.txt').write_text(PROFILE + '\n')
    shutil.rmtree(PACKAGE_CACHE)
