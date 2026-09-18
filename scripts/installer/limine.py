"""Install Limine as the sole installed-system bootloader."""
import json
import re
import shutil

from runtime import chroot, output, selected_disk, target


def root_uuid(fstab):
    match = re.search(r'^UUID=(\S+)\s+/\s+ext4\s', fstab, re.M)
    if not match:
        raise RuntimeError('Could not find the installed ext4 root UUID.')
    return match.group(1)


def configuration(_uuid):
    return (
        'timeout: 5\n'
        'default_entry: 1\n'
        'interface_branding: Starch Linux\n'
        '\n'
        '/Starch Linux LTS\n'
        '    protocol: efi\n'
        '    path: boot():/EFI/Linux/starch-linux-lts.efi\n'
    )


def run(gs):
    root = target(gs)
    disk = selected_disk(gs)
    uuid = root_uuid((root / 'etc/fstab').read_text())
    if gs.value('firmwareType') == 'efi':
        esp = root / 'boot/efi'
        source = root / 'usr/share/limine/BOOTX64.EFI'
        uki = esp / 'EFI/Linux/starch-linux-lts.efi'
        if not source.is_file() or not uki.is_file():
            raise RuntimeError('The Limine EFI executable or Starch UKI is missing.')
        for relative in ('EFI/Limine', 'EFI/BOOT'):
            loader = esp / relative
            loader.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, loader / 'BOOTX64.EFI')
        config = configuration(uuid)
        (esp / 'EFI/Limine/limine.conf').write_text(config)
        (esp / 'EFI/BOOT/limine.conf').write_text(config)

        updater = root / 'usr/local/lib/starch/update-limine'
        updater.parent.mkdir(parents=True, exist_ok=True)
        updater.write_text(
            '#!/bin/sh\nset -eu\n'
            'install -Dm644 /usr/share/limine/BOOTX64.EFI /boot/efi/EFI/Limine/BOOTX64.EFI\n'
            'install -Dm644 /usr/share/limine/BOOTX64.EFI /boot/efi/EFI/BOOT/BOOTX64.EFI\n')
        updater.chmod(0o755)
        hook = root / 'etc/pacman.d/hooks/99-starch-limine.hook'
        hook.parent.mkdir(parents=True, exist_ok=True)
        hook.write_text(
            '[Trigger]\nOperation = Install\nOperation = Upgrade\nType = Package\nTarget = limine\n\n'
            '[Action]\nDescription = Updating the Starch Limine EFI loader...\nWhen = PostTransaction\n'
            'Exec = /usr/local/lib/starch/update-limine\n')

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

    tree = json.loads(output(['lsblk', '--json', '-o', 'PATH,PARTN,PARTTYPE', '--', disk]))
    bios_guid = '21686148-6449-6e6f-744e-656564454649'
    partitions = (tree.get('blockdevices') or [{}])[0].get('children') or []
    bios = [p for p in partitions if str(p.get('parttype', '')).lower() == bios_guid]
    if len(bios) != 1 or not str(bios[0].get('partn', '')).isdigit():
        raise RuntimeError('Could not identify the BIOS boot partition.')
    loader = root / 'boot/limine'
    loader.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(root / 'usr/share/limine/limine-bios.sys', loader / 'limine-bios.sys')
    (loader / 'limine.conf').write_text(
        'timeout: 5\ndefault_entry: 1\ninterface_branding: Starch Linux\n\n'
        '/Starch Linux LTS\n    protocol: linux\n'
        f'    path: uuid({uuid}):/boot/vmlinuz-linux-lts\n'
        f'    module_path: uuid({uuid}):/boot/initramfs-linux-lts.img\n'
        f'    cmdline: root=UUID={uuid} rw rootfstype=ext4\n')
    chroot(root, 'limine', 'bios-install', disk, str(bios[0]['partn']))
