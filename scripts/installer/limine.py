"""Install an experimental Limine UEFI loader alongside GRUB."""
import re
import shutil

from runtime import chroot, output, selected_disk, target


def root_uuid(fstab):
    match = re.search(r'^UUID=(\S+)\s+/\s+ext4\s', fstab, re.M)
    if not match:
        raise RuntimeError('Could not find the installed ext4 root UUID.')
    return match.group(1)


def configuration(uuid):
    return (
        'timeout: 5\n'
        'default_entry: 1\n'
        'interface_branding: Starch Linux\n'
        '\n'
        '/Starch Linux LTS\n'
        '    protocol: linux\n'
        f'    path: uuid({uuid}):/boot/vmlinuz-linux-lts\n'
        f'    module_path: uuid({uuid}):/boot/initramfs-linux-lts.img\n'
        f'    cmdline: root=UUID={uuid} rw rootfstype=ext4\n'
    )


def run(gs):
    root = target(gs)
    # The first prototype changes only UEFI installs. GRUB remains both the
    # legacy-BIOS loader and the UEFI recovery loader.
    if gs.value('firmwareType') != 'efi':
        return

    esp = root / 'boot/efi'
    loader = esp / 'EFI/Limine'
    loader.mkdir(parents=True, exist_ok=True)
    source = root / 'usr/share/limine/BOOTX64.EFI'
    if not source.is_file():
        raise RuntimeError('The Limine x86_64 EFI executable is missing.')
    shutil.copyfile(source, loader / 'BOOTX64.EFI')
    (loader / 'limine.conf').write_text(configuration(root_uuid((root / 'etc/fstab').read_text())))

    hook = root / 'etc/pacman.d/hooks/99-starch-limine.hook'
    hook.parent.mkdir(parents=True, exist_ok=True)
    hook.write_text(
        '[Trigger]\n'
        'Operation = Install\n'
        'Operation = Upgrade\n'
        'Type = Package\n'
        'Target = limine\n'
        '\n'
        '[Action]\n'
        'Description = Updating the Starch Limine EFI loader...\n'
        'When = PostTransaction\n'
        'Exec = /usr/bin/cp /usr/share/limine/BOOTX64.EFI /boot/efi/EFI/Limine/BOOTX64.EFI\n'
    )

    partitions = gs.value('partitions') or []
    esps = [p for p in partitions if p.get('mountPoint') == '/boot/efi']
    if len(esps) != 1:
        raise RuntimeError('Could not identify the EFI system partition.')
    part_number = output(['lsblk', '-d', '-n', '-o', 'PARTN', '--', esps[0]['device']])
    if not part_number.isdigit():
        raise RuntimeError('Could not identify the EFI system partition number.')
    disk = selected_disk(gs)
    chroot(root, 'efibootmgr', '--create', '--disk', disk, '--part', part_number,
           '--label', 'Starch Limine', '--loader', r'\EFI\Limine\BOOTX64.EFI')
