# Linux Update Utility integration

Starch includes Linux Update Utility in both the booted live environment and
the system produced by Calamares. The utility remains a separately built
project: this repository tracks its desktop integration, but not its AppImage
or artwork.

## Build inputs

Create `luu-input/` at the repository root and place exactly these two inputs
inside it:

- one file whose name ends in `.AppImage`;
- one SVG icon whose name ends in `.svg`.

The filenames before those extensions are unrestricted. The build rejects a
missing input, duplicate AppImages or icons, and symbolic links. Other files in
the directory are not consumed. The entire directory is Git-ignored so large
binaries, candidate builds, and release artwork cannot be committed
accidentally.

Run the input and host checks with:

```bash
./build.sh --check
```

At the start of a build, both files are copied into the build's private run
directory. The remainder of that build uses this snapshot, so replacing an
input while Archiso is running cannot mix versions in the resulting image.

## Installed files

The input filenames are normalized to fixed system paths:

| Path | Mode | Purpose |
| --- | ---: | --- |
| `/usr/local/bin/linux-update-utility.AppImage` | `755` | Application executable |
| `/usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg` | `644` | Application icon |
| `/usr/share/applications/linux-update-utility.desktop` | `644` | Desktop and application-menu entry |

The desktop entry is maintained at
`packages/linux-update-utility/linux-update-utility.desktop` and uses the
following application identity:

- name: `Linux Update Utility`;
- comment: `Update your Linux system through a graphical interface`;
- categories: `System;Settings;`;
- startup window class: `linux-update-utility`;
- terminal: disabled.

The `Exec` and `Icon` values use the fixed absolute paths above. `fuse2` is an
explicit dependency in both the live and installed package manifests because
the supplied utility is a type-2 AppImage.

## Live and installed-system flow

The staging helper writes one copy directly into the generated Archiso
filesystem for the live session. It also writes a copy into the installer's
target overlay. After `pacstrap` creates a fresh target system, the bootstrap
job applies that overlay to the mounted target. The installer does not copy the
live root filesystem.

Generated-live validation and final installed-system validation both require
all three files and their exact modes. Unit tests separately verify the desktop
entry and staging behavior. A build or installation stops when these contracts
are not met.

## Release and update policy

Changing either local input requires rebuilding the ISO. Existing Starch
installations do not receive a replacement AppImage through a Starch package
repository or dedicated Starch update channel.

The input files must be license-cleared before an ISO is distributed. Record
the artifact version, source, checksums, license, notices, and redistribution
terms as required by [licensing.md](licensing.md). Keeping an artifact out of
Git does not exclude it from release licensing obligations.
