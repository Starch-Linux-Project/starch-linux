#!/usr/bin/python3
"""Fail-closed maintenance for Starch's plain GPT boot layout."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

CONFIG = Path('/etc/starch/limine.json')
BIOS_GUID = '21686148-6449-6e6f-744e-656564454649'


def query(*args):
    return subprocess.check_output(args, text=True).strip()


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def flatten(nodes):
    for node in nodes:
        yield node
        yield from flatten(node.get('children', []))


def validate(mode, expected=None):
    require(mode in ('efi', 'bios'), 'Unknown firmware mode')
    mount = Path('/boot/efi' if mode == 'efi' else '/boot')
    entries = [line.split() for line in Path('/etc/fstab').read_text().splitlines()
               if line.strip() and not line.lstrip().startswith('#')]
    entries = [e for e in entries if len(e) >= 4 and e[1] == str(mount)]
    require(len(entries) == 1 and entries[0][0].startswith('UUID=') and entries[0][2] == 'vfat',
            f'{mount} needs one UUID-based vfat fstab entry')
    uuid = entries[0][0][5:]
    mounted = json.loads(query('findmnt', '--json', '--mountpoint', str(mount), '--output',
                              'TARGET,FSTYPE,UUID,MAJ:MIN,OPTIONS'))['filesystems']
    require(len(mounted) == 1, 'Boot filesystem is not a unique mount')
    fs = mounted[0]
    require(fs['target'] == str(mount) and fs['fstype'] == 'vfat' and fs['uuid'] == uuid,
            'Boot mount does not match fstab')
    require('rw' in fs['options'].split(',') and os.access(mount, os.W_OK), 'Boot mount is not writable')
    disks = json.loads(query('lsblk', '--json', '--tree', '--bytes', '--paths', '--output',
                            'PATH,TYPE,PTTYPE,PTUUID,PARTUUID,PARTTYPE,PARTN,UUID,MAJ:MIN,RO,SIZE,MOUNTPOINTS'))['blockdevices']
    matches = [n for n in flatten(disks) if n.get('uuid') == uuid]
    require(len(matches) == 1 and matches[0]['maj:min'] == fs['maj:min'], 'Ambiguous or wrong boot device')
    parents = [d for d in disks if d.get('type') == 'disk' and matches[0] in d.get('children', [])]
    require(len(parents) == 1 and matches[0]['type'] == 'part' and not matches[0].get('children'), 'Boot filesystem needs a plain disk partition')
    disk = parents[0]
    require(not disk['ro'] and not matches[0]['ro'], 'Boot storage is read-only')
    identity = {'mode': mode, 'uuid': uuid}
    bios = None
    if mode == 'bios':
        candidates = [p for p in disk.get('children', []) if (p.get('parttype') or '').lower() == BIOS_GUID]
        require(disk.get('pttype') == 'gpt' and len(candidates) == 1, 'Ambiguous GPT BIOS boot partition')
        bios = candidates[0]
        require(bios.get('partuuid') and disk.get('ptuuid') and str(bios.get('partn', '')).isdigit()
                and int(bios['partn']) > 0 and int(bios['size']) >= 32768 and not bios['ro']
                and not any(bios.get('mountpoints') or []) and not bios.get('children'), 'Invalid BIOS boot partition')
        require(sum(n.get('partuuid') == bios['partuuid'] for n in flatten(disks)) == 1
                and sum(d.get('ptuuid') == disk['ptuuid'] for d in disks) == 1, 'Duplicate BIOS storage identity')
        identity.update(partuuid=bios['partuuid'], ptuuid=disk['ptuuid'])
    require(expected is None or expected == identity, 'Installed boot storage identity changed')
    source = Path('/usr/share/limine') / ('BOOTX64.EFI' if mode == 'efi' else 'limine-bios.sys')
    require(source.is_file() and os.access(source, os.R_OK), f'Missing or unreadable loader: {source}')
    if bios:
        require(shutil.which('limine'), 'Missing limine bios-install utility')
    destinations = ([mount / 'EFI/Limine/BOOTX64.EFI', mount / 'EFI/BOOT/BOOTX64.EFI']
                    if mode == 'efi' else [mount / 'limine/limine-bios.sys'])
    for dest in destinations:
        require(dest.parent.is_dir() and dest.parent.resolve().is_relative_to(mount.resolve())
                and not dest.is_symlink() and os.access(dest.parent, os.W_OK), 'Unsafe loader directory')
        require(os.stat(dest.parent).st_dev == os.stat(mount).st_dev, 'Nested loader filesystem')
    return identity, disk, bios, source, destinations


def deploy(expected, check=False):
    _, disk, bios, source, destinations = validate(expected['mode'], expected)
    if check:
        return
    staged = []
    try:
        for dest in destinations:
            fd, name = tempfile.mkstemp(prefix='.starch-limine-', dir=dest.parent)
            staged.append((Path(name), dest))
            with os.fdopen(fd, 'wb') as stream, source.open('rb') as loader:
                shutil.copyfileobj(loader, stream)
                stream.flush()
                os.fchmod(stream.fileno(), 0o644)
                os.fsync(stream.fileno())
        _, disk, bios, _, _ = validate(expected['mode'], expected)
        if bios:
            subprocess.run(['limine', 'bios-install', disk['path'], str(bios['partn'])], check=True)
        for name, dest in staged:
            os.replace(name, dest)
        os.sync()
    finally:
        for name, _ in staged:
            name.unlink(missing_ok=True)


def main():
    try:
        if len(sys.argv) == 3 and sys.argv[1] == '--setup' and sys.argv[2] in ('efi', 'bios'):
            identity, *_ = validate(sys.argv[2])
            require(not CONFIG.exists(), 'Boot identity already enrolled; review it manually')
            CONFIG.parent.mkdir(parents=True, exist_ok=True)
            CONFIG.write_text(json.dumps(identity) + '\n')
        else:
            require(sys.argv[1:] in ([], ['--check']), 'Usage: update-limine [--check | --setup efi|bios]')
            deploy(json.loads(CONFIG.read_text()), check=bool(sys.argv[1:]))
    except (RuntimeError, OSError, ValueError, KeyError, subprocess.SubprocessError) as error:
        sys.exit(f'Starch Limine update failed: {error}. Mount the configured boot filesystem, verify fstab and /etc/starch/limine.json, then rerun /usr/local/lib/starch/update-limine. If the package was upgraded, deployment is still required before reboot.')


if __name__ == '__main__':
    main()
