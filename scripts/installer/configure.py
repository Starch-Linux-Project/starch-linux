import re

from runtime import chroot, put, target


def run(gs):
    root = target(gs)
    # This file has higher precedence than sddm.conf.d and Calamares writes it.
    # Autologin is reserved for the disposable live environment.
    put(root, 'etc/sddm.conf', '[Autologin]\nUser=\nSession=\nRelogin=false\n')
    put(root, 'etc/os-release', 'NAME="Starch Linux"\nPRETTY_NAME="Starch Linux"\nID=starch\nID_LIKE=arch\nBUILD_ID=rolling\nANSI_COLOR="38;2;23;147;209"\n')
    put(root, 'etc/issue', 'Starch Linux \\r (\\l)\n\n')
    put(root, 'etc/issue.net', 'Starch Linux\n')
    put(root, 'etc/sddm.conf.d/10-starch.conf', '[General]\nDisplayServer=wayland\n\n[Wayland]\nCompositorCommand=kwin_wayland --drm --no-lockscreen --no-global-shortcuts --locale1\n\n[X11]\nSessionDir=/usr/share/starch/no-x11-sessions\n\n[Theme]\nCurrent=breeze\n')
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
        put(root, 'etc/mkinitcpio.d/linux-lts.preset',
            'ALL_kver="/boot/vmlinuz-linux-lts"\n'
            'PRESETS=(\'default\')\n'
            'default_uki="/boot/efi/EFI/Linux/starch-linux-lts.efi"\n'
            'default_options="--splash /usr/share/starch/splash-starch.bmp"\n')
    else:
        # Select the theme before mkinitcpio embeds it in the BIOS initramfs.
        chroot(root, 'plymouth-set-default-theme', 'starch')
    chroot(root, 'usermod', '--shell', '/usr/bin/bash', 'root')
    chroot(root, 'passwd', '--lock', 'root')
    chroot(root, 'nft', '--check', '--file', '/etc/nftables.conf')
    chroot(root, 'systemctl', 'enable', 'NetworkManager.service', 'nftables.service', 'sddm.service')
    chroot(root, 'systemctl', 'set-default', 'graphical.target')
    chroot(root, 'mkinitcpio', '-P')
