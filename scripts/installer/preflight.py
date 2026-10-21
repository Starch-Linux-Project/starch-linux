import json
import hashlib
from pathlib import Path
import tempfile
from graphics import select_packages
from profiles import is_lite, has_xfce, lite_packages, pacman_config, profile_name, verified_bundle
from repositories import prepare_lite_keyring
from runtime import DATA, STATE, check_disk_tree, command, deactivate_disk, microcode, output, read_manifest, selected_disk


def run(gs):
    lite_archives = []
    if is_lite(gs):
        if gs.value('starchAdvancedAcknowledged') is not True:
            raise RuntimeError('Acknowledge the Advanced warning before selecting Starch Lite.')
        lite_archives = verified_bundle(DATA / 'lite')
    if gs.value('partitionChoices') != {'install': 'erase', 'swap': 'none'}:
        raise RuntimeError('Only erase-disk installation without disk swap is supported.')
    disk = selected_disk(gs)
    command(['udevadm', 'settle'], timeout=30)
    tree = json.loads(output(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                              'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk]))
    deactivate_disk(tree, disk)
    command(['udevadm', 'settle'], timeout=30)
    tree = json.loads(output(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                              'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk]))
    check_disk_tree(tree, disk)
    STATE.mkdir(mode=0o700, exist_ok=True)
    (STATE / 'selection.json').unlink(missing_ok=True)
    packages = read_manifest(DATA / 'minimal-packages.txt') + microcode(Path('/proc/cpuinfo').read_text())
    if is_lite(gs):
        packages = lite_packages(packages, xfce=has_xfce(gs))
    # BIOS cannot display the EFI stub's embedded splash.
    if not is_lite(gs) and gs.value('firmwareType') != 'efi' and 'plymouth' not in packages:
        packages.append('plymouth')
    # Lite initializes its own Arch/Artix trust below and supplies --gpgdir to
    # every package operation. Only standard installs use the live keyring.
    if not lite_archives and not Path('/etc/pacman.d/gnupg/pubring.gpg').is_file():
        raise RuntimeError('The live Arch signing keyring is not ready. Wait for pacman-init and retry.')
    db = Path(tempfile.mkdtemp(prefix='sync-', dir=STATE))
    (db / 'local').mkdir()
    config_path = pacman_config(DATA, gs)
    keyring_args = []
    if lite_archives:
        keyring_args = ['--gpgdir', prepare_lite_keyring(lite_archives, STATE)]
    args = ['pacman', '--config', config_path, *keyring_args, '--dbpath', db,
            '--logfile', STATE / 'pacman-preflight.log']
    command([*args, '-Sy', '--noconfirm'], timeout=300)
    gpu_packages = (select_packages(args, STATE, kernel='linux-zen') if is_lite(gs)
                    else select_packages(args, STATE))
    packages = list(dict.fromkeys(packages + gpu_packages))
    command([*args, '-Sp', '--print-format', '%n %v', '--', *packages], timeout=120)
    if lite_archives:
        # Resolve the local integration package against Artix and Arch extra.
        # The bundle has already been authenticated against its ISO manifest.
        config = STATE / 'lite-preflight.conf'
        config.write_text(config_path.read_text().replace(
            'LocalFileSigLevel = Required', 'LocalFileSigLevel = Optional'))
        command(['pacman', '--config', config, *keyring_args, '--dbpath', db, '-Up',
                 '--print-format', '%n %v', '--', *lite_archives], timeout=120)
    # Recheck after network operations, immediately before partition jobs run.
    check_disk_tree(json.loads(output(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                                     'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk])), disk)
    # Record only the resolved selection; no credentials or full global storage.
    (STATE / 'selection.json').write_text(json.dumps({
        'disk': disk, 'packages': packages, 'profile': profile_name(gs),
        'repositories_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest()
        if lite_archives else None,
        'lite_bundle_sha256': hashlib.sha256((DATA / 'lite/bundle.json').read_bytes()).hexdigest()
        if lite_archives else None}))
