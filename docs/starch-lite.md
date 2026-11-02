# Starch Lite

Starch Lite is an optional configuration of Starch Linux 1.2 with the same
identity and branding. It is included in normal builds; fresh boot and desktop
validation remain required.

In the installer's **Advanced** page, acknowledge the warning and select
**Starch Lite**. The option defaults off.

| Component | Lite configuration |
| --- | --- |
| Kernel | Linux Zen |
| Init and sessions | Artix OpenRC and elogind |
| Desktop | KDE Plasma Wayland by default |
| Alternative desktop | Xfce on X11 |
| Boot and storage | Limine, ext4, and compressed zram swap |
| Package sources | Artix system, world, and galaxy; Arch extra |

To install Xfce, also select **Use Xfce instead of KDE Plasma (X11)**.
This replaces Plasma for a fresh installation. Xfce uses Thunar as its file
manager and has desktop animations, compositing, and session restoration off
by default. Lite's Plasma defaults also reduce animations and decorative effects.
Users can customize desktop settings after installation.

Lite provides a recovery text login on **Ctrl+Alt+F2**. Networking, audio,
Bluetooth, and the firewall are configured through OpenRC and session services.
No fixed memory saving or performance improvement is promised.

Runtime packages update from Artix and Arch extra through `pacman -Syu`.
Starch's Lite configuration package has no dedicated binary update repository.
The standard installation and live desktop use Arch packages and systemd.
