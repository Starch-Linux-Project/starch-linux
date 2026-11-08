# Optional COSMIC installation

COSMIC is an opt-in **Advanced** checkbox, available with Standard or Lite.
Acknowledge the existing Advanced warning and select **Use COSMIC instead of
KDE Plasma (Wayland)**. Selecting COSMIC clears Xfce; selecting Xfce clears
COSMIC. Clearing both keeps Plasma. Xfce still requires Lite. Switching Lite
off clears Xfce but retains a selected COSMIC desktop.

| Selection | Profile ID | Kernel/init | Display manager |
| --- | --- | --- | --- |
| Default | `standard` | Linux LTS/systemd | SDDM, existing Plasma greeter |
| Lite | `lite` | Linux Zen/OpenRC/elogind | SDDM, existing Plasma greeter |
| Lite + Xfce | `lite-xfce` | Linux Zen/OpenRC/elogind | Existing LightDM configuration |
| COSMIC | `standard-cosmic` | Linux LTS/systemd | COSMIC Greeter/greetd, COSMIC Wayland session |
| Lite + COSMIC | `lite-cosmic` | Linux Zen/OpenRC/elogind | COSMIC Greeter/greetd, COSMIC Wayland session |

Implementation and static checks are complete; **neither COSMIC installation
has passed fresh-VM desktop acceptance yet**. Do not describe this as tested
dual-init desktop support. This environment exposes neither `/dev/kvm` nor a
`/dev/dri` graphics device. QEMU offers software emulation, but installed guest
login, rendering, power management and hardware acceptance were not exercised.
No desktop screenshots are available. The live ISO desktop is unchanged.

## Packages and repository policy

`profiles.selected_packages()` chooses the desktop before dependency resolution.
COSMIC removes the Plasma desktop/workspace, KWin-related roots, KDE portal,
Plasma applets/utilities, KWallet integration, Nautilus and Blueman. It requests
explicit COSMIC components, Files, Terminal, Text Editor, Xwayland, the portal
backends, Xwayland, polkit-gnome, GNOME Keyring and BlueZ. BlueZ is explicit
because removing Blueman otherwise drops the daemon that provides
`bluetooth.service`. Without it, Standard + COSMIC fails during the shared
`systemctl enable` step. The COSMIC closure audit now requires BlueZ before
partitioning. It does not request the
COSMIC group or store. Required Qt/KDE libraries and Breeze icons remain valid
application dependencies; they do not install the Plasma desktop.

`cosmic-session` requires `cosmic-greeter`, which uses `greetd` for login.
COSMIC targets now activate COSMIC Greeter rather than SDDM, as requested.
The `cosmic-greeter` service launches greetd with Starch's explicit COSMIC
configuration; the generic `greetd` service is not also enabled. SDDM and
LightDM are excluded from COSMIC package resolution. The greeter's root
helper daemon runs separately and supplies user information over system D-Bus.

Preflight audits pacman's full `%r %n %v` transaction. It rejects Plasma/KWin,
Xfce sessions, a second selected display manager or COSMIC Store. Lite also
rejects systemd runtime packages and requires Artix builds of the critical
COSMIC components. Artix `system`, `world`, `galaxy` still precede Arch `extra`;
repository URLs and signature policies are unchanged. The inspected schema
and startup version is **1.11.0**; a different upstream version stops preflight
before partitioning, pending a compatibility review.
Package releases may change, but installed COSMIC versions must still match
the transaction audited by preflight.

Offline resolution on 2026-11-08 used fresh databases from the configured
mirrors and an empty local package database, with `vulkan-swrast` selected for
the audit (base roots, before CPU microcode/firmware-specific additions).
Standard resolved 729 packages; Lite resolved 753. Neither closure
contains Plasma, KWin, KWallet or an Xfce desktop; Lite contains no systemd
runtime package. These are dependency-resolution results, not installations.
The downloaded Artix session and greeter archives matched the SHA256 values
in that repository database; installation still uses normal package signature
verification. Full local reports are in `build/cosmic-audit/db/*/resolved.txt`.
Installed systems retain their actual reports under
`/var/log/starch-installer/{resolved-packages,installed-packages}.txt`.

| Package | Standard repository/version | Lite repository/version |
| --- | --- | --- |
| cosmic-session | extra/1:1.11.0-1 | galaxy/1:1.11.0-1 |
| cosmic-greeter | extra/1:1.11.0-1 | galaxy/1:1.11.0-1 |
| cosmic-workspaces | extra/2:1.11.0-1 | galaxy/2:1.11.0-1 |
| cosmic-osk | extra/1.11.0-1 | galaxy/1.11.0-1 |
| xdg-desktop-portal-cosmic | extra/1:1.11.0-1 | galaxy/1:1.11.0-1 |
| xdg-desktop-portal | extra/1.22.1-2 | world/1.22.1-2 |
| xdg-desktop-portal-gtk | extra/1.15.3-2 | world/1.15.3-2 |
| greetd | extra/0.10.3-2 | world/0.10.3-2.1 |
| polkit-gnome | extra/0.105-12 | world/0.105-12 |
| gnome-keyring | extra/1:51.1-1 | world/1:51.1-1 |
| pipewire | extra/1:1.6.10-1 | world/1:1.6.11-1 |
| wireplumber | extra/0.5.18-1 | world/0.5.18-1 |
| linux-lts | core/6.18.60-1 | — |
| linux-zen | — | galaxy/7.2.14.zen1-1 |
| systemd | core/262.1-1 | — |
| openrc | — | system/0.64.1-2 |
| elogind | — | system/257.16-1 |

