# Starch Linux

Starch Linux is an x86_64 Linux distribution with a graphical online installer.
One ISO offers three installation profiles:

| Profile | Desktop / login | Kernel / init | Repositories |
| --- | --- | --- | --- |
| KDE Plasma LTS (default) | Plasma Wayland / SDDM | Linux LTS / systemd | Arch |
| COSMIC LTS | COSMIC Wayland / COSMIC Greeter | Linux LTS / systemd | Arch |
| Starch Lite | Xfce X11 / LightDM | Linux Zen / OpenRC | Artix + Arch extra |

Calamares installs fresh packages with pacstrap and erases the selected disk.
All profiles use ext4, Limine (UEFI or BIOS), zram, NetworkManager, PipeWire,
Flatpak, and Linux Update Utility. The Archiso live desktop uses Plasma,
systemd, and the regular Arch kernel.

See [installation profiles](docs/installation-profiles.md),
[supported scope](docs/decisions.md), and [licensing](docs/licensing.md).

Source: `archiso/profile/` holds the live image; `calamares/` the installer;
`manifests/` the base package list; `scripts/installer/` profile configuration;
`packages/` integrations; and `tests/` automated checks.
