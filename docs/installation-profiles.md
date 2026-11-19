# Installation profiles

Starch provides three installation profiles in one ISO. Each profile defines a
desktop, login manager, kernel, init system, and repository configuration.

| Profile | Desktop / login | Kernel / init | Repositories |
| --- | --- | --- | --- |
| KDE Plasma LTS — Recommended (default) | Plasma Wayland / SDDM | Linux LTS / systemd | Arch |
| COSMIC LTS | COSMIC Wayland / COSMIC Greeter (greetd) | Linux LTS / systemd | Arch |
| Starch Lite — For experienced users | Xfce X11 / LightDM | Linux Zen / OpenRC | Artix, then Arch `extra` |

## Desktop environments and components

### KDE Plasma LTS

KDE Plasma LTS is the default profile. Its desktop runs on Wayland, with SDDM
for login, the `linux-lts` kernel, systemd, and Arch repositories.

The installed application selection includes Nautilus for file management,
COSMIC Terminal and Text Editor, Gwenview for images, Spectacle for screenshots,
and Plasma System Monitor.

Plasma provides its own on-screen keyboard integration and sensor rotation
through KWin and Qt Sensors. Related documentation: [keyboard controls](virtual-keyboard.md)
and [screen rotation](rotation.md).

### COSMIC LTS

COSMIC LTS runs the COSMIC Wayland desktop with the `linux-lts` kernel, systemd,
and Arch repositories. COSMIC Greeter, through greetd, handles login.

It includes COSMIC Files, Terminal, Text Editor, Viewer, Screenshot, and Store,
along with COSMIC desktop portals and GNOME Keyring. Dedicated Starch defaults
configure the desktop; the on-screen keyboard opens manually, and automatic
rotation uses Starch's session helper.

The installer audits the resolved COSMIC packages against reviewed versions and
can stop installation when repository packages move beyond that baseline. This
check applies to fresh installations; it does not lock package versions on an
installed system. The [COSMIC reference](cosmic.md) records the reviewed
baseline, authentication details, and verification limits.

### Starch Lite

Starch Lite runs Xfce on X11 with the `linux-zen` kernel, OpenRC, LightDM for
login, and elogind for session management.

Thunar handles files, Ristretto handles images, and Xfce supplies screenshot and
task-manager applications. Compositing and session restoration are disabled by
default. The bundled Lite integration supplies low-memory settings, zram
configuration, and Xfce defaults. Starch's automatic screen-rotation integration
is not included in Lite.

Repository priority is Artix `system`, `world`, and `galaxy`, followed by Arch
`extra`; Arch `core` is disabled. System services use OpenRC. Audio runs through
Artix's OpenRC user services for PipeWire and WirePlumber. A recovery text login
is available with **Ctrl+Alt+F2**.

Lite is included in normal ISO builds. Its choice is disabled if the required
bundle is missing, and installation also verifies the bundle before using it.
The [Starch Lite reference](starch-lite.md) covers service integration and
existing-system migration.

New Lite installations use a full-width top taskbar and a centered bottom dock
with Thunar, COSMIC Terminal, and Firefox launchers. The native Xfce dock hides
when the focused window overlaps it. Existing user panel settings are preserved.

## Shared components

- An x86_64 installation with Limine boot support for UEFI or legacy BIOS.
- An ext4 root filesystem and compressed RAM swap through zram, rather than a
  disk swap partition.
- NetworkManager, PipeWire/WirePlumber audio, and nftables.
- Fish as the standard user's default shell, with authenticated desktop login
  and installed-system autologin disabled.
- Shared applications including Firefox, VLC, nano, and btop.
- Flatpak with Flathub configured; no Flatpak applications are selected by default.
- [Linux Update Utility](linux-update-utility.md), supplied as a bundled AppImage.

The [base package manifest](../manifests/minimal-packages.txt) is the starting
point, not the complete package list for every profile. The installer replaces
desktop and init packages for the chosen profile, resolves dependencies, and
selects graphics packages for the detected hardware and target kernel.

## Installation model and supported scope

Installation requires an internet connection: Calamares downloads fresh target
packages with `pacstrap`. It does not copy the running live desktop into the
installed system. The live ISO always runs Plasma, systemd, and the regular
Arch `linux` kernel, independent of the target profile.

All three profiles use an erase-disk installation that replaces the contents
of the entire selected disk. Manual partitioning,
install-alongside/dual boot, offline installation, full-disk encryption, Secure
Boot, hibernation, and snapshot rollback are outside the supported scope.
There are no ARM or 32-bit images. Installation and hardware boundaries are
documented in [supported scope](decisions.md).

The Installation Profiles page allows one selection at a time. Selection
persists across backward navigation and appears on the Summary page. Desktop,
kernel, and init are fixed combinations; Plasma/OpenRC, COSMIC/OpenRC, and
Xfce/systemd are not supported installation profiles.

## Additional Software

After selecting a profile, optionally enter **Pacman package names** and
**Flathub app IDs** in separate fields. Separate entries with spaces, commas,
or newlines. Both fields start empty; there are no presets or AUR support.
Entries survive backward navigation and appear in Summary. Duplicate entries
are installed once per field.

Optional installs run in the mounted target only after essential OS installation
and validation succeed, immediately before unmounting. Pacman uses the target's
configured repositories (including Lite's Artix-first configuration). Flathub
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

The **LTS** label identifies the `linux-lts` kernel in the Plasma and COSMIC
profiles. It does not turn the whole distribution into a fixed-release system
or freeze desktop applications. Standard profiles use Arch repositories
directly; Lite uses its configured Artix and Arch repositories.

Starch does not stage upstream Arch updates or provide automatic rollback.
Starch-owned utilities and configuration are bundled with ISO releases and have
no dedicated update channel for existing installations. Rebuilding an ISO
changes future installations; it does not migrate an existing desktop or reset
an existing user's settings. Profile selection is an installation choice, not
an installed-system profile-switching tool.

## Implementation reference

The internal profile identities are `standard`
(KDE Plasma LTS), `standard-cosmic` (COSMIC LTS), and `lite-xfce` (Starch Lite).
The internal Calamares module remains named `starchadvanced`, although its
visible page is **Installation Profiles**.

[`scripts/installer/profiles.py`](../scripts/installer/profiles.py) validates
the selection and chooses packages and repositories before disk operations.
The [profile fixtures](../tests/fixtures/installation-profiles.json) record the
expected package requests for all three profiles; dependencies and
hardware-specific additions can expand the final installed package set.