All inspected COSMIC desktop components use 1.11.0 (usually epoch `1`, with
workspaces using epoch `2` and OSK no epoch).

## Defaults and session ownership

Maintained input is `packages/starch-cosmic/{root,lite-root}`. Staging separates
shared branding/firewall/LUU/wallpapers from desktop overlays. Bootstrap copies
only the selected desktop's defaults before account creation. Lite's existing
Plasma defaults are preserved verbatim in its integration package and copied
into `/etc/xdg` only for the original profiles. No active Plasma defaults or
Plasma login command is selected on a COSMIC target.

COSMIC seeds only 13 keys: dark mode without automatic switching, readable
Starch blue (`#4DA9DF`), Evergreen, floating windows, a small centered native
dock, its Firefox/Files/Terminal/LUU favorites, and launcher/workspaces plus
normal status controls in the top panel. The clock and other unmodified
behavior use upstream defaults. Favorites use installed desktop-entry stems:
`firefox`, `com.system76.CosmicFiles`, `com.system76.CosmicTerm`, and
`linux-update-utility`. Validation checks the corresponding `.desktop` files
and Evergreen image. Fonts, scaling and window controls remain upstream.

Keys are seeded under `/etc/skel/.config/cosmic`, not reapplied at login.
`cosmic-config` finds a system default *directory* through XDG data paths;
a partial `/usr/local/share/cosmic` directory would shadow the package's
remaining defaults. Minimal per-key skel values preserve those fallbacks and
avoid overwriting package-owned data. No monitor IDs, caches or output layouts
are copied. User customizations survive login and reboot by construction;
this still needs confirmation in the installed desktop acceptance test.

COSMIC Greeter runs inside `cosmic-comp` on tty1 with a private D-Bus
session. Its launch script preserves errors in the service log. The launcher
and its parent directory explicitly use mode 0755, including under Calamares's
restrictive umask. Validation checks executable access and shell readability
as the unprivileged `cosmic-greeter` account rather than only as root. It discovers
`cosmic.desktop` in the standard `/usr/share/wayland-sessions` directory.
Standard retains the packaged `start-cosmic` launcher; Lite rewrites that entry
to its session supervisor so selecting COSMIC actually starts the Lite session.
The Lite package keeps its dormant Plasma session entry outside standard
session discovery and copies it back only for the existing profiles. Validation
rejects additional session choices on a COSMIC target. No automatic user login
is configured. Systemd activates the greeter through
`display-manager.service`; OpenRC starts its greeter and helper services after
D-Bus and elogind. Lite keeps its recovery console on tty2.

On Standard, the packaged launcher and systemd user services own the session
and audio. The Lite supervisor is not installed. On Lite, the small
`/usr/lib/starch-cosmic/session` wrapper checks the PAM-owned runtime directory,
sets COSMIC's desktop environment, creates a D-Bus session only if one is absent,
and runs the packaged `/usr/bin/start-cosmic`. It owns an audio-supervisor group
and a COSMIC group, and cleans up only those groups on session exit. The existing
KDE-only audio autostart is not activated on COSMIC. The Artix audio packages
inspected contain no competing XDG autostarts.

Artix's session recipe builds with `--features autostart`; upstream 1.11.0 scans
XDG autostarts when `/run/systemd/system` is absent. Its maintained patch
substitutes optional loginctl commands in the systemd integration module; we
do not replace or hide `systemctl`. Its packaged `start-cosmic` establishes the
environment and avoids a nested session bus. The compositor exports Wayland/X11
display addresses into the D-Bus activation environment. Portals start through
packaged D-Bus activation, not another Starch process supervisor. The packaged
`cosmic-portals.conf` selects COSMIC first, GTK only for missing interfaces, and
GNOME Keyring for Secret. COSMIC itself provides FileChooser, ScreenCast,
RemoteDesktop, Screenshot, Settings and Access.

A COSMIC-only polkit-gnome XDG autostart provides authorization prompts on both
init systems. Login uses a dedicated `starch-greetd` PAM policy, including
`system-local-login` for authentication, account checks and session registration,
plus GNOME Keyring unlocking. Lite's system-login registration uses elogind.
The packaged lock screen calls PAM service `cosmic-greeter`; Starch supplies
that separate policy delegating authentication/account checks to `system-auth`,
denying root and respecting `pam_nologin`. No permissive polkit rules or
root-run desktop processes are introduced.

