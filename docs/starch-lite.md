# Starch Lite optional configuration

Status: included in normal builds as an optional configuration; fresh boot and
desktop validation remain required.

Starch Lite is an optional configuration of **Starch Linux**, selected in the
installer's Advanced page. It keeps the same installed OS name, identity,
branding, applications and desktop defaults. It is not a separate distribution.
The checkbox defaults off and requires the Advanced warning acknowledgement.

## Scope and repositories

Only Lite targets use this repository order, defined in
`calamares/pacman-lite.conf`:

1. Artix `system` — replaces Arch `core` for the base system.
2. Artix `world` and `galaxy` — supply compatible desktop, kernel and service packages.
3. Arch `extra` — supplies additional packages after Artix takes precedence.

Arch `core` is not enabled for Lite. Artix's `artix-archlinux-support` and both
distributions' keyrings are installed. Repository package signatures remain
required. The installed configuration uses these same repositories for updates.

Standard Starch and the live ISO continue using their existing Arch repositories,
packages and systemd runtime. Their manifests and repository files are unchanged.
The live ISO carries Lite inputs as installer data; it does not install or start
OpenRC, import Artix signing trust into its main keyring, or enable Artix repos
for the live system.

## What the configuration changes

The package list is derived from `manifests/minimal-packages.txt`; it is not a
second independent application list. Lite selects `linux-zen` instead of
`linux-lts`, replaces systemd D-Bus/zram choices, and adds Artix's OpenRC services.

| Component | Lite configuration |
| --- | --- |
| Kernel | Linux Zen; matching headers and DKMS for supported NVIDIA GPUs |
| Init | Artix OpenRC, selected by `init=/usr/bin/openrc-init` |
| Boot | Existing Limine installation; Zen UKI for UEFI, kernel/initramfs for BIOS |
| UKI tooling | Artix mkinitcpio, eukify and its EFI stub dependency |
| Desktop | KDE Plasma Wayland with `systemdBoot=false` |
| Sessions | Artix elogind, PAM and SDDM packages; a Starch session wrapper |
| Services | Artix D-Bus, NetworkManager, nftables, Bluetooth, SDDM and syslog-ng OpenRC scripts |
| zram | Starch OpenRC script preserving the standard min(RAM/2, 4 GiB) policy |

The small `starch-lite` package contains configuration, the session/audio wrapper,
a PAM maintenance hook and the zram service. OpenRC and elogind are no longer
Starch-built forks: Artix maintains them and their service packages, updated by
`pacman -Syu`. The previous custom OpenRC/elogind recipes have been removed.

Starch's normal firewall rules are used by Artix's nftables service. The login
screen exposes the configured Wayland session. Artix's Plasma package currently
requires an X11 session package as a dependency; that does not enable an X11
session in Starch's login screen.

Because Lite has no systemd user manager, `/usr/lib/starch-lite/audio-session`
starts PipeWire first, waits for its control plane, starts the PulseAudio server
and waits for its socket, then starts WirePlumber. It supervises and restarts the
stack for the Plasma session. Diagnostics are written to
`~/.local/state/starch/audio-session.log`.
The Lite package also installs a KDE autostart entry, so audio starts when
Plasma is launched without the custom login wrapper. A runtime-directory lock
prevents the wrapper and autostart entry from starting duplicate stacks.
This entry is installed only with the optional Lite package.

Starch Lite ships as an optional configuration of Starch Linux 1.2 Evergreen,
without a separate public release version. Pacman package versions are internal
update metadata.

The Artix OpenRC binary has a compiled-in Artix startup banner. Lite uses
`/etc/rc.conf.d/10-starch-branding.conf` to enable quiet informational output
and a `starch-banner` sysinit service to print the Starch release name.
Routine OpenRC status messages are suppressed; warnings and errors remain.
The upstream OpenRC binary is not modified.

