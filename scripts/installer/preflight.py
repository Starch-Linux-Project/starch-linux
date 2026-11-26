import json
import hashlib
import os
from pathlib import Path
import shutil
import tempfile
from graphics import select_packages
from profiles import PROFILE, validate_selection, check_cosmic_closure
from runtime import DATA, PACKAGE_CACHE, STATE, check_disk_tree, command, deactivate_disk, microcode, output, read_manifest, selected_disk


def retain_packages(args, db, packages, archives):
    """Keep audited Arch databases and signed archives on the live filesystem."""
    # /run is deliberately small on live systems. Use the live /tmp for
    # compressed packages, in a private directory shared only by installer jobs.
    cache = PACKAGE_CACHE
    cache.mkdir(mode=0o700, exist_ok=True)
    info = cache.lstat()
    if not cache.is_dir() or cache.is_symlink() or info.st_uid != os.geteuid() or info.st_mode & 0o077:
        raise RuntimeError('Expected a private root-owned live installer cache in /tmp.')
    # A cancelled run may have left older packages (or partial downloads).
    # Keep only complete, still-requested names. Pacman verifies reused bytes.
    for existing in cache.iterdir():
        if existing.name not in archives or existing.stat().st_size != archives[existing.name][0]:
            existing.unlink()
    missing_bytes = sum(size for name, (size, _) in archives.items() if not (cache / name).exists())
    free = shutil.disk_usage(cache).free
    if output(['findmnt', '-n', '-o', 'FSTYPE', '--target', cache]) == 'tmpfs':
        available = next(line.split()[1] for line in Path('/proc/meminfo').read_text().splitlines()
                         if line.startswith('MemAvailable:'))
        free = min(free, int(available) * 1024)
    if missing_bytes + 256 * 1024**2 > free:
        raise RuntimeError(f'Insufficient live storage to retain the signed installation packages '
                           f'({missing_bytes // 1024**2} MiB to download). The disk has not been erased.')
    for attempt in range(3):
        try:
            command([*args, '--cachedir', cache, '-Sw', '--noconfirm', '--', *packages])
            break
        except RuntimeError:
            if attempt == 2:
                raise
    for name, (_, checksum) in archives.items():
        with (cache / name).open('rb') as package:
            if hashlib.file_digest(package, 'sha256').hexdigest() != checksum:
                (cache / name).unlink()
                raise RuntimeError(f'Downloaded package differs from the resolved Arch database: {name}')
    # Keep the original repo names/order and database signatures. With only
    # file:// servers, pacstrap cannot drift to a newer mirror transaction.
    for metadata in (db / 'sync').iterdir():
        if metadata.name.endswith(('.db', '.db.sig')):
            shutil.copyfile(metadata, cache / metadata.name)
    repositories = output(['pacman-conf', '--config', DATA / 'pacman.conf', '--repo-list']).splitlines()
    config = '[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\n'
    for repo in repositories:
        if not (cache / (repo + '.db')).is_file():
            raise RuntimeError(f'Missing retained repository: {repo}')
        config += f'\n[{repo}]\nServer = {cache.as_uri()}\n'
    (STATE / 'retained-pacman.conf').write_text(config)


def resolve_and_retain(args, db, packages):
    report = output([*args, '-Sp', '--noconfirm', '--print-format', '%r %n %v %f %s %h', '--', *packages])
    resolved = []
    archives = {}
    for line in report.splitlines():
        repo, name, version, filename, size, digest = line.split()
        if Path(filename).name != filename or filename in ('.', '..') or len(digest) != 64:
            raise RuntimeError(f'Invalid Arch package metadata for {name}.')
        resolved.append(f'{repo} {name} {version}')
        archives[filename] = (int(size), digest)
    resolved = '\n'.join(resolved)
    check_cosmic_closure(resolved)
    retain_packages(args, db, packages, archives)
    (STATE / 'cosmic-resolved-packages.txt').write_text(resolved + '\n')


def run(gs):
    validate_selection(gs)
    if gs.value('partitionChoices') != {'install': 'erase', 'swap': 'none'}:
        raise RuntimeError('Only erase-disk installation without disk swap is supported.')
    disk = selected_disk(gs)
    command(['udevadm', 'settle'], timeout=30)
    tree = json.loads(output(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                              'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk]))
    selected_disk(gs)
    deactivate_disk(tree, disk)
    command(['udevadm', 'settle'], timeout=30)
    tree = json.loads(output(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                              'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk]))
    check_disk_tree(tree, disk)
    STATE.mkdir(mode=0o700, exist_ok=True)
    (STATE / 'selection.json').unlink(missing_ok=True)
    packages = read_manifest(DATA / 'minimal-packages.txt') + microcode(Path('/proc/cpuinfo').read_text())
    # BIOS cannot display the EFI stub's embedded splash.
    if gs.value('firmwareType') != 'efi' and 'plymouth' not in packages:
        packages.append('plymouth')
    if not Path('/etc/pacman.d/gnupg/pubring.gpg').is_file():
        raise RuntimeError('The live Arch signing keyring is not ready. Wait for pacman-init and retry.')
    config_path = DATA / 'pacman.conf'
    with tempfile.TemporaryDirectory(prefix='sync-', dir=STATE) as directory:
        db = Path(directory)
        (db / 'local').mkdir()
        args = ['pacman', '--config', config_path, '--dbpath', db,
                '--logfile', STATE / 'pacman-preflight.log']
        command([*args, '-Sy', '--noconfirm'], timeout=300)
        packages = list(dict.fromkeys(packages + select_packages(args, STATE)))
        resolve_and_retain(args, db, packages)
    # Recheck after network operations, immediately before partition jobs run.
    check_disk_tree(json.loads(output(['lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                                     'PATH,TYPE,SIZE,RO,MOUNTPOINTS', '--', disk])), disk)
    selected_disk(gs)
    # Record only the resolved selection; no credentials or full global storage.
    (STATE / 'selection.json').write_text(json.dumps({
        'disk': disk, 'packages': packages, 'profile': PROFILE,
        'repositories_sha256': hashlib.sha256(config_path.read_bytes()).hexdigest(),
    }))
