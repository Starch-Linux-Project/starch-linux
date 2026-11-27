import json
from pathlib import Path
import re

from runtime import chroot, put, target
from profiles import KERNEL
import cosmic


def seed_greeter_wallpaper(root, username, drm=Path('/sys/class/drm')):
    """Seed the per-output state cosmic-bg normally publishes after first login."""
    skel = root / 'etc/skel/.config/cosmic'
    selection = skel / 'com.system76.CosmicBackground/v1/all'
    if not selection.is_file():
        return
    match = re.search(r'source:\s*Path\("(/usr/share/backgrounds/starch/[\w.-]+)"\)', selection.read_text())
    if not match or not (root / match[1].lstrip('/')).is_file():
        return
    outputs = sorted({status.parent.name.split('-', 1)[1]
                      for status in drm.glob('card[0-9]*-*/status')})
    if not outputs:
        return
    entries = [f'({json.dumps(output)}, Path({json.dumps(match[1])}))' for output in outputs]
    state = '[' + ', '.join(entries) + ']'
    # Run as the installed user so the first session can update the file normally.
    chroot(root, 'runuser', '-u', username, '--', 'sh', '-c',
           'cd "$HOME" && dir=.local/state/cosmic/com.system76.CosmicBackground/v1 && '
           'mkdir -p "$dir" && if [ ! -e "$dir/wallpapers" ]; then '
           'printf "%s\n" "$1" > "$dir/wallpapers"; fi', 'seed-wallpaper', state)


def run(gs):
    root = target(gs)
    kernel = KERNEL
    put(root, 'etc/os-release', 'NAME="Starch Linux"\nPRETTY_NAME="Starch Linux 1.4"\nID=starch\nID_LIKE=arch\nVERSION="1.4"\nVERSION_ID="1.4"\nVERSION_CODENAME=evergreen\nBUILD_ID=rolling\nANSI_COLOR="38;2;23;147;209"\n')
    put(root, 'etc/issue', 'Starch Linux \\r (\\l)\n\n')
    put(root, 'etc/issue.net', 'Starch Linux\n')
    put(root, 'etc/systemd/zram-generator.conf', '[zram0]\nzram-size = min(ram / 2, 4096)\ncompression-algorithm = zstd\n')
    splash_hook = '' if gs.value('firmwareType') == 'efi' else ' plymouth'
    put(root, 'etc/mkinitcpio.conf.d/10-starch.conf', f'HOOKS=(base systemd autodetect microcode modconf kms{splash_hook} keyboard sd-vconsole block filesystems fsck)\n')
    if gs.value('firmwareType') == 'efi':
        fstab = (root / 'etc/fstab').read_text()
        match = re.search(r'^UUID=(\S+)\s+/\s+ext4\s', fstab, re.M)
        if not match:
            raise RuntimeError('Could not find the installed ext4 root UUID.')
        put(root, 'etc/kernel/cmdline', f'root=UUID={match.group(1)} rw rootfstype=ext4\n')
        (root / 'boot/efi/EFI/Linux').mkdir(parents=True, exist_ok=True)
        put(root, f'etc/mkinitcpio.d/{kernel}.preset',
            f'ALL_kver="/boot/vmlinuz-{kernel}"\n'
            'PRESETS=(\'default\')\n'
            f'default_uki="/boot/efi/EFI/Linux/starch-{kernel}.efi"\n'
            'default_options="--splash /usr/share/starch/splash-starch.bmp"\n')
    else:
        # Select the theme before mkinitcpio embeds it in the BIOS initramfs.
        chroot(root, 'plymouth-set-default-theme', 'starch')
    chroot(root, 'usermod', '--shell', '/usr/bin/bash', 'root')
    chroot(root, 'passwd', '--lock', 'root')
    chroot(root, 'nft', '--check', '--file', '/etc/nftables.conf')
    chroot(root, 'systemctl', 'enable', 'NetworkManager.service', 'nftables.service',
           'power-profiles-daemon.service', 'bluetooth.service')
    chroot(root, 'systemctl', 'set-default', 'graphical.target')
    cosmic.configure(root)
    seed_greeter_wallpaper(root, gs.value('username'))
    chroot(root, 'mkinitcpio', '-P')
