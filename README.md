# Starch Linux

Starch Linux is an Arch-based Linux distribution made by SethDoesTech and built
around KDE Plasma and Wayland. This repository contains the Archiso profile,
Calamares installer integration, package manifests, build tooling, and
validation tests used to produce the Starch Linux live ISO
and installed system.

> [!WARNING]
> Installation erases the selected disk. Back up your data and test in a
> virtual machine before installing on physical hardware.

## Features

- KDE Plasma desktop running on Wayland
- Calamares online installer backed by official Arch Linux repositories
- Optional Starch Lite configuration in the installer's Advanced page
- BIOS and UEFI boot support
- Limine as the installed system's sole bootloader
- NetworkManager and desktop network controls
- PipeWire and WirePlumber audio
- Fish, Konsole, Firefox, Nautilus, Fastfetch, and zram
- Linux Update Utility in the live environment and installed system
- KDE Plasma Keyboard for touch and keyboard-less use
- Reproducible build inputs, checksums, and validation reports

The standard configuration uses the Linux LTS kernel, systemd, KDE Plasma
Wayland, and the official Arch repositories. Starch Lite is an optional
configuration of the same Starch Linux installation. It uses Linux Zen,
OpenRC, elogind, and Artix `system`, `world`, and `galaxy` followed by Arch
`extra`. Lite can use KDE Plasma Wayland or install Xfce X11 as the only
desktop. Selecting Lite does not create a separate distribution or change the
installed Starch Linux name.

The installer supports whole-disk erase only. It does not offer manual
partitioning, install-alongside, disk encryption, disk swap, or an X11 Plasma
session.

## Boot design

On UEFI systems, mkinitcpio builds the selected kernel, initramfs, microcode,
and kernel command line into a unified kernel image beneath
`/boot/efi/EFI/Linux/`. Limine chainloads that image and is installed at both
its named EFI path and the standard fallback path. Legacy BIOS installations
use Limine's native Linux boot protocol, with the kernel, initramfs, and Limine
files on a separate FAT32 `/boot` partition. GRUB is not installed on the
target system.

The standard installation uses `linux-lts`. Starch Lite substitutes
`linux-zen` and starts OpenRC as PID 1. Both configurations retain the Starch
Linux boot name and Limine layout.

The live ISO continues to use Archiso's native live-media boot layout. Those
boot files and packages are build-time and live-environment details; they do
not define the bootloader installed by Starch.

The live desktop remains a Plasma Wayland session. Because Calamares runs with
root privileges, its launcher uses the session's XWayland display and preserves
`DISPLAY` and `XAUTHORITY` across `sudo`; passing the live user's Wayland
runtime directory to a root Qt process is rejected by Qt. For that reason,
`xorg-xwayland` is an explicit live-image dependency even though an X11 Plasma
session is not provided.

## Starch Lite

Starch Lite is built with the rest of the ISO and remains disabled by default.
To select it, open the installer's Advanced page, acknowledge the warning, and
enable Starch Lite. Its repository and init-system changes apply only to the
installed Lite target; the live ISO and standard installation remain on the
normal Arch and systemd configuration.

Lite includes lower-memory defaults, an OpenRC zram service, PipeWire session
startup without a systemd user manager, and a reduced number of text consoles.
The optional Xfce selection removes Plasma and KWin before package resolution
and exposes only the working Xfce X11 session in SDDM.

See [docs/starch-lite.md](docs/starch-lite.md) for the repository order,
service configuration, profile behavior, build inputs, and release test list.

## Project status

The standard live environment, Calamares installation, Limine/UKI boot, and
Plasma desktop have completed an end-to-end UEFI virtual-machine test. Legacy
BIOS installation remains supported and should continue to be covered by
release testing.

Starch Lite is integrated into normal builds. Its package resolution,
installer validation, OpenRC startup, Plasma audio, and Xfce X11 login have
been exercised during development. Fresh UEFI and BIOS installations still
need the complete release test matrix before Starch Linux 1.2 is published.

