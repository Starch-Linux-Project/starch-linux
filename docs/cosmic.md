# COSMIC LTS

Starch Linux uses Arch packages, Linux LTS, systemd, and COSMIC Wayland with
COSMIC Greeter (greetd). The live ISO uses the Arch kernel and starts the same
desktop with a temporary live account.

The desktop includes COSMIC Files, Terminal, Text Editor, desktop portals,
GNOME Keyring, and Starch desktop defaults. The on-screen keyboard opens
manually; automatic screen rotation uses the Starch session helper.
See [keyboard](virtual-keyboard.md) and [rotation](rotation.md) controls.

## Ownership and startup

Arch supplies `cosmic-greeter.service`, `cosmic-greeter-daemon.service`, their
binaries, D-Bus policy, account/directory declarations, the native COSMIC OSD
polkit agent, and the COSMIC session launcher. Fresh installations enable the
vendor display manager and mask competing greetd/SDDM/LightDM services. They
have no full Starch unit replacements or service drop-ins, so pacman updates
to the vendor units take effect normally on subsequent service loads/reboots.
The vendor unit orders startup after its daemon and requests it with `Wants=`.
There is no established requirement for Starch's former `Requires=` or its
three-second restart delay; the vendor one-second delay is used.

The installer still manages:

- `/etc/greetd/cosmic-greeter.toml`: tty1, authenticated login and the Starch
  login PAM service. This is an upstream backup file; review future `.pacnew`
  files rather than overwriting local settings.
- `/etc/pam.d/starch-greetd`: upstream `system-local-login` authentication,
  account, password and session policy plus optional GNOME Keyring password
  handoff and startup. Arch's `login` stack lacks these explicit keyring rules.
- `/usr/lib/starch-cosmic/greeter`: provisionally retained, with COSMIC XDG
  variables and a private `dbus-run-session`. The upstream launcher clears
  greeter settings state and suppresses output instead. Equivalent greeter
  environment, bus lifetime and diagnostic behavior need a booted comparison
  before this helper can safely be retired. No new launcher is introduced.
- Display-manager selection, masks, graphical boot and global enablement of
  upstream PipeWire sockets/WirePlumber; normal power-management defaults.
- Panel/dock/favorites, theme/accent, wallpaper, tiling, OSK and Viewer/VLC MIME
  defaults. User homes are seeded before account creation, not reset on updates.
- The separate rotation helper and rotation-lock control.

Scoped sysusers/tmpfiles calls remain as idempotent installer ordering safeguards.
Arch's current hooks already process them in chroots; these calls do not repair
an assumed upstream chroot defect. Validation checks the account and ownership
of its home and runtime directories before declaring installation successful.

## Authentication baseline

Fresh installations and live images include Arch's `fprintd` and `libfprint`
regardless of reader hardware. Arch owns their D-Bus activation, systemd unit,
udev rules and Polkit policy. Enrollment UI and desktop authentication depend
on upstream COSMIC integration. Greetd's existing selection of `starch-greetd`
means changes specific to the vendor login PAM service may not apply at login.

The desktop manifest is consumed at installation. There is no installed
desktop metapackage to pull these dependencies onto older installations.
Once installed, both packages receive normal Arch package updates.

Runtime validation is pending. On a supported reader, check device discovery
with the fprintd Manager's `GetDevices` D-Bus method, then test
`fprintd-enroll` and `fprintd-verify` as a disposable test user. Test password
login and unlock on both that system and a machine without a reader.

On 2026-11-15, Arch `cosmic-greeter 1:1.11.0-1` still reverted upstream commit
`ef1253aa2393666bb2a0b0132b722f51ec7ebbf3`. This restores **login** as the locker's
PAM service as well as the vendor TOML's login selection. The locker calls
PAM authentication and account management, not a new login session. Starch's
old `/etc/pam.d/cosmic-greeter` was unused by that build and is no longer copied
into fresh COSMIC LTS targets. This is a source/packaging finding, not a claim
that a VM unlock test has passed.

Greetd user login still selects `starch-greetd`. Its default greeter-account
service is `greetd-greeter`; greetd 0.10.3 falls back to the general service when
that PAM file is absent. We leave that selection and fallback unchanged; the
launcher does not fabricate a runtime directory or bypass account/session checks.

COSMIC OSD 1:1.11.0-1 registers its native polkit agent, so the additional GNOME
agent is absent from fresh installations and live media.

`profiles.py` accepts upstream 1.12.x patch releases for the checked COSMIC
components. Greeter and OSD require Arch `extra/1:1.12.0-1` because a packaging
revision can change locker PAM selection or native agent activation.
The [Arch 1.12 greeter recipe](https://gitlab.archlinux.org/archlinux/packaging/packages/cosmic-greeter/-/blob/1-1.12.0-1/PKGBUILD)
retains the PAM revert. The [1.12 OSD](https://github.com/pop-os/cosmic-osd/blob/epoch-1.12.0/src/components/app.rs)
still subscribes to its polkit agent. Review a new minor series or either
authentication package revision before accepting it. This is an installer gate, not an installed-system
pacman version lock. No custom COSMIC package or repository is introduced;
Linux Update Utility remains outside pacman.

Evidence: [Arch greeter recipe](https://gitlab.archlinux.org/archlinux/packaging/packages/cosmic-greeter/-/blob/main/PKGBUILD),
[reverted PAM change](https://github.com/pop-os/cosmic-greeter/commit/ef1253aa2393666bb2a0b0132b722f51ec7ebbf3),
[native polkit registration](https://github.com/pop-os/cosmic-osd/blob/epoch-1.11.0/src/subscriptions/polkit_agent.rs),
[OSD activation](https://github.com/pop-os/cosmic-osd/blob/epoch-1.11.0/src/components/app.rs),
and [package-derived test fixtures](../tests/fixtures/cosmic-arch-1.11.0/README.md).

## Verification and existing systems

Unit tests cover vendor-unit preservation, offline display-manager enablement,
PAM/keyring rules, overlay cleanup, native-agent selection, and live/installed overlay parity. They do not prove successful login or authentication.

Before release, test a fresh VM and an existing-installation clone: cold boot,
login/logout, incorrect passwords and account restrictions, lock/unlock,
keyring automatic unlocking, polkit authorization/cancellation, audio/portals,
restart/reboot, daemon failure recovery, and upstream package upgrades. Test
sensor rotation, touch mapping and suspend/resume on hardware. Preserve a
working non-root TTY login with sudo throughout authentication testing.

Existing installations are not automatically migrated. Use the separate,
reversible [migration procedure](cosmic-migration.md); do not rerun installer
configuration against an installed system.
