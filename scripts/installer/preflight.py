import json
from pathlib import Path
import tempfile
from runtime import DATA, STATE, check_disk_tree, command, deactivate_disk, microcode, output, read_manifest, selected_disk


def run(gs):
    if gs.value('partitionChoices') != {'install': 'erase', 'swap': 'none'}:
        raise RuntimeError('Only erase-disk installation without disk swap is supported.')
    disk = selected_disk(gs)
    tree = json.loads(output(['lsblk', '--json', '--bytes', '--paths', '--output',
                              'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk]))
    deactivate_disk(tree, disk)
    tree = json.loads(output(['lsblk', '--json', '--bytes', '--paths', '--output',
                              'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk]))
    check_disk_tree(tree, disk)
    STATE.mkdir(mode=0o700, exist_ok=True)
    (STATE / 'selection.json').unlink(missing_ok=True)
    packages = read_manifest(DATA / 'minimal-packages.txt') + microcode(Path('/proc/cpuinfo').read_text())
    if not Path('/etc/pacman.d/gnupg/pubring.gpg').is_file():
        raise RuntimeError('The live Arch signing keyring is not ready. Wait for pacman-init and retry.')
    db = Path(tempfile.mkdtemp(prefix='sync-', dir=STATE))
    (db / 'local').mkdir()
    args = ['pacman', '--config', DATA / 'pacman.conf', '--dbpath', db,
            '--logfile', STATE / 'pacman-preflight.log']
    command([*args, '-Sy', '--noconfirm'], timeout=300)
    command([*args, '-Sp', '--print-format', '%n %v', '--', *packages], timeout=120)
    # Recheck after network operations, immediately before partition jobs run.
    check_disk_tree(json.loads(output(['lsblk', '--json', '--bytes', '--paths', '--output',
                                     'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk])), disk)
    # Record only the resolved selection; no credentials or full global storage.
    (STATE / 'selection.json').write_text(json.dumps({'disk': disk, 'packages': packages}))
