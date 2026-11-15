# Lite audio migration and VM acceptance

## What changed

The former installer installed `starch-lite 0.2.2-15`, copied an unowned
`/etc/xdg/autostart/starch-audio.desktop`, and ran Starch's audio supervisor.
Working audio on such a VM did not verify OpenRC user services. The checked-out
source still had that behavior before this change; no VM or ISO identity was
available to establish which image was used.

`starch-lite 0.2.2-16` removes the supervisor, both packaged audio-autostart
templates, and the PAM rewrite helper/hook. The dormant Plasma inner launcher
no longer calls the removed program. Other package preferences/services remain.
The supported Xfce installer no longer copies legacy Plasma session inputs.
Dormant COSMIC/OpenRC code remains outside the supported Lite path and is not
an alternative supported installation profile.

The installer requests Artix's audio user-service packages and seeds:

| User runlevel | Services |
| --- | --- |
| boot | dbus |
| default | pipewire, pipewire-pulse, wireplumber |

The symlinks in `~/.config/rc/runlevels` target `/etc/user/init.d/`. Upstream
services use `supervise-daemon`, with dependency ordering and PipeWire readiness
notification. Artix PAM includes elogind and OpenRC user-session integration.
OpenRC accounts for concurrent PAM sessions and shuts down the user services
when the final relevant session closes; a remaining TTY/SSH login can keep them
running. No system-wide PipeWire service is enabled.

The package builder fingerprints inputs, rebuilds isolated package sources,
checks the real archive identity and rejects retired payloads. Bundle format 3
rejects older bundles. Repeated ISO staging replaces only its generated Lite
bundle directory. Existing historical work directories/ISOs are not retrofitted.
Rebuild an ISO with `./build.sh --build` for a fresh VM test; do not reuse an old
ISO merely because it has the same distribution name.

## Existing installations: preparation

This is a reviewed manual migration, not an automatic package hook. Use a
snapshot/clone first. Do not run these steps on the build host. Do not remove
`starch-lite`, force file overwrites, or enable system-level audio services.

1. Record `pacman -Q`, `pacman -Qqe`, `rc-status -a`, and, as each affected user,
   `rc-status --user -a`. Save the previous `starch-lite` archive and its checksum
   from the original ISO/bundle or installation cache. A package list alone is
   not a rollback archive.
2. Back up `/etc/pam.d`, `/etc/pacman.d/hooks`, `/etc/xdg/autostart`, `/etc/skel`,
   `/etc/rc.conf`, `/etc/rc.conf.d`, `/etc/runlevels` and each affected user's
   `.config/rc` and `.config/autostart`. Preserve ownership, symlinks and modes.
   Keep existing `.pacnew` files and copies of any administrator modifications.
