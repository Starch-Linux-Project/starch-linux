# Supported scope and updates

## Installation

Starch supports x86_64 PCs with UEFI or legacy BIOS. The standard desktop is
KDE Plasma on Wayland, with SDDM login and Fish as the user's default shell.
[COSMIC LTS](cosmic.md) uses COSMIC with Linux LTS and systemd.
[Starch Lite](starch-lite.md) uses Xfce, Linux Zen, and OpenRC.

Calamares installs packages online and erases the entire selected disk.
Back up its contents before installing. The root filesystem is ext4; swap is
provided by zram rather than a disk partition.

Unsupported workflows include manual partitioning, dual boot/install-alongside,
offline installation, full-disk encryption, Secure Boot, hibernation, and
snapshot-based rollback. There are no ARM or 32-bit installation images.

## Packages and updates

Standard installations use Arch repositories directly. Flatpak and Flathub are
configured, with no Flatpak applications preinstalled. The application package
list is in [`manifests/minimal-packages.txt`](../manifests/minimal-packages.txt).

Starch does not stage Arch updates or provide automatic rollback. Upstream
updates can break an installed system. Starch-owned utilities and configuration
are bundled with ISO releases and have no dedicated update channel for existing
installations. See also [Linux Update Utility](linux-update-utility.md).

## Hardware

Support is best effort for Intel, AMD, and NVIDIA PCs. The installer selects
appropriate graphics packages; older or unsupported NVIDIA hardware uses
Nouveau where viable. Compatibility with every GPU generation is not guaranteed.