See [docs/decisions.md](docs/decisions.md) for the supported scope and
non-goals. See [docs/virtual-keyboard.md](docs/virtual-keyboard.md) for the
KWin/SDDM integration and hardware test matrix.

## Requirements

Build on an up-to-date Arch Linux system with at least 20 GiB of free space.
The build and online installer require an internet connection.

```bash
sudo pacman -Syu --needed base-devel archiso arch-install-scripts limine \
  qemu-desktop edk2-ovmf shellcheck python python-yaml
```

Rootless Archiso builds require working subordinate UID/GID mappings. Check the
host before building:

```bash
unshare --map-auto --map-root-user -- id
./build.sh --check
```

## Build

Before building, add the Linux Update Utility AppImage and icon as described in
[docs/linux-update-utility.md](docs/linux-update-utility.md). Both inputs are
required and remain outside version control.

Use the repository build wrapper so Calamares, Starch Lite, and the local
packages are staged into a fresh Archiso profile:

```bash
./build.sh --build
```

Do not invoke `mkarchiso` directly on `archiso/profile`; doing so bypasses
installer staging and can leave the shared work directory owned by root or a
subordinate namespace user. If a previous build reports that a generated
directory is not writable, remove that generated state and retry:

```bash
sudo ./clean.sh work
./build.sh --build
```

Builds create a unique run directory and preserve existing outputs. ISO images
and checksums are written beneath `starch-out/`; logs and intermediate files are
written beneath `build/`.

## Test

Run the automated checks with:

```bash
python3 -m unittest discover -s tests/unit -v
shellcheck build.sh clean.sh scripts/build/*.sh \
  scripts/validate/calamares-smoke.sh \
  archiso/profile/airootfs/usr/local/bin/starch-install \
  archiso/profile/airootfs/usr/local/lib/starch/setup-live-user
```

Test generated images in a virtual machine before using physical hardware.
GNOME Boxes is the project's current interactive test environment; begin with
4 GiB RAM and 2 virtual CPUs. Verify the image against its `SHA256SUMS` file
before booting it. Test standard Starch separately from both Lite desktop
choices so changes to Lite cannot hide a standard-install regression.

## Repository layout

| Path | Purpose |
| --- | --- |
| `archiso/profile/` | Live ISO profile and filesystem overlay |
| `calamares/` | Installer sequence, configuration, and branding |
| `manifests/` | Requested packages for the installed system |
| `packages/calamares/` | Pinned Calamares package sources and patches |
| `packages/starch-lite/` | Optional Lite configuration package and pinned trust input |
| `packages/linux-update-utility/` | Tracked desktop integration for Linux Update Utility |
| `luu-input/` | Git-ignored AppImage and SVG inputs supplied by the builder |
| `wallpapers/` | Source images packaged into the desktop wallpaper library |
| `scripts/build/` | Build and staging helpers |
| `scripts/installer/` | Installation, target configuration, and validation jobs |
| `scripts/validate/` | Generated-system validation tools |
| `tests/` | Automated tests |
| `docs/` | Supported scope, build integration, licensing, and provenance |
| `build/` | Generated work trees, caches, and logs |
| `starch-out/` | Generated ISO artifacts |

## Cleaning generated files

Preview a cleanup operation before running it:

```bash
./clean.sh --dry-run work
sudo ./clean.sh work
```

The accepted categories are `work`, `cache`, `logs`, and `inventory`. Each
category removes every generated run in that category. ISO files in
`starch-out/` are managed separately.

## Contributing

Keep source changes outside generated `build/` trees and run the checks above.
Installer safety changes should include regression coverage, especially for
disk selection, partitioning, bootloader installation, profile isolation, and
target validation.

## Licensing

Original Starch Linux software is licensed under the GNU General Public License
version 3 or later. The Fastfetch artwork is dedicated under CC0 1.0 Universal.
Third-party work remains under its respective licenses; provenance and notices
are recorded in [docs/third-party/](docs/third-party/) and
[docs/third-party-provenance.tsv](docs/third-party-provenance.tsv). Modified
distributions must use a different name and branding; see [NOTICE.md](NOTICE.md)
and [docs/licensing.md](docs/licensing.md).