3. Inspect `pacman -Qo /etc/xdg/autostart/starch-audio.desktop` and any matching
   user file. Compare with the old package's template, extracted with `bsdtar
   -xOf OLD_PACKAGE usr/share/starch-lite/xfce-config/autostart/starch-audio.desktop`.
   The old installer copy is normally unowned. A modified or differently owned
   file requires review; do not silently delete it.
4. Search `/etc/xdg/autostart`, `/etc/skel`, each user's `.config/autostart`,
   `.config/rc`, `.xprofile`, `.xinitrc` and saved Xfce sessions for old supervisor
   references or direct audio launchers. Review administrator launchers and
   saved-session entries before selecting exactly one startup mechanism.
5. Obtain the new bundle, verify its SHA256SUMS against the trusted build output,
   and confirm its package version and contents with `bsdtar`. No new repository
   is required. The development package is not automatically trusted by pacman.

## Apply at a controlled session boundary

Finish preparation first, then deliberately log out of the graphical desktop
and use the recovery console. No migration command should terminate a running
graphical session automatically. Retain a root recovery console until reboot.

Before updating PAM, mask the old hook using a same-named `/dev/null` symlink in
`/etc/pacman.d/hooks/95-starch-lite-pam.hook`, **only after checking for and backing
up an existing override**. This prevents an old package hook from rewriting PAM
during the upstream update. Leave a pre-existing administrator override alone
until its purpose is understood.

Install upstream prerequisites as a full upgrade, not a partial upgrade:

```sh
sudo pacman -Syu pipewire-openrc pipewire-pulse-openrc wireplumber-openrc dbus-openrc elogind-openrc
```

Install the verified `starch-lite-0.2.2-16-x86_64.pkg.tar.zst` archive using the
project's trusted package-signing setup, if available. For the unsigned local
development bundle, copy the installed pacman configuration to a private
migration directory and change **only** its `LocalFileSigLevel` to `Optional`.
Invoke `pacman --config /absolute/path/to/that-copy -U /absolute/path/to/the-verified-archive`.
Keep repository `SigLevel` unchanged, pass only that verified archive, and delete
the temporary configuration afterward. Do not relax the installed pacman policy.

Review effective PAM files and `.pacnew` files against the installed Artix
packages. A package update can preserve Starch's old active file while placing
the current upstream file in `.pacnew`. Required session paths are:

- LightDM authentication/account/password/session include `system-login`.
- `system-login` retains upstream authentication/account policy and includes
  `pam_elogind.so`, then the upstream UID guard and `pam_openrc.so` session rule.
- `openrc-user` includes/substacks `system-local-login`, which includes `system-login`.
- LightDM greeter retains its upstream elogind session rule.
- `/usr/lib/security/pam_openrc.so`, `pam_elogind.so`, `/etc/init.d/user` and
  `/usr/lib/openrc/bin/openrc-user` exist; `rc_autostart_user` is not disabled.

Merge only understood differences; never overwrite administrator authentication
policy blindly. Do not invent a new PAM template or strip the UID guard. Test a
second console login before closing the recovery console. If upstream integration
cannot be established, stop the migration and restore the saved state.

As **each intended ordinary user**, in a real login with a valid runtime directory:

```sh
mkdir -p ~/.config/rc/runlevels/boot ~/.config/rc/runlevels/default
rc-update --user add dbus boot
rc-update --user add pipewire default
rc-update --user add pipewire-pulse default
rc-update --user add wireplumber default
```

These commands configure runlevels; they do not prove services started. Do not
run them with sudo or for root/the greeter. Preserve deliberate existing service
settings. Seed equivalent symlinks under `/etc/skel/.config/rc/runlevels` for
future accounts, without overwriting customized skel settings. Each link targets
`/etc/user/init.d/SERVICE`.

Move only verified obsolete Starch audio autostarts to the private backup,
outside XDG autostart directories. Resolve customized or separately owned copies
explicitly. The new package removes its owned helper/templates; it cannot remove
unowned `/etc/xdg` copies or user copies. Remove the temporary hook mask only if
this migration created it and the old packaged hook is now absent. Preserve
administrator overrides. Keep all other Xfce autostarts and Lite settings.

Check that no old supervisor remains after graphical logout. If it survived,
inspect its owner and exact PID/command; do not broadly kill all users' audio.
Use the planned reboot as the final boundary so no old process or inherited lock
can coexist with the new startup path. Reboot manually after all checks above.

## VM acceptance commands

Run these in a terminal **inside the new graphical login**, without sudo unless
shown. The default shell is Fish; enter `bash` for the shell snippets below.

```sh
pacman -Q starch-lite openrc pambase dbus-openrc pipewire-openrc pipewire-pulse-openrc wireplumber-openrc
id
printf '%s\n' "$XDG_RUNTIME_DIR" "$DBUS_SESSION_BUS_ADDRESS"
stat -c '%U %a %n' "$XDG_RUNTIME_DIR"
loginctl list-sessions
rc-status --user -a
rc-service --user dbus status
rc-service --user pipewire status
rc-service --user pipewire-pulse status
rc-service --user wireplumber status
ps -u "$(id -u)" -o pid,ppid,args --forest
pgrep -af '[s]tarch-lite/audio-session'
test ! -e /usr/lib/starch-lite/audio-session
test ! -e /etc/xdg/autostart/starch-audio.desktop
find ~/.config/autostart /etc/skel -name starch-audio.desktop -print
wpctl status
pactl info
pactl list short sinks
pactl list short sources
```

Expected: the runtime directory belongs to the user and has mode 0700; D-Bus
uses `unix:path=$XDG_RUNTIME_DIR/bus`; elogind lists the graphical session; all
four user services report started. There must be no Starch supervisor process,
file or obsolete autostart. PipeWire and WirePlumber must have upstream
`supervise-daemon` parents in the process tree. Pulse compatibility may appear
as `pipewire -c pipewire-pulse.conf`, rather than a process named `pipewire-pulse`.

`rc-status --user` without `-a` generally shows the current runlevel, so a boot
service may not be listed there. Use `-a` and individual `rc-service` status.
Conversely, merely seeing a process does not prove that OpenRC owns it.

Use pavucontrol and an audio application to test playback, input, selected device
and volume. For recovery, find each service's exact child PID in the tree, then
use `kill -KILL PID` as that user, one service at a time. Expect a replacement
PID under the supervisor and restored playback/input. Include PipeWire,
PipeWire-Pulse and WirePlumber. Do not kill the supervisor or use a broad process
name match that could hit multiple services/users. Repeat enough to identify
crash-loop limits; OpenRC may intentionally stop a repeatedly failing service.

Then test logout/login, reboot, Xfce lock/unlock, suspend/resume and multiple
sessions. On final logout check from a different account's recovery console that
services stop; a same-user TTY/SSH session intentionally prevents final logout.
Test upstream package updates and subsequent login again. Hardware testing is
still needed for USB/Bluetooth/HDMI devices, microphones and suspend recovery.

## Rollback

Prefer reverting the tested VM snapshot. For manual rollback, log out first and
use a recovery console. Back up any new user changes. Restore the saved user
runlevels so upstream audio is no longer enabled alongside Starch's launcher.
Reinstall the exact saved previous `starch-lite` archive; keep the temporary PAM
hook mask in place during that transaction so it cannot overwrite reviewed PAM.
Restore saved active PAM, hook overrides and autostart files with their original
ownership/modes, resolving any upstream-version differences deliberately.
Do not downgrade upstream packages individually or recursively remove dependency
packages. Verify console authentication, then reboot manually and verify that
only the restored audio startup mechanism runs. If the original runtime package
set is required, restore the whole snapshot rather than performing a partial
Artix downgrade.

## Verification limits

Source tests exercise package selection, preserved defaults, account seeding,
PAM/service contracts, stale-file rejection and repeated staging. The actual
0.2.2-16 package is built and inspected. An offline extracted target can validate
payload and configuration, but cannot establish PAM login, audio recovery or
logout reliability. The developer host and the user's VM are not migrated by
this source change; fresh-VM acceptance remains outstanding.

## Implementation file inventory and verification record

Paths below are relative to the source repository. Existing COSMIC implementation
changes were preserved; the only additional change to its test file is removal
of an expectation that the retired Lite audio template remain packaged.

| Changed source | Responsibility |
| --- | --- |
| `packages/starch-lite/integration/PKGBUILD` | Release 16; upstream service dependencies; removes helper-only Python/procps dependency requests. |
| `packages/starch-lite/integration/root/usr/lib/starch-lite/audio-session` | Deleted custom supervisor. |
| `packages/starch-lite/integration/root/usr/lib/starch-lite/configure-pam` | Deleted PAM rewrite helper. |
| `packages/starch-lite/integration/root/usr/share/libalpm/hooks/95-starch-lite-pam.hook` | Deleted update-time PAM rewrite. |
| `packages/starch-lite/integration/root/usr/share/starch-lite/legacy-desktop-config/autostart/starch-audio.desktop` | Deleted legacy audio autostart template. |
| `packages/starch-lite/integration/root/usr/share/starch-lite/xfce-config/autostart/starch-audio.desktop` | Deleted supported audio autostart template. |
| `packages/starch-lite/integration/root/usr/lib/starch-lite/plasma-session-inner` | Removes dangling supervisor invocation from dormant Lite compatibility launcher. |
| `scripts/installer/profiles.py` | Lite-only service selection; format-3 bundle and actual archive identity/payload validation. |
| `scripts/installer/bootstrap.py` | Seeds upstream user runlevels before account creation. |
| `scripts/installer/lite.py` | Seeds/validates user services and active PAM; rejects old/competing launchers; stops copying legacy inputs into Xfce; removes PAM mutation. |
| `scripts/installer/validate.py` | Checks the created user's runlevels, ownership and startup configuration. |
| `scripts/build/starch-lite.sh` | Fingerprints archive validator, validates builds and reuse, emits bundle format 3. |
| `scripts/build/stage-installer.py` | Replaces the generated Lite bundle directory on repeated staging, including disabling Lite. |
| `tests/unit/test_lite_audio.py` | New upstream PAM/service, ownership, competing startup, archive and preserved-payload regression tests. |
| `tests/unit/test_starch_lite.py` | Removes obsolete supervisor implementation tests; uses archive fixtures; checks absence and repeated staging. |
| `tests/unit/test_cosmic.py` | Adjusts only the legacy-Lite preference snapshot for the removed audio template. |
| `tests/fixtures/installation-profiles.json` | Adds the three audio-service roots to Lite only. |
| `tests/fixtures/lite-artix-user-services/` | New upstream fixtures; `packages.json` lists every extracted path, exact archive identity, hash, dependencies and licenses; README/license files retain provenance. |
| `docs/starch-lite.md` | Current user-service architecture and migration link. |
| `docs/starch-lite-audio-migration.md` | Migration, rollback, acceptance commands and this record. |
| `docs/third-party-provenance.tsv` | Adds upstream fixture provenance. |
| `AGENTS.md` | Records bundle format/version review and upstream audio invariants. |

Verification performed:

- Full unit suite: **108 tests passed**.
- Python syntax compilation, relevant Bash/PKGBUILD syntax, `git diff --check`:
  passed.
- `./build.sh --check`: passed.
- Isolated Lite package build and subsequent `--ensure` verified reuse: passed.
- Actual package inspected; retired audio/PAM files absent and remaining banner,
  zram and defaults helpers executable.
- Actual package extracted to a temporary target; installer configure/default
  setup, copied account runlevels and repeated actual-bundle staging passed.
  Chroot actions in that offline check were mocked; no installed OS was booted.
- A historical `0.2.2-15` staged package was inspected and confirmed to contain
  the old supervisor/autostarts; the new archive validator rejected it.
- Captured upstream archive hashes were checked against repository metadata.

Final package:
`build/starch-lite/artix-repo/starch-lite-0.2.2-16-x86_64.pkg.tar.zst`

SHA-256:
`d2adbbdd69b53e02f7dff886981969be0132a7e64d22e5653489b02a39150662`

No new ISO was built and no running host/VM was migrated. Fresh-VM acceptance,
including audio recovery, locking and session cleanup, remains required.

### Follow-up: OpenRC file validation

The initial audio validator incorrectly included `openrc` in a blanket
`pacman -Qk` check. Lite intentionally removes the package's default getty
runlevel links, so that command returns exit 1 even for the intended target.
The audio package check now excludes `openrc`; the existing
`validate_openrc_files()` still checks all its other paths and permits only the
intentional getty-link removals. A regression test reproduces pacman's exit 1
using a temporary database and verifies the corrected validation path.
The reported VM failure still requires its installer log to confirm this was
the particular failing command. Existing ISOs require rebuilding for this fix.