The installed OS remains `NAME="Starch Linux"`, `ID=starch`, with the standard
Starch version and branding. The Zen boot entry is named **Starch Linux** and
the session is **Plasma (Wayland)**. “Starch Lite” identifies only the optional
installer configuration and its maintenance package.

The Plasma profile uses the Starch panel layout with Firefox, Nautilus, COSMIC
Terminal and Linux Update Utility pinned in that order. The Xfce profile also
pins Linux Update Utility in its panel.

## Build and select

Build the configuration package and verified keyring bundle:

```sh
./scripts/build/starch-lite.sh --build
```

Artifacts are written to `build/starch-lite/artix-repo/`. The script uses an
isolated Arch build root for the script-only package; Artix runtime packages
are resolved and installed only into Lite targets. It never converts the build
host or the live ISO to Artix.

Build the ISO normally. This builds or reuses the verified Lite bundle and
enables the optional checkbox:

```sh
./build.sh --build
```

Open Advanced, acknowledge the warning, then select Starch Lite. Revoking the
acknowledgement clears the selection. Leaving Lite unchecked installs standard
Starch exactly as before.

## Signing trust and updates

`packages/starch-lite/artix-keyring.json` pins the Artix bootstrap keyring archive
URL and SHA-256. This reviewed pin is the initial Artix trust anchor; updating it
requires reviewing the source and checksum. The builder verifies it before
including it in the ISO bundle. The bundle format rejects the older custom
runtime package set.

Preflight verifies the bundle and initializes a separate temporary keyring with
Arch and Artix trust. It resolves Lite dependencies before partitioning. Pacstrap
uses that trust to verify repository packages. The target receives its own
keyring and the selected repository configuration. Only the locally built,
checksum-verified `starch-lite` archive gets a scoped local-signature exception;
the installed pacman configuration continues to require signatures.

Runtime updates come from Artix and Arch extra. Starch configuration updates
require rebuilding and installing the `starch-lite` package; it has no separate
binary update repository. AUR helpers are not required for OpenRC or elogind.
The PAM hook preserves elogind registration after relevant package updates.
Zen kernel updates regenerate the UKI using the existing mkinitcpio preset.

Rolling repository contents are not frozen by the configuration package. Save
package inventories, bundle hashes and source inputs with each tested ISO.

## Validation

### Xfce desktop option

With Starch Lite checked in Advanced, select **Use Xfce instead of KDE Plasma
(X11)**. This installs Xfce as the only desktop, not alongside Plasma. It remains
Starch Linux with the same Evergreen wallpaper. Plasma, KWin, the Plasma keyboard
and KDE desktop applications are excluded before package resolution. Thunar,
COSMIC Terminal, Ristretto, Xfce Screenshooter and Task Manager supply their desktop
roles; GTK portals and the GNOME PolicyKit agent replace KDE's integrations.
The Xfce applications menu favorites are Web Browser, File Manager and Terminal
Emulator, with Firefox, Thunar and COSMIC Terminal as their defaults. Mail Reader
is omitted from the favorites.
Qt libraries may still be installed for SDDM or applications.

SDDM runs on Xorg with its embedded theme and exposes only the native Xfce
session copied from Artix's xfce4-session package. That session is preselected
for the first login. SDDM and Xfce's Xsession scripts establish the session
environment; Starch does not replace its D-Bus connection. Lite's PipeWire
supervisor and cosmetic defaults launch through Xfce autostart after the
desktop session starts. Xfce uses a dark GTK theme, Evergreen wallpaper and a single
panel with an application menu, tasks, tray, audio controls, clock and session
actions. Compositing, GTK animations and session restoration default to off.
Existing Xfce user configuration is preserved.

Leaving Xfce unchecked retains Plasma in Lite. Standard Starch and the live
ISO retain their existing desktop. The preflight profile identity includes the
choice, and final validation rejects Plasma or KWin in an Xfce installation.

These changes apply to fresh installations; they do not remove KDE from an
existing installation. Fresh-install testing of login/logout, audio, mounting,
authentication, locking, suspend and multi-monitor wallpaper remains required.

