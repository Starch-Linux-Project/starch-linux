import json
import shutil
from runtime import DATA, STATE, command, target


def run(gs):
    root = target(gs)
    packages = json.loads((STATE / 'selection.json').read_text())['packages']
    # Fresh root and keyring; never copy the live filesystem or its users.
    command(['pacstrap', '-K', '-M', '-C', DATA / 'pacman.conf', root, *packages])
    shutil.copyfile(DATA / 'pacman.conf', root / 'etc/pacman.conf')
    # Seed /etc/skel before Calamares creates the account and home directory.
    shutil.copytree(DATA / 'target-overlay', root, dirs_exist_ok=True)
    manifests = root / 'var/log/starch-installer'
    manifests.mkdir(parents=True, exist_ok=True, mode=0o700)
    (manifests / 'requested-packages.txt').write_text('\n'.join(packages) + '\n')
