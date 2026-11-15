# COSMIC vendor-unit migration

This is a manual procedure for existing **Arch/systemd COSMIC LTS** systems,
not an installer job, package hook, or an Artix/OpenRC procedure. First rehearse
it on a disposable clone. No automatic migration or display-manager restart is
performed by the source refactor.

## Prepare recovery and identify the installed behavior

1. Confirm a non-root user can log in on an alternate TTY and use sudo. Starch
   locks root's password; do not depend on a root-password console login.
   Keep live recovery media available and take a VM/disk backup.
2. Record `pacman -Q cosmic-greeter cosmic-osd greetd pambase gnome-keyring`,
   `systemctl cat cosmic-greeter.service cosmic-greeter-daemon.service`,
   `systemctl is-enabled cosmic-greeter.service greetd.service sddm.service lightdm.service`,
   and `readlink /etc/systemd/system/display-manager.service`. Inspect both
   `/etc/systemd/system` and `/run/systemd/system` and all relevant drop-ins.
3. Verify the exact installed greeter package's locker PAM selection. The
   reviewed Arch 1:1.11.0-1 reverts the upstream PAM commit and selects `login`.
   Do not extrapolate this to older, newer, local or Artix builds. Verify native
   OSD polkit registration in the clone before removing its fallback agent.
4. Back up the files below, preserving contents, permissions and symlinks,
   including which paths were absent. Use a root-owned directory outside the
   active configuration directories, mode 0700. Keep the package versions,
   effective unit output and hashes with that backup.

| Path | Treatment |
| --- | --- |
| `/etc/systemd/system/cosmic-greeter.service` | Review full override against the old installer output |
| `/etc/systemd/system/cosmic-greeter-daemon.service` | Review full override against the old installer output |
| `/etc/systemd/system/display-manager.service` | Preserve exact alias for rollback |
| Relevant unit drop-ins and competing-manager masks | Preserve administrator intent |
| `/etc/greetd/cosmic-greeter.toml` and any `.pacnew` | Keep tty, PAM, session and launcher settings in this migration |
| `/etc/pam.d/starch-greetd` | Keep authentication/account/session/keyring rules unchanged |
| `/usr/lib/starch-cosmic/greeter` | Keep; upstream equivalence is not yet established |
| `/etc/pam.d/cosmic-greeter` | Retire only after proving installed locker does not use it |
| `/etc/xdg/autostart/polkit-gnome-authentication-agent-1.desktop` | Retire only the recognized Starch fallback after native-agent testing |
| User autostart overrides | Inspect separately; never delete user files automatically |

The former installer output is in `scripts/installer/cosmic.py` at source
commit `f586b382712b8ea226bdbb2dea9e63f402ab85ec`. Compare manually; do not execute
that installer module on an installed machine. Unrecognized differences require
review. Translate a necessary local service customization into a narrow drop-in;
do not discard it just to match the new installation defaults.

## Switch only reviewed configuration

1. Log out normally and continue from the verified TTY. Do not restart or stop
   the display manager from an active graphical session.
2. Move only the reviewed Starch full unit overrides into the backup directory,
   outside systemd's search path. Do not move vendor units under `/usr/lib`.
   Leave custom overrides in place until their behavior has been understood.
3. Confirm the vendor units are present and owned by `cosmic-greeter`, and inspect
   the effective result with `systemctl cat`. Do not blindly apply `systemctl
   revert`, which can discard administrator drop-ins.
4. With no graphical user session active, reload unit definitions and repair
   the alias using `sudo systemctl daemon-reload` and
   `sudo systemctl enable --force cosmic-greeter.service`. Verify that
   `display-manager.service` resolves to the vendor COSMIC unit and that the
   competing display managers remain disabled/masked. These commands do not
   start/restart the display manager; a planned reboot tests the new startup.
5. Keep the custom launcher, TOML and `starch-greetd` unchanged. Do not replace
   the TOML with its vendor version: that would change PAM and keyring behavior.
6. After independent locker and native-polkit verification, move the recognized
   unused lock PAM and GNOME autostart files into the backup. Do not uninstall
   `polkit-gnome` globally: another desktop/user may still need it.
7. Reboot deliberately, then run the acceptance tests below. Preserve the backup
   until reboot, repeated login and a package-upgrade rehearsal all succeed.

## Acceptance and rollback

Test correct and incorrect passwords, faillock/account restrictions, repeated
login/logout, screen lock/unlock and suspend/resume, keyring secrets across login,
polkit authorize/cancel/wrong-password prompts, audio and portals. In the clone,
test daemon startup failure and service recovery, reinstall/upgrade the reviewed
packages, review `.pacnew` files, and repeat authentication tests. The new vendor
`Wants=` dependency permits the greeter unit to proceed if its helper fails,
unlike Starch's former `Requires=`; exercise that failure explicitly.

If startup or authentication fails, use the pre-tested TTY/sudo path. Restore
only the changed files and the exact previous alias/masks from the backup,
including removal of newly created paths that were originally absent. Preserve
unrelated changes made since the backup. Reload systemd and reboot deliberately;
do not force a display-manager restart over an active user session. Restore
PAM/TOML immediately if either was accidentally changed. If TTY login is also
unavailable, boot recovery media, mount the verified installed root, restore
those same reviewed files offline, and reboot. A package downgrade alone will
not restore installer-owned configuration.

Record each step and rehearse both completion and rollback on the clone. Existing
user homes, keyrings, favorites, theme, MIME preferences, rotation settings and
LUU must remain untouched. This procedure is not yet VM-validated.
