# Starch Linux

Starch Linux is an Arch-based Linux distribution built around KDE
Plasma and Wayland. This repository contains the Archiso profile, Calamares
installer integration, package manifests, build tooling, and validation tests
used to produce a bootable live ISO and install a minimal desktop system.

> [!WARNING]
> Starch is under active development. Images produced from this repository are
> development builds, not audited releases. Back up your data and test in a
> virtual machine before considering installation on physical hardware.

## Features

- KDE Plasma desktop running on Wayland
- Calamares online installer backed by official Arch Linux repositories
- BIOS and UEFI boot support
- Limine as the installed system's sole bootloader
- NetworkManager and Plasma network controls
- PipeWire and WirePlumber audio
- Fish, Konsole, Firefox, Nautilus, Fastfetch, and zram
- Linux Update Utility in the live environment and installed system
- A reproducible build layout with source snapshots, checksums, and validation
  reports

The installer currently supports whole-disk erase only. It does not offer
manual partitioning, install-alongside, disk encryption, disk swap, or an X11
Plasma session.

On UEFI systems, mkinitcpio builds the LTS kernel, initramfs, microcode, and
kernel command line into `/boot/efi/EFI/Linux/starch-linux-lts.efi`. Limine
chainloads that UKI and is installed at both its named EFI path and the standard
fallback path. Legacy BIOS installations use Limine's native Linux boot
protocol. GRUB is not installed on the target system.

The live ISO continues to use Archiso's native live-media boot layout. Those
boot files and packages are build-time/live-environment details and do not
define the bootloader installed by Starch.

The live desktop itself remains a Plasma Wayland session. Because Calamares
runs with root privileges, its launcher uses the session's XWayland display and
preserves `DISPLAY` and `XAUTHORITY` across `sudo`; passing the live user's
Wayland runtime directory to a root Qt process is rejected by Qt. For that
reason, `xorg-xwayland` is an explicit live-image dependency even though an X11
Plasma session is not provided.

## Project status

The live environment, Calamares installation, Limine/UKI installed-system boot,
and Plasma desktop have completed an end-to-end UEFI VM test. Legacy BIOS
installation remains supported and should continue to be covered by release
testing.

See [docs/release-checklist.md](docs/release-checklist.md) for the remaining
release gates and [docs/decisions.md](docs/decisions.md) for the supported scope
and non-goals.

## Requirements

Build on an up-to-date Arch Linux system with at least 20 GiB of free space.

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

Use the repository build wrapper so the Calamares package and local repository
are staged into a fresh Archiso profile:

Before building, add the Linux Update Utility AppImage and icon as described in
[docs/linux-update-utility.md](docs/linux-update-utility.md). Both inputs are
required and remain outside version control.

```bash
./build.sh --build
```

Do not invoke `mkarchiso` directly on `archiso/profile`; that bypasses installer
staging and can leave the shared work directory owned by root or a subordinate
namespace user. If a previous build reports that a generated directory is not
writable, remove that generated state and retry:

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
before booting it.

## Repository layout

| Path | Purpose |
| --- | --- |
| `archiso/profile/` | Live ISO profile and filesystem overlay |
| `calamares/` | Installer sequence, configuration, and branding |
| `manifests/` | Requested packages for the installed system |
| `packages/calamares/` | Pinned Calamares package sources and patches |
| `packages/linux-update-utility/` | Tracked desktop integration for Linux Update Utility |
| `luu-input/` | Git-ignored AppImage and SVG inputs supplied by the builder |
| `scripts/build/` | Build and staging helpers |
| `scripts/installer/` | Installation, target configuration, and validation jobs |
| `scripts/validate/` | Generated-system validation tools |
| `tests/` | Automated tests |
| `docs/` | Architecture, decisions, testing, provenance, and release notes |
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

Keep source changes outside generated `build/work/` trees and run the checks
above. Installer safety changes should include regression coverage, especially
for disk selection, partitioning, bootloader installation, and target
validation.

## Licensing

Original Starch Linux software is licensed under the GNU General Public License
version 3 or later. The Fastfetch artwork is dedicated under CC0 1.0 Universal.
Third-party work remains under its respective licenses; provenance and notices
are recorded in [docs/third-party/](docs/third-party/) and
[docs/third-party-provenance.tsv](docs/third-party-provenance.tsv). Modified
distributions must use a different name and branding; see
[TRADEMARKS.md](TRADEMARKS.md) and [docs/licensing.md](docs/licensing.md).
