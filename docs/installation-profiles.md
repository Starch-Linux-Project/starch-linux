# Installing Starch Linux

The installer configures COSMIC Wayland with COSMIC Greeter, Linux LTS, systemd,
and official Arch repositories. The live ISO uses the regular Arch kernel and
starts COSMIC automatically. Both use the Starch COSMIC defaults for the panel,
dock, theme, wallpaper, desktop shortcuts, and on-screen keyboard.

Before erasing the selected disk, Calamares downloads the essential packages
into the live session's temporary storage and keeps the repository databases
used to resolve them. This requires enough free space in live `/tmp` for the
compressed packages. On the normal RAM-backed live system, available memory
also limits this space. A download or space failure stops before partitioning.
The installer uses the retained packages during bootstrap. The installed system
uses ext4, zram, and Limine with UEFI or legacy BIOS. An internet connection is
required. See [supported installation options](decisions.md).

## Additional Software

Optionally enter **Pacman package names** and
**Flathub app IDs** in separate fields. Separate entries with spaces, commas,
or newlines. Both fields start empty; there are no presets or AUR support.
Entries survive backward navigation and appear in Summary. Duplicate entries
are installed once per field.

Optional installs run in the mounted target only after essential OS installation
and validation succeed, immediately before unmounting. Pacman uses the target's
configured Arch repositories. Flathub
apps install system-wide; the Flathub remote is added if missing. No installation
is deferred to first boot or login.

A separate progress window shows each requested install, its elapsed time, and
live package-manager output. Each request is checked in the installed package
database before being reported as installed. **Skip remaining
optional installs** waits for the current transaction to finish, then skips the
rest without interrupting package writes. Failed or invalid requests appear as
warnings; other requests continue, and the completed OS installation is neither
failed nor rolled back. Results remain visible until you choose **Continue**,
including when all requests succeeded. Failure output stays in the results when the next request
starts. Per-request outcomes and package command logs are retained under
`/var/log/starch-installer/` in the target.

## Updates and existing installations

Linux LTS refers to the installed kernel. Starch continues to use Arch's
rolling repositories for desktop and system packages. Rebuilt images apply
to new installations. Existing installations keep their current desktop.

The target package requests are recorded in
[the installation manifest](../manifests/minimal-packages.txt). Preflight adds
hardware-specific microcode and graphics packages and adds Plymouth for BIOS.
The historical `standard-cosmic` identifier remains in installation logs.
