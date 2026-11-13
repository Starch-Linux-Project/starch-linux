# Starch Lite

Select **Starch Lite — For experienced users** on the Installation Profiles page.
Lite uses Xfce on X11, LightDM, Linux Zen, OpenRC, and elogind.

Packages come from Artix `system`, `world`, and `galaxy`, then Arch `extra`;
Arch `core` is disabled. Update with `sudo pacman -Syu`.

Lite retains Limine, ext4, NetworkManager, PipeWire/WirePlumber, nftables,
and zram. Its integration package supplies OpenRC services, session audio,
and Xfce defaults. Thunar is the file manager; compositing and session
restoration are off by default. Standard user folders are created at login.
A recovery text login is available with **Ctrl+Alt+F2**.

The live ISO remains Plasma with systemd. Starch's Lite configuration package
is bundled with the ISO and has no dedicated binary update repository.
