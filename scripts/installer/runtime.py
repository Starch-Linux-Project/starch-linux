"""Shared boundaries for Starch's small Calamares job modules.

Never import or execute this on behalf of a target inferred from the host.
Every mutating job requires the live marker and Calamares's mounted target.
"""
import html
import json
import os
from pathlib import Path
import re
import shutil
import signal
import stat
import subprocess
import time

DATA = Path('/usr/share/starch-installer')
STATE = Path('/run/starch-installer')
LOG = Path('/var/log/starch-installer.log')


def require_live():
    if os.geteuid() != 0 or not Path('/etc/starch-live').is_file():
        raise RuntimeError('The installer must run as root inside the Starch live ISO.')


def command(argv, timeout=3600):
    """No shell expansion, and no password-bearing commands enter this log."""
    with LOG.open('a') as log:
        LOG.chmod(0o600)
        log.write('\n$ ' + ' '.join(map(str, argv)) + '\n')
        log.flush()
        proc = subprocess.Popen(list(map(str, argv)), stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
        try:
            status = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(proc.pid, signal.SIGKILL)
                proc.wait()
            raise RuntimeError(f'{argv[0]} timed out; its process group was stopped. See {LOG}.') from None
    if status:
        raise RuntimeError(f'{argv[0]} failed (exit {status}). See {LOG}.')


def output(argv):
    return subprocess.check_output(list(map(str, argv)), text=True, timeout=60).strip()


def read_manifest(path):
    packages = []
    for line in path.read_text().splitlines():
        name = line.split('#', 1)[0].strip()
        if not name:
            continue
        if not re.fullmatch(r'[a-z0-9][a-z0-9@+_.-]*', name) or name in packages:
            raise RuntimeError(f'Invalid or duplicate package name: {name!r}')
        packages.append(name)
    if not packages:
        raise RuntimeError('The installation package manifest is empty.')
    return packages


def microcode(cpuinfo):
    vendors = set(re.findall(r'^vendor_id\s*:\s*(\S+)', cpuinfo, re.M))
    if vendors == {'AuthenticAMD'}:
        return ['amd-ucode']
    if vendors == {'GenuineIntel'}:
        return ['intel-ucode']
    return []


def check_disk_tree(tree, selected):
    """Reject mounted/busy targets; never unmount another disk to make room."""
    disks = tree.get('blockdevices', [])
    if len(disks) != 1 or disks[0].get('path') != selected:
        raise RuntimeError('Could not identify the selected disk unambiguously.')
    disk = disks[0]
    if disk.get('type') != 'disk' or disk.get('ro') or int(disk.get('size', 0)) < 21 * 1024**3:
        raise RuntimeError('Select a writable whole disk with at least 21 GiB.')
    def visit(node):
        if any(node.get('mountpoints') or []):
            raise RuntimeError('The selected disk has mounted filesystems or active swap. Unmount it first.')
        if node.get('type') not in ('disk', 'part'):
            raise RuntimeError('The selected disk has active mapped devices. Deactivate them first.')
        for child in node.get('children', []):
            visit(child)
    visit(disk)


def selected_disk(gs):
    disk = gs.value('starchTargetDisk')
    if not isinstance(disk, str) or not disk.startswith('/dev/'):
        raise RuntimeError('The selected erase-disk target is missing. No disks were changed.')
    disk = str(Path(disk).resolve())
    if not stat.S_ISBLK(Path(disk).stat().st_mode):
        raise RuntimeError('The selected target is not a block device.')
    return disk


def target(gs):
    require_live()
    value = gs.value('rootMountPoint')
    if not isinstance(value, str):
        raise RuntimeError('Calamares did not provide a mounted target.')
    root = Path(value)
    if root.parent != Path('/tmp') or not root.name.startswith('calamares-root-') or root.is_symlink():
        raise RuntimeError('Refusing an unexpected installation root.')
    if not root.is_mount() or root.resolve() == Path('/'):
        raise RuntimeError('The installation root is not a separate mounted filesystem.')
    state = json.loads((STATE / 'selection.json').read_text())
    disk = selected_disk(gs)
    if disk != state['disk']:
        raise RuntimeError('The selected disk changed after preflight.')
    partitions = gs.value('partitions') or []
    roots = [p for p in partitions if p.get('mountPoint') == '/']
    if len(roots) != 1 or roots[0].get('fs') != 'ext4':
        raise RuntimeError('Expected exactly one ext4 root partition.')
    root_device = roots[0]['device']
    parents = output(['lsblk', '-s', '-n', '-p', '-o', 'PATH', '--', root_device]).splitlines()
    if disk not in parents:
        raise RuntimeError('The root partition is not on the selected disk.')
    mounted = output(['findmnt', '-n', '-o', 'MAJ:MIN', '--mountpoint', root])
    expected = output(['lsblk', '-d', '-n', '-o', 'MAJ:MIN', '--', root_device])
    if mounted != expected:
        raise RuntimeError('The mounted root does not match the selected partition.')
    if gs.value('firmwareType') == 'efi':
        esps = [p for p in partitions if p.get('mountPoint') == '/boot/efi']
        if len(esps) != 1 or esps[0].get('fs') != 'fat32':
            raise RuntimeError('Expected one FAT32 EFI partition on the selected disk.')
        parents = output(['lsblk', '-s', '-n', '-p', '-o', 'PATH', '--', esps[0]['device']]).splitlines()
        if disk not in parents or not (root / 'boot/efi').is_mount():
            raise RuntimeError('EFI partition is not mounted on the selected disk.')
        if output(['findmnt', '-n', '-o', 'MAJ:MIN', '--mountpoint', root / 'boot/efi']) != output(['lsblk', '-d', '-n', '-o', 'MAJ:MIN', '--', esps[0]['device']]):
            raise RuntimeError('Mounted EFI partition differs from the selected partition.')
    else:
        boot = gs.value('bootLoader') or {}
        if boot.get('installPath') != disk:
            raise RuntimeError('GRUB must install to the selected disk.')
    return root


def put(root, relative, content, mode=0o644):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    # Package-owned symlinks (notably os-release) must not escape the target.
    if path.is_symlink():
        path.unlink()
    path.write_text(content)
    path.chmod(mode)


def chroot(root, *argv):
    command(['arch-chroot', root, *argv])


def preserve_logs(root):
    dest = root / 'var/log/starch-installer'
    dest.mkdir(parents=True, exist_ok=True, mode=0o700)
    for source in (LOG, Path('/root/.cache/calamares/session.log')):
        if source.is_file():
            shutil.copyfile(source, dest / source.name)
            (dest / source.name).chmod(0o600)


def run_stage(name, gs, function):
    try:
        require_live()
        with LOG.open('a') as log:
            LOG.chmod(0o600)
            log.write(f'\n{time.strftime("%Y-%m-%dT%H:%M:%S%z")} {name}\n')
        function(gs)
    except Exception as error:
        with LOG.open('a') as log:
            log.write(f'FAILED: {error}\n')
        return (f'Starch: {name} failed', html.escape(str(error)) + '<br/>Installation did not complete. Log: /var/log/starch-installer.log')
    return None