Schema/startup sources inspected:

- [COSMIC session 1.11.0](https://github.com/pop-os/cosmic-session/tree/epoch-1.11.0),
  commit `4b0a0a24e98b9e755b6a7146e4cb29539cacda0a`.
- [Artix recipe and patches](https://gitea.artixlinux.org/packages/cosmic-session/src/commit/8502cb4759209bfb970b7c206437f7511963d6d3).
- [Panel default schema](https://github.com/pop-os/cosmic-panel/tree/epoch-1.11.0/data/default_schema)
  and [applet favorites](https://github.com/pop-os/cosmic-applets/blob/epoch-1.11.0/cosmic-app-list/cosmic-app-list-config/src/lib.rs).
- [Wallpaper schema](https://github.com/pop-os/cosmic-bg/blob/epoch-1.11.0/config/src/lib.rs)
  and [compositor schema](https://github.com/pop-os/cosmic-comp/blob/epoch-1.11.0/cosmic-comp-config/src/lib.rs).
- [libcosmic theme/config types](https://github.com/pop-os/libcosmic/tree/430f3d48a97d8779f9c1985473912e594ccca1ae),
  the revision pinned by COSMIC Settings 1.11.0. Theme components and builder
  use `v2`; mode, panel, background, compositor and favorites use `v1`.
- [Lock-screen PAM calls](https://github.com/pop-os/cosmic-greeter/blob/epoch-1.11.0/src/locker.rs).

## Checks run and installation verification

- `python3 -m unittest discover -s tests/unit`: 87 tests passed, including all
  five selection mappings, mutually exclusive checkboxes/backend state,
  desktop-only overlays, unchanged Lite default contents, init/native-greeter branches,
  dependency-closure rejection, target validation and owned-process cleanup.
- `tests/calamares/advanced-selection.cpp`: the actual built plugin passed
  offscreen checkbox/state transitions for all profiles, mutual exclusion,
  disabling Lite and resetting acknowledgement. See its [runner notes](../tests/calamares/README.md).
- All Calamares patches applied to pinned 3.3.14; configuration schema validation
  passed, including `displaymanager.conf` and `starchadvanced.conf`.
- `scripts/build/calamares.sh --build`: built `calamares-starch 3.3.14-12`.
- `scripts/build/starch-lite.sh --ensure`: built `starch-lite 0.2.2-14` with the native-greeter PAM support and dormant
  Plasma session entry outside greeter discovery.
- `bash scripts/validate/calamares-smoke.sh`: installer remained open for 20
  seconds offscreen and `starchadvanced` loaded. The chroot reports expected
  missing system D-Bus warnings; this is not a login or installation test.
- A disposable Rust/serde/RON check deserialized all 13 settings; theme colors
  used the pinned upstream `Component` and `ColorReprOption` types directly.
  Sources and output are under `build/cosmic-audit/ron-check*`; no Rust runtime
  or build dependency was added to the installer.
- `git diff --check`: passed.

Build a new ISO with the normal build process so it contains both rebuilt
packages and the new overlays; an old ISO does not gain the checkbox. In fresh
VMs, install Standard + COSMIC and Lite + COSMIC, and retain regression installs
of the original choices. Test login, logout/login, reboot, appearance/pins,
LUU, networking, microphone/audio, removable drives, polkit, lock/unlock,
Flatpak file dialogs and screen sharing. Test Bluetooth and suspend/resume
on suitable hardware. Confirm kernel, PID 1 and desktop with:

```sh
uname -r
ps -p 1 -o comm=
printf '%s\n' "$XDG_CURRENT_DESKTOP" "$XDG_SESSION_TYPE" "$DBUS_SESSION_BUS_ADDRESS"
stat -c '%u %a' "$XDG_RUNTIME_DIR"
pgrep -a -u "$USER" 'pipewire|wireplumber|cosmic-session'
pacman -Q cosmic-session cosmic-greeter greetd
pacman -Q plasma-desktop plasma-workspace kwin xfce4-session sddm
```

The final query must report those desktop packages absent. Expect one PipeWire,
one pipewire-pulse and one WirePlumber per active session. Check `systemctl is-enabled cosmic-greeter` reports enabled on Standard,
`display-manager.service` points to `cosmic-greeter.service`, and the generic
`greetd.service` is masked. On Lite, `rc-status -a` must show
cosmic-greeter/cosmic-greeter-daemon/elogind/D-Bus with no SDDM or generic greetd service. Verify the package report shows Artix origins
on Lite. After logout, inspect from the recovery console that owned audio,
polkit and COSMIC children are gone. Change a dock pin/theme preference and
confirm it survives logout and reboot. Record screenshots, installed versions
and remaining hardware limitations before claiming release acceptance.
