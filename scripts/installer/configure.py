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
    put(root, 'etc/mkinitcpio.conf.d/10-starch.conf', 'HOOKS=(base systemd autodetect microcode modconf kms keyboard sd-vconsole block filesystems fsck)\n')
    # No resume, live media, os-prober or distribution-specific kernel arguments.
    put(root, 'etc/default/grub', 'GRUB_DEFAULT=0\nGRUB_TIMEOUT=5\nGRUB_DISTRIBUTOR="Starch"\nGRUB_CMDLINE_LINUX_DEFAULT=""\nGRUB_CMDLINE_LINUX=""\nGRUB_PRELOAD_MODULES="part_gpt part_msdos"\nGRUB_DISABLE_OS_PROBER=true\n')
    chroot(root, 'usermod', '--shell', '/usr/bin/bash', 'root')
    chroot(root, 'passwd', '--lock', 'root')
    chroot(root, 'systemctl', 'enable', 'NetworkManager.service', 'sddm.service')
    chroot(root, 'systemctl', 'set-default', 'graphical.target')
    chroot(root, 'mkinitcpio', '-P')