### Lite memory and desktop defaults

Fresh Lite installations enable one text console: `agetty.tty1` for Plasma,
or `agetty.tty2` in the earlier boot runlevel for Xfce, before SDDM starts in
the default runlevel, so Ctrl+Alt+F2 provides a recovery login beside the
graphical session. The installer removes the other getty runlevel entries.
This disables their text-login
services, not the kernel's virtual terminals or SDDM's graphical session.

Only the Lite package installs `/etc/sysctl.d/99-low-ram.conf`. The installer
enables OpenRC's `sysctl` service in the boot runlevel, which loads sysctl.d
settings on each boot. Swappiness 100 and page-cluster 0 suit the existing zram
swap configuration; watermark boosting is disabled and the watermark scale is
10 to limit spare-page reserves. These are standard Linux VM settings supported
by Zen, not special Zen-only controls. They trade some latency under pressure
for memory availability; no fixed RAM saving is promised. Caches are not flushed
and overcommit/OOM safeguards are unchanged.

KDE defaults in `/etc/xdg` disable animations and decorative KWin effects,
including blur and background contrast. Wayland compositing, overview/window
management and accessibility functionality remain available. Users can override
the defaults in their own configuration.

Akonadi is off at a fresh login: calendar/reminder autostart defaults are off
and Plasma starts an empty session rather than restoring PIM applications.
The current baseline package list does not include Akonadi. Installing and
explicitly opening a PIM application can still start it on demand. This does
not misuse the Akonadi database `StartServer` option, which is not a switch
for disabling the whole service.

After installing, verify with `rc-update show boot`, `rc-service sysctl status`,
and `sysctl vm.swappiness vm.page-cluster vm.watermark_boost_factor
vm.watermark_scale_factor`. On an existing Lite install, enable the service with
`sudo rc-update add sysctl boot` after updating the package, then reboot.
Existing per-user KDE overrides take precedence over these defaults.

Development checks on 2026-10-15: the `starch-lite` 0.2.0 package built
successfully, all 55 installer unit tests passed, and the complete Lite package
list and local integration package resolved against Artix plus Arch extra.
The bootstrap Artix keyring and sampled OpenRC/service archives passed signature
verification using the isolated keyring. These are build and dependency checks,
not fresh-install or graphical-session validation.

The earlier Arch-only experimental bundle built and reached OpenRC in a QEMU
UEFI fixture, but did not demonstrate graphical login. Those results do not
validate the new Artix-based configuration. Do not reuse that fixture or its
old package bundle as evidence for this implementation.

Before public enablement, test fresh UEFI and BIOS installations, PID 1,
graphical login, logout/login, runtime-directory ownership, D-Bus, networking,
audio, suspend/resume, shutdown/reboot and kernel/package updates. Exercise the
actual Calamares partition/bootstrap path as well as target configuration.
Check standard installs for regressions and test NVIDIA/hybrid GPUs separately.
Measure resource usage before making performance claims.

### Xfce startup diagnostics

Xfce now follows the packaged `xfce.desktop` → `startxfce4` → Xfce xinitrc
startup path. First-login appearance changes are not on the critical login
path. The panel is seeded before the user is created. Session errors are in
`~/.local/share/sddm/xorg-session.log`; audio diagnostics remain in
`~/.local/state/starch/audio-session.log`. The former custom
`xfce-session.log` is no longer the active session log.

References checked: [SDDM Xsession](https://github.com/sddm/sddm/blob/v0.21.0/data/scripts/Xsession),
[Xfce startxfce4](https://github.com/xfce-mirror/xfce4-session/blob/xfce4-session-4.20.4/scripts/startxfce4.in),
and [OpenRC agetty guide](https://github.com/OpenRC/openrc/blob/0.63.3/agetty-guide.md).
The console instance includes both its init.d link and conf.d configuration.
A black screen or nonresponsive VT switch still requires installed-system logs;
these source-level checks do not establish successful graphical boot.
