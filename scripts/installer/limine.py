"""Install Limine as the sole installed-system bootloader."""
from pathlib import Path
import json
import re
import shutil

from runtime import chroot, output, selected_disk, target
from profiles import is_lite, kernel_name


def root_uuid(fstab):
    match = re.search(r'^UUID=(\S+)\s+/\s+ext4\s', fstab, re.M)
    if not match:
        raise RuntimeError('Could not find the installed ext4 root UUID.')
    return match.group(1)


def configuration(_uuid, kernel='linux-lts'):
    label = 'Starch Linux' if kernel == 'linux-zen' else 'Starch Linux LTS'
    return (
        'timeout: 5\n'
        'default_entry: 1\n'
        'interface_branding: Starch Linux\n'
        '\n'
        f'/{label}\n'
        '    protocol: efi\n'
        f'    path: boot():/EFI/Linux/starch-{kernel}.efi\n'
    )


def install_maintenance(root, mode):
    updater = root / 'usr/local/lib/starch/update-limine'
    updater.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(Path(__file__).with_name('limine_update.py'), updater)
    updater.chmod(0o755)
    chroot(root, '/usr/local/lib/starch/update-limine', '--setup', mode)
    hooks = root / 'etc/pacman.d/hooks'
    hooks.mkdir(parents=True, exist_ok=True)
    trigger = '[Trigger]\nOperation = Install\nOperation = Upgrade\nType = Package\nTarget = limine\n\n'
    for name, when, args in (('05-starch-limine-check', 'PreTransaction', ' --check'),
                             ('99-starch-limine', 'PostTransaction', '')):
        (hooks / (name + '.hook')).write_text(
            trigger + '[Action]\nDescription = Checking/deploying the Starch Limine loader...\n'
            + f'When = {when}\nExec = /usr/local/lib/starch/update-limine{args}\n'
            + ('AbortOnFail\n' if when == 'PreTransaction' else ''))


def run(gs):
    root = target(gs)
    kernel = kernel_name(gs)
    disk = selected_disk(gs)
    uuid = root_uuid((root / 'etc/fstab').read_text())
    if gs.value('firmwareType') == 'efi':
        esp = root / 'boot/efi'
        source = root / 'usr/share/limine/BOOTX64.EFI'
        uki = esp / f'EFI/Linux/starch-{kernel}.efi'
        if not source.is_file() or not uki.is_file():
            raise RuntimeError('The Limine EFI executable or Starch UKI is missing.')
        for relative in ('EFI/Limine', 'EFI/BOOT'):
            loader = esp / relative
            loader.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, loader / 'BOOTX64.EFI')
        config = configuration(uuid, kernel)
        (esp / 'EFI/Limine/limine.conf').write_text(config)
        (esp / 'EFI/BOOT/limine.conf').write_text(config)

        install_maintenance(root, 'efi')

        partitions = gs.value('partitions') or []
        esps = [p for p in partitions if p.get('mountPoint') == '/boot/efi']
        if len(esps) != 1:
            raise RuntimeError('Could not identify the EFI system partition.')
        part_number = output(['lsblk', '-d', '-n', '-o', 'PARTN', '--', esps[0]['device']])
        if not part_number.isdigit():
            raise RuntimeError('Could not identify the EFI system partition number.')
        chroot(root, 'efibootmgr', '--create', '--disk', disk, '--part', part_number,
               '--label', 'Starch Linux', '--loader', r'\EFI\Limine\BOOTX64.EFI')
        return

    tree = json.loads(output(['lsblk', '--json', '--tree', '-o', 'PATH,PARTN,PARTTYPE', '--', disk]))
    bios_guid = '21686148-6449-6e6f-744e-656564454649'
    partitions = (tree.get('blockdevices') or [{}])[0].get('children') or []
    bios = [p for p in partitions if str(p.get('parttype', '')).lower() == bios_guid]
    if len(bios) != 1 or not str(bios[0].get('partn', '')).isdigit():
        raise RuntimeError('Could not identify the BIOS boot partition.')
    loader = root / 'boot/limine'
    loader.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / 'usr/share/limine/limine-bios.sys', loader / 'limine-bios.sys')
    label = 'Starch Linux' if is_lite(gs) else 'Starch Linux LTS'
    options = 'init=/usr/bin/openrc-init' if is_lite(gs) else 'quiet splash'
    (loader / 'limine.conf').write_text(
        'timeout: 5\ndefault_entry: 1\ninterface_branding: Starch Linux\n\n'
        f'/{label}\n    protocol: linux\n'
        f'    path: boot():/vmlinuz-{kernel}\n'
        f'    module_path: boot():/initramfs-{kernel}.img\n'
        f'    cmdline: root=UUID={uuid} rw rootfstype=ext4 {options}\n')
    chroot(root, 'limine', 'bios-install', disk, str(bios[0]['partn']))

    install_maintenance(root, 'bios')
