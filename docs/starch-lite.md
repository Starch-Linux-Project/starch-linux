# Starch Lite

Select **Starch Lite — For experienced users** on the Installation Profiles page.
Lite uses Xfce on X11, LightDM, Linux Zen, OpenRC, and elogind.

Packages come from Artix `system`, `world`, and `galaxy`, then Arch `extra`;
Arch `core` is disabled. Update with `sudo pacman -Syu`.

Lite retains Limine, ext4, NetworkManager, PipeWire/WirePlumber, nftables,
and zram. Its integration package supplies the boot banner, zram service,
low-memory settings and Xfce defaults. Thunar is the file manager; compositing and session
restoration are off by default. Standard user folders are created at login.
A recovery text login is available with **Ctrl+Alt+F2**.

The live ISO remains Plasma with systemd. Starch's Lite configuration package
is bundled with the ISO and has no dedicated binary update repository.

## Audio and sessions

Artix owns audio supervision through `pipewire-openrc`, `pipewire-pulse-openrc`,
`wireplumber-openrc` and `dbus-openrc`. User D-Bus starts in the OpenRC user
`boot` runlevel; PipeWire, PipeWire-Pulse and WirePlumber start in `default`.
The installer seeds these runlevels in `/etc/skel` before creating the account.
They are user services, not system PipeWire daemons.

Upstream Artix PAM (`pambase`, LightDM and OpenRC) supplies `pam_elogind` and
`pam_openrc`: elogind provides session/runtime setup and OpenRC manages user
services across logins. Starch does not rewrite PAM or maintain an audio
supervisor. Audio service updates arrive through normal Artix package updates.

New images require `starch-lite 0.2.2-16` and bundle format 3. Old ISO images
and installed systems do not change when source is rebuilt. See
[existing-installation migration, rollback and VM checks](starch-lite-audio-migration.md).
The implementation is verified offline; fresh-VM login, recovery and logout
acceptance remain required before release.
