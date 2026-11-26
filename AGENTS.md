# Agent guide for Starch Linux

This file is the working guide for coding agents in the Starch Linux source
repository. Read it before changing code, packaging, installer behavior, build
tooling, desktop defaults, or documentation. Paths and commands below are
relative to this repository's root unless explicitly stated otherwise.

Keep this guide accurate when changing the workflows or invariants it describes.
It documents the implementation inspected on 2026-11-14; version numbers here
are repository baselines, not claims about the latest upstream releases.

## 1. Scope, instructions, and working assumptions

- This checkout is `starch-linux`. Its parent may contain a separate
  `dev-private-starch` checkout with development notes. They are separate Git
  repositories, not source subdirectories or submodules of one project.
- Apply this guide throughout this repository. Read any more specific
  `AGENTS.md` in a directory before editing files there.
- Follow applicable higher-priority instructions and the user's current task.
  This guide does not authorize unrelated changes, host administration, disk
  erasure, publication, or disclosure of private material.
- Work autonomously on authorized, reversible implementation and verification.
  Resolve ordinary implementation choices from the code and task context.
- Preserve unrelated work. Inspect the working tree before editing; do not
  discard, reset, stash, or rewrite someone else's changes to simplify a task.
- Do not assume a clean working tree means generated outputs are current.
  Build caches, local inputs, and ISO artifacts are Git-ignored.
- Do not add a second agent guide with different capitalization. Maintain this
  canonical `AGENTS.md` rather than creating competing instructions.

### Establish context at the start

From the source checkout:

```sh
pwd
git rev-parse --show-toplevel
git status --short
rg --files --hidden -g AGENTS.md -g '!build/**' -g '!starch-out/**' -g '!.git/**'
```

Read `README.md`, the relevant documents in `docs/`, the implementation being
changed, and its tests. Use `rg` for focused searches. Include `--hidden` when
looking for desktop defaults under `.config`, `.local`, or similar directories.
Avoid broad recursive reads of generated chroots, caches, and binary artifacts.

### Resolve conflicting evidence carefully

For current behavior, inspect executable code, configuration, and tests together.
Use `docs/decisions.md` and `docs/installation-profiles.md` for the documented
product boundary. When they disagree, identify the discrepancy and make the
smallest task-relevant correction; do not silently broaden supported behavior.

Historical plans and validation reports are context. The current installer
automatically installs the canonical COSMIC configuration.

## 2. Product and platform contract

Starch Linux is an x86_64 Linux distribution built with Archiso. One live ISO
provides a graphical, online, erase-disk installer using Calamares.

| Environment | Desktop and login | Kernel | Init | Repositories |
| --- | --- | --- | --- | --- |
| Live ISO | COSMIC Wayland / automatic live-user login through greetd | `linux` | systemd | Arch plus the staged local installer package |
| Installed system | COSMIC Wayland / authenticated COSMIC Greeter through greetd | `linux-lts` | systemd | Arch |

Shared installed-system behavior includes ext4, Limine, zram, NetworkManager,
PipeWire, Flatpak/Flathub, and Linux Update Utility. Fish is the standard user's
default shell. Flatpak applications are not preinstalled merely because Flathub
is configured.

Preserve these boundaries unless the task explicitly changes them:

- Preflight downloads fresh target packages before erasure. `pacstrap` installs
  from the retained signed package transaction.
- Installation erases the selected whole disk. There is no supported manual
  partitioning, install-alongside, or dual-boot workflow.
- UEFI and legacy BIOS are supported installation modes. Secure Boot is not a
  supported workflow.
- Full-disk encryption, offline installation, hibernation, snapshot rollback,
  ARM images, and 32-bit images are outside the documented scope.
- Starch does not stage upstream Arch updates or promise automatic rollback.
- Starch-owned bundled utilities and configuration have no dedicated update
  channel for existing installations. Rebuilding an ISO changes future installs.

## 3. Repository map and source ownership

| Path | Responsibility and editing guidance |
| --- | --- |
| `README.md` | Concise public overview and entry points. |
| `build.sh` | Build preconditions, package preparation, snapshot staging, Archiso invocation, artifact collection, and built-filesystem validation. |
| `clean.sh` | Restricted cleanup of named generated directories. |
| `scripts/build/paths.sh` | Shared generated-path containment checks. |
| `archiso/profile/profiledef.sh` | Archiso metadata, boot modes, and file permissions. |
| `archiso/profile/packages.x86_64` | Live-image packages, distinct from target packages. |
| `archiso/profile/pacman.conf` | Live-image build repository configuration. |
| `archiso/profile/airootfs/` | Files and defaults installed into the live root. |
| `archiso/profile/{efiboot,grub,syslinux}/` | Live-media boot configuration; separate from installed Limine configuration. |
| `calamares/settings.conf` | Installer page sequence and execution job order. |
| `calamares/modules/` | Module configuration, including erase-disk and display-manager behavior. |
| `calamares/branding/starch/` | Installer branding, content, artwork, and stylesheet. |
| `calamares/pacman.conf` | Standard target repository configuration. |
| `manifests/minimal-packages.txt` | Canonical installed package requests. |
| `scripts/installer/` | Starch installer stages, validation and COSMIC target configuration. |
| `scripts/build/stage-installer.py` | Copies maintained sources into a generated profile and assembles target overlays. |
| `scripts/build/calamares*.sh` | Isolated Calamares package construction and chroot operations. |
| `packages/calamares/` | Pinned PKGBUILD and Starch patches to upstream Calamares. |
| `packages/starch-cosmic/root/` | Supported COSMIC target overlay and account defaults. |
| `packages/starch-rotation/root/` | Session rotation helper, autostart, and lock launcher. |
| `packages/linux-update-utility/` | Starch desktop integration for a separately supplied AppImage. |
| `fastfetch-text` | Maintained root artwork; staging refreshes the live copy from this file. |
| `wallpapers/` | Wallpaper source inputs and packaging guidance. |
| `scripts/validate/` | Schema checks, Calamares launch smoke test, and built-live filesystem checks. |
| `tests/unit/` | Python `unittest` suite using fixtures, temporary trees, and mocked system boundaries. |
| `tests/fixtures/installation-profiles.json` | Original COSMIC package request fixture. |
| `tests/calamares/` | Native Qt Additional Software test and its build instructions. |
| `tests/integration/rotation-dbus.py` | Rotation integration on a private D-Bus instance. |
| `scripts/collect-inventory.sh` | Host inventory collection; inspect scope and generated output before sharing it. |
| `docs/` | Public behavior, supported scope, and licensing documentation. |
| `docs/third-party/` | Recorded upstream notices and baseline material. |
| `docs/third-party-provenance.tsv` | Third-party source, revision, licensing, modifications, and review records. |

### Generated and local-only paths

`build/`, `starch-out/`, `luu-input/`, `starch-branding/`, Python caches, and local
agent configuration are ignored. Keep generated packages, downloaded archives,
mounted roots, ISO files, inventory, logs, and caches out of tracked source.

The principal generated locations are:

- `build/work/run-*`: fresh per-build snapshots and Archiso work trees.
- `build/cache/`: reusable package downloads.
- `build/logs/run-*.log`: main ISO build logs.
- `build/calamares/chroot/`: isolated installer package build/test root.
- `build/calamares/cosmic-repo/`: installer package, repository database, checksums,
  source archive, notices, and dependency records.
- `build/calamares/smoke.log`: installer launch smoke-test output.
- `starch-out/run-*`: normal build output and accompanying reports.

Edit maintained source, not files inside these generated trees. A change made
only in a staged profile or chroot will disappear on rebuild and will not be
reviewable as a source change.

## 4. Installer architecture and execution order

`calamares/settings.conf` is the authority for execution order. The current
visible pages are welcome, locale, keyboard, partition, users,
`starchsoftware` (Additional Software), and summary.

The execution sequence is:

1. `starch-preflight`
2. `partition`
3. `mount`
4. `starch-bootstrap`
5. `machineid`
6. `fstab`
7. `locale`
8. `keyboard`
9. `localecfg`
10. `users`
11. `starch-configure`
12. `starch-limine`
13. `starch-validate`
14. `starchsoftware` (optional software; warning-only failures)
15. `umount`

The Additional Software page preserves raw entries in `starchSoftware_pacman`
and `starchSoftware_flathub`; its native job deduplicates requests and shows
separate progress with elapsed time and live package output. Results require
Continue even on success; each install is verified and its outcome logged.
Skip waits for the active transaction, then drops pending requests. Optional failures are warnings and never fail the OS job queue.
`additional.py` reuses mounted-target checks and requires the
`starchEssentialComplete` flag set only at the end of validation. Nothing is
scheduled for boot/login.

The finished page follows execution. Preserve dependencies between stages;
particularly, defaults intended for a new user's home must reach `/etc/skel`
before `users` creates the account.

### Python responsibilities

| Module | Responsibility |
| --- | --- |
| `runtime.py` | Live-environment guard, checked subprocesses, disk identity, mounted-target validation, writes, log preservation, and stage error reporting. |
| `profiles.py` | Canonical target identity and kernel, stale desktop-state guard, and COSMIC dependency audit. |
| `preflight.py` | Validate selection and erase mode, inspect/deactivate selected-disk consumers, resolve and retain signed packages, recheck the disk, and save the resolved selection. |
| `bootstrap.py` | Check saved identity, run bounded `pacstrap` retries, and seed overlays before account creation. |
| `configure.py` | Configure the installed system and enable COSMIC login. |
| `cosmic.py` | COSMIC login/session/default configuration and validation. |
| `graphics.py` | Display-device identification and kernel-aware graphics package selection. |
| `media_defaults.py` | Media MIME defaults and their validation. |
| `limine.py` | Initial installed-system bootloader deployment and maintenance enrollment. |
| `limine_update.py` | Later validation and refresh of installed Limine loader files/stages. |
| `validate.py` | Final installed-target checks and essential-completion gate. |
| `additional.py` | One validated optional pacman/Flathub transaction in the mounted target; called by the native `starchsoftware` job after validation. |

Staging creates the Calamares Python job wrappers. Change their generator in
`stage-installer.py`, not a wrapper found in a built image.

## 5. Disk and target safety invariants

These checks protect real disks. A build or test failure is not a reason to
disable them. Changes to this boundary require meaningful negative-case tests.

### Live and mounted-root identity

- Mutating installer stages require root and the `/etc/starch-live` marker.
  Do not create that marker on the development host to force a stage to run.
- The selected target comes from Calamares state, never from a guessed host
  device, the first `lsblk` entry, or the disk containing the checkout.
- The selected path must resolve to a block device and the intended whole disk.
- The installation root must be a separate mount directly under `/tmp` with a
  `calamares-root-` name, not a symlink, host `/`, or an ordinary directory.
- Saved profile and disk identity must match the current Calamares selection.
- Root must be exactly the expected ext4 partition on that disk. Compare the
  mounted filesystem's `MAJ:MIN` with the selected partition's identity.
- UEFI requires the expected FAT32 partition mounted at `/boot/efi`; BIOS
  requires the expected FAT32 filesystem mounted at `/boot`. Both must belong
  to the selected disk and match the actual mount identity.

### Disk preparation and failure behavior

- Preserve the writable whole-disk and minimum-size checks. Current disk
  preparation requires at least 21 GiB; the separate build-space check is 20 GiB.
- Reject the disk containing the running live system, including protected live
  mounts. Do not relax this because a particular fixture has a simpler layout.
- Inspect inverse dependencies for mapped, RAID, and LVM consumers before
  changing anything. Reject consumers with shared or unidentified backing disks.
- Gather and validate relevant topology before unmounting or deactivating
  consumers. An inspection failure must not trigger partial teardown.
- Deactivate only consumers belonging exclusively to the selected disk, with
  deeper mounts/consumers handled before their backing devices.
- Keep explicit JSON tree queries and handle repeated nodes or multiple roots.
  Device enumeration order is not identity.
- Recheck disk state after network/package resolution and before partition jobs.
- Preflight can unmount and deactivate storage. Treat it as mutating even though
  it runs before partitioning; never use it as a casual host diagnostic.
- Reject stale desktop selections before touching the disk. Require the
  expected mounted-target identity before mutating the target.

### Subprocesses, files, and diagnostics

Use argument arrays and existing command helpers rather than shell interpolation
of device paths or user input. Keep timeouts and process-group cleanup for
commands that may hang. Propagate nonzero exits rather than continuing with an
incomplete target.

Preserve target-aware path handling and the symlink protection in `put()`.
Review both final path and parent-directory assumptions when adding writes.
Do not redirect target configuration operations to the host's `/etc` or `/boot`.

Installer runtime paths are `/usr/share/starch-installer` for staged data,
`/run/starch-installer` for transient state, and `/var/log/starch-installer.log`
for the main log. Preserved target logs live in `/var/log/starch-installer/`.
Keep restricted log permissions and avoid recording passwords, complete global
storage, or password-bearing subprocess arguments. Escape errors displayed as
HTML. Failure must not be presented as installation success.

## 6. Packages, repositories, and signing

The installer installs COSMIC automatically and retains `standard-cosmic` in
its logs. Stale desktop selection state must be rejected before disk operations.

Keep live requests in `archiso/profile/packages.x86_64` and target requests in
`manifests/minimal-packages.txt`. The manifest parser rejects duplicates, empty
manifests, options, and invalid package names. Use official Arch repositories
for both builds and installations. The live build also stages the local
Calamares package.

`profiles.py` audits the resolved COSMIC dependency closure for both
environments and pins specified components to upstream version `1.11.0`.
Arch greeter and OSD additionally require the reviewed package releases. Review
defaults, startup, greeter/locking, portals, keyboard, and display command
formats before accepting new COSMIC releases. Qt Virtual Keyboard and kdialog's
KWallet dependency are allowed on the live ISO for Calamares.

Graphics selection remains based on display hardware and the target kernel.
Preserve unknown-vendor handling, hybrid GPU support, unsupported NVIDIA ID
fallbacks, and vendor-based CPU microcode selection.

## 7. Live image, overlays, and account defaults

The live filesystem contains conveniences that must not leak into installed
systems: its user account, sudo policy, autologin, power behavior, network
state, and build-only hooks. Preserve the explicit staging allowlist and the
distinction between shared target and desktop-specific overlays.

`stage-installer.py` stages the COSMIC skeleton, wallpapers, and rotation helper
into both the live root and target overlays. The live package hook runs after
installation and creates the live user from `/etc/skel`. Target bootstrap seeds
the target skeleton before the Calamares users job. Both roots generate media
defaults with `media_defaults.py` after package installation.

When changing a default:

1. Identify whether it belongs to the live session, the installed system, both environments, or a new user's home.
2. Edit the maintained source for that scope.
3. Check which roots receive it during staging and bootstrap.
4. Check required permissions in `profiledef.sh`, package installation, and
   bootstrap. Archiso can normalize nested overlay modes.
5. Check that account defaults are seeded before the account is created.
6. Check that later login does not overwrite the user's own settings.
7. Describe existing-installation effects accurately; new `/etc/skel` defaults
   do not retrofit existing homes.

Use `configure.py` for installed OS identity and
`archiso/profile/airootfs/etc/os-release` for live identity. Review both when
changing distribution naming or release information.

### Installer launch

The live installer launcher is
`archiso/profile/airootfs/usr/local/bin/starch-install`. It launches elevated
Calamares through the live Wayland socket using Qt's Wayland backend and a
private root-owned runtime directory.

The launcher offers standard keyboard mode by default and an optional
on-screen-keyboard mode for installer fields. Keep that choice scoped to the
installer. The installed system must require authenticated login.

### COSMIC

The live image adds a greetd initial session for `liveuser`. The target uses the
same greeter launcher and PAM policy with authenticated login.

COSMIC LTS uses Arch's vendor greeter units, with no full `/etc` replacements or
Starch service drop-ins. Keep the custom greeter launcher provisionally until its
bus/environment equivalence is tested; retain scoped `starch-greetd` PAM/keyring
integration. The reviewed Arch greeter 1:1.11.0-1 selects `login` for locking via
its packaging revert. COSMIC OSD supplies polkit.
Arch greeter/OSD package releases are audited exactly before fresh installation.
Do not turn installer configuration into an installed-system migration. See
`docs/cosmic.md` and the reversible procedure in `docs/cosmic-migration.md`.


The on-screen keyboard uses manual activation. Its default is the `false` value
at `/etc/skel/.local/state/cosmic/com.system76.CosmicOSK/v1/ime_activation`.
This is a state path, not a `.config` path. Validate that it reaches the created
user's home and preserve subsequent user changes.

### Rotation

Both environments ship Starch's session helper and `cosmic-randr`.

Preserve active/unlocked-session checks, sensor claim/release, discovery retry,
debouncing, internal-panel selection, dock/mirror/ambiguous-layout exclusion,
mode/refresh preservation, persistent rotation lock, and clean shutdown.
Do not activate dormant Xfce paths merely because helper tests exercise them.
See `docs/rotation.md` for the private-bus test and hardware acceptance steps.

## 8. Bootloader and boot presentation

Installed systems use Limine. The live ISO's GRUB/Syslinux/EFI files serve a
different boot path; changing one does not automatically change the other.

- UEFI targets use the profile's unified kernel image under `EFI/Linux` and
  Limine deployment under both the normal and fallback EFI locations.
- BIOS targets use a GPT BIOS boot partition, a mounted FAT32 `/boot`, separate
  kernel/initramfs files, and the matching kernel arguments.
- Keep Linux LTS and Linux Zen filenames consistent across package selection,
  initramfs/UKI construction, boot configuration, and final validation.
- UEFI splash and BIOS Plymouth behavior are separate implementations. Do not
  assume a splash change tested in one firmware mode covers the other.

The installer enrolls maintenance identity in `/etc/starch/limine.json` and
installs pre/post pacman hooks for the Limine updater. Maintenance must validate
the intended mounted boot filesystem and enrolled identities before writing.
BIOS maintenance additionally validates disk PTUUID, boot partition PARTUUID,
and a unique valid BIOS boot partition, then refreshes embedded stages and the
loader file. Device names may change; identity checks must survive that change.

Maintenance refreshes loader files/stages only. Preserve boot menus, kernels,
initramfs, UKIs, and kernel options. Fail on duplicate identities, missing
sources, unexpected mounts, mapped storage, or ambiguous layout. Do not run
enrollment or deployment against the development host as a validation shortcut.
See `docs/limine-maintenance.md` and `test_release_fixes.py`.

## 9. Build prerequisites and supported commands

Run build commands from this repository. Read the scripts before adding flags:
these are small custom entry points, not generic package-manager interfaces.

### Prerequisites and check modes

```sh
./build.sh --check
scripts/build/calamares.sh --check
```

The top-level check requires Archiso/pacman tooling, Python, checksum/logging
utilities, valid source inputs, safe generated paths, and at least 20 GiB free.
The Calamares package build has additional tool checks, including chroot/bootstrap
and namespace tooling. A successful top-level check is not a successful package
build, ISO build, boot test, or installation test.

For a complete ISO build, `luu-input/` must contain exactly one `*.AppImage` and
one `*.svg`, both regular non-symlink files. `wallpapers/` must be a real
directory. Do not download an arbitrary substitute or fabricate a binary to
make these checks pass.

Rootless builds use subordinate UID/GID mappings and
`unshare --map-auto --map-root-user`. Diagnose unavailable mappings or namespace
restrictions rather than silently changing host configuration or running an
entire build with unrestricted privileges. Use the repository's isolated Arch
build roots instead of installing build dependencies into the host ad hoc.

### Build modes

```sh
./build.sh --build
```

This prepares/reuses verified Calamares package output, creates a fresh
run directory, stages a copied profile, invokes Archiso, validates the built
filesystem, and emits the ISO with reports under `starch-out/run-*`.

```sh
./build.sh --compile
```

This also performs the ISO build. It keeps accompanying artifacts under that
run's `build/work/run-*/artifacts/` and places the ISO directly in `starch-out/`
with the run ID in its name. It is not a syntax-only or package-only check.
The final move uses a hard link; source and destination must support it.

For package-specific work:

```sh
scripts/build/calamares.sh --build
```

The package script also supports `--ensure`, which reuses output only when input
fingerprints and output checksums pass. Prefer these mechanisms over manually
editing cached output or deleting the entire build tree.

### Snapshot and artifact expectations

Fresh run directories avoid stale Archiso run-once markers. The build copies
profile and local asset inputs before invoking staging. Do not edit an active
run's snapshot to inject a fix, and do not assume arbitrary edits to other
repository sources during a build are included. Record the source revision and
working-tree changes associated with a result.

Normal outputs include the ISO, `SHA256SUMS`, `build-report.txt`, requested/live
package records, `profile-source.tar.gz`, `starch-installer-source.tar.gz`, and
Calamares source and notice artifacts. Preserve accompanying reports when
evaluating or handing off an ISO. `--compile` publishes the ISO and its matching
`.iso.sha256` file together in `starch-out/`. It leaves reports in its work run,
so cleaning that run also removes those reports.

The build report explicitly distinguishes filesystem validation from VM boot.
Retain that distinction in status reports and release claims.

### Cleanup

```sh
./clean.sh --dry-run work
./clean.sh work
```

Supported cleanup names are `work`, `cache`, `logs`, and `inventory`; multiple
names may be supplied. Inspect the dry-run and avoid deleting active build work
or evidence still needed for diagnosis. Use `sudo ./clean.sh work` only when
ownership makes elevation necessary and the deletion is within the task scope.

Keep validation of the entire cleanup request before any deletion. Preserve
rejection of unsupported names, symlink roots/targets, non-directories, and
mounted targets, plus filesystem containment during deletion. The script does
not clean `starch-out`, `build/calamares`, ; do not invent
unsupported cleanup arguments or replace it with broad recursive deletion.

## 10. Calamares packaging and upstream changes

The current package baseline is Calamares `3.3.14`, built with Qt 6 and a reduced
module set. The source's bundled pybind11 is replaced with the Arch build
dependency for the package's Python toolchain. Preserve the isolated official
Arch build configuration and the pinned upstream archive checksum.

Starch patches cover erase-only partitioning, OS-prober avoidance, live-only
autologin policy, installer presentation, and optional software. When changing
a patch:

1. Inspect its current upstream context and the corresponding tests.
2. Keep the patch narrowly scoped and readable against the pinned source.
3. Update the matching checksum in `packages/calamares/PKGBUILD`.
4. Update package release metadata when the resulting package changes.
5. Build through `scripts/build/calamares.sh` and inspect failures in the
   isolated build root/logs.
6. Run schema, launch, and native selection checks as appropriate.
7. Update provenance/notices if the source or borrowed implementation changes.

Do not fix a checksum mismatch by replacing an integrity check with `SKIP`.
Do not re-enable unused upstream modules to hide a configuration mismatch.
Content-only installer news and presentation changes generally belong in
`calamares/branding/starch/`; inspect the consuming patch before changing C++.

## 11. Validation strategy and executable checks

Choose checks according to the changed behavior and its consequences. There is
no reason to build an ISO for a documentation-only edit. Installer/storage,
package-selection, boot, and privilege-boundary changes need regression coverage
that tests outcomes and failure paths rather than only matching source strings.

### Local syntax and unit checks

```sh
bash -n build.sh clean.sh scripts/build/*.sh scripts/validate/calamares-smoke.sh
python3 -m unittest discover -s tests/unit -v
```

Use targeted discovery while iterating:

```sh
python3 -m unittest discover -s tests/unit -p 'test_installer.py' -v
python3 -m unittest discover -s tests/unit -p 'test_desktop_selection.py' -v
python3 -m unittest discover -s tests/unit -p 'test_release_fixes.py' -v
```

Run ShellCheck on modified Bash scripts when available and applicable. Extensionless
shell helpers require their own syntax checks with the interpreter identified by
their shebang. Some tests conditionally require tools such as `pacman-conf` or
offline `systemctl`; report skips and missing prerequisites accurately.

| Test file | Primary concerns |
| --- | --- |
| `test_scaffold.py` | Build/cleanup containment, explicit actions, path handling, and private-checkout isolation. |
| `test_live_profile.py` | Live packages, users, desktop defaults, and image configuration. |
| `test_installer.py` | Installer safety, target identity, staging, configuration, package bootstrap, and validation. |
| `test_desktop_selection.py` | Supported profile identities, selection validation, package isolation, and fixtures. |
| `test_cosmic.py` | COSMIC target configuration, defaults, overlays, media behavior, and isolation. |
| `test_rotation.py` | Display parsing, orientation behavior, mode preservation, and profile isolation. |
| `test_release_fixes.py` | Shared storage, BIOS mount safety, graphics selection, and Limine maintenance. |

Use temporary roots and mocked subprocess/system boundaries. Never turn a unit
test into a real host partition, service, package, or bootloader operation.
Useful negative cases include malformed state, changed disk identity, missing
mounts, symlink inputs, stale desktop selections, dependency drift,
network failure, command timeout, and failure before the first write.

### Calamares configuration schemas

The validator needs Python `yaml`/PyYAML and `jsonschema`, plus an extracted
pinned Calamares source tree containing the Starch module/schema patches:

```sh
python3 scripts/validate/calamares-config.py /path/to/patched/calamares-3.3.14
```

Replace the placeholder with the actual source tree. An untouched upstream
archive lacks Starch's custom module schema. The validator contains a deliberate
narrow exception for `defaultPartitionTableType`, consumed by upstream code but
absent from its schema; preserve the source check supporting that exception.

### Installer launch and Additional Software

After building the package:

```sh
bash scripts/validate/calamares-smoke.sh
```

This stages configuration, installs the package into the isolated Calamares
chroot, and launches the GUI offscreen. It does not execute installation jobs,
but it does modify generated chroot state. The timeout status indicates that
the GUI remained open; inspect `build/calamares/smoke.log` for module errors.
On the booted ISO, run `/usr/local/lib/starch/smoke-installer` from a liveuser terminal to verify the real Wayland launcher, both keyboard modes, and password input. Cancel both sessions before applying any disk changes.
A successful launch does not prove a successful installation.

For native Additional Software validation, follow `tests/calamares/README.md`.

### Built live filesystem and rotation integration

`build.sh` invokes `scripts/validate/built-live.py` against the assembled
`airootfs`, within the appropriate namespace for a rootless build. This checks
files, permissions, service links, desktop defaults, installer artifacts, and
patch presence without executing the image. It is not a VM boot test.

For rotation changes:

```sh
python3 tests/integration/rotation-dbus.py
```

This requires PyGObject, `dbus-daemon`, and permission to bind a temporary Unix
socket. It uses a private bus and substitutes display operations. A sandbox or
dependency failure is a blocked check, not evidence of a rotation regression
or a passing integration test.

### VM and hardware acceptance

For changes affecting installation or boot, test both firmware
modes on disposable VM disks. Exercise the relevant cases rather than claiming
coverage from a single successful default installation:

- BIOS and UEFI live boot, installer launch, installation, and installed reboot.
- Back navigation, Additional Software, and Summary.
- Disk selection with multiple disks; verify an unselected disk is untouched.
- Network loss, failed downloads, signature failures, and safe failure messages.
- Correct kernel/init/display manager and absence of incompatible desktop state.
- Account creation, authenticated login, screen locking, logout, and reboot.
- Network, audio, portals, Flatpak configuration, and update-utility launch.
- Keyboard mode and desktop on-screen-keyboard behavior where affected.
- Bootloader maintenance through the relevant update hooks and failure cases.

Physical hardware remains necessary for GPU behavior, touch mapping, sensors,
rotation, suspend/resume, and device-specific audio/networking. Report tested
hardware and actual observations. Do not convert an untested feature into a
support claim or describe static checks as end-to-end verification.

## 12. Assets, Linux Update Utility, and licensing

Linux Update Utility is a separately built AppImage. Starch supplies the desktop
entry and staging/integration. Its staged paths include:

- `/usr/local/bin/linux-update-utility.AppImage`, executable mode `0755`.
- `/usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg`, mode `0644`.
- `/usr/share/applications/linux-update-utility.desktop`, mode `0644`.

Preserve both live and target delivery. The COSMIC dock uses the bundled
desktop entry. Wallpaper inputs are copied to `/usr/share/backgrounds/starch`;
see `wallpapers/README.md` for supported formats and the Evergreen default.

Original Starch software is GPL-3.0-or-later. The root `fastfetch-text` artwork
and its maintained live copy are CC0-1.0. Third-party material keeps its own
license, and the Starch name/branding has separate restrictions in `NOTICE.md`.

When introducing or updating third-party material, record destination, source
URL, exact revision/version, author/rightsholder, license, notices, modifications,
and review status in `docs/third-party-provenance.tsv`. Preserve required notices
and source materials. Do not treat package license metadata alone as complete
redistribution review.

Local Git-ignored AppImages, artwork, firmware, and other bundled inputs still
need release provenance and redistribution review. Unknown rights are not
resolved by keeping the inputs out of Git. Follow `docs/licensing.md`; do not
claim a successful build establishes release compliance.

## 13. Implementation and documentation conventions

- Follow the surrounding language, formatting, and architecture. The main
  implementation uses Bash, Python, package recipes, declarative desktop/system
  configuration, and patches to upstream C++; do not add a framework without a
  concrete need.
- Keep Python helpers small, target-aware, and testable with temporary paths.
  Reuse `runtime.py` and profile helpers rather than duplicating safety logic.
- Keep Bash quoting, strict error handling, command arrays, and path containment.
  Handle spaces in checkout paths; existing tests deliberately exercise them.
- Add comments for invariants, ordering, upstream exceptions, and failure
  boundaries. Avoid comments that merely restate the next statement.
- Preserve executable bits, symlink targets, configuration syntax, and ownership
  assumptions. Text correctness alone is insufficient for image contents.
- Avoid broad formatting churn, unrelated refactors, and generated-file edits.
- Fix a defect at its maintained source and adjust the relevant validator/test
  when the intended contract changes. Do not weaken assertions to hide a defect.
- Add regression tests for meaningful behavior changes; do not invent tests for
  prose-only edits or reversible low-impact changes that need only inspection.
- Keep public docs concise and user-oriented. Put durable agent workflow details
  here; do not dump logs, private planning, or task transcripts into public docs.
- If private notes are available, use them for context without copying private
  content into tracked files. This guide must remain usable without that sibling
  checkout.
- Consult primary upstream sources when external API/version behavior needs
  verification. Record the relevant version rather than relying on “latest.”

### Common change paths

| Task | Review together |
| --- | --- |
| Add/remove an installed app | Manifest, resolved dependencies, launcher/MIME defaults, and relevant target tests. |
| Change the live desktop | Live packages, `airootfs` defaults, permissions, staging allowlist, and built-live validation. |
| Change a package source | Pacman configs, keyring handling, preflight resolution, and provenance. |
| Change installer copy/artwork | Branding files, consuming presentation patch, asset staging, and launch/UI inspection. |
| Change boot behavior | Profile kernel, configuration/initramfs generation, Limine setup/maintenance, final validation, BIOS/UEFI tests. |
| Change a desktop default | Overlay source, staging isolation, `/etc/skel` timing, created-home validation, and existing-user preservation. |
| Change a shell service/helper | Interpreter syntax, mode, startup ordering, error/timeout behavior, cleanup, and matching init/session path. |
| Change build or cleanup | Path validation, namespace boundaries, cache fingerprints, artifact locations, and scaffold safety tests. |

## 14. Troubleshooting without losing evidence

Start with the earliest failing stage and its actual error. Preserve the run ID,
command, source changes, relevant log, and artifact paths before cleanup.

| Symptom | First investigation |
| --- | --- |
| `build.sh --check` fails | Missing tools, free space, local LUU inputs, profile presence, and rejected generated paths. |
| Generated directory is unwritable | Ownership and prior elevated builds; use scoped cleanup after preserving needed evidence. |
| Rootless namespace fails | Subordinate mappings and environment restrictions; do not bypass installer safety or alter the host silently. |
| Calamares build fails | Pinned-source/patch checksums, patch context, pybind11/toolchain compatibility, and isolated package logs. |
| Installer page/module fails to load | Staged settings, built module set, matching schema, plugin linkage, and smoke log. |
| COSMIC preflight rejects packages | Actual resolved transaction, forbidden/missing packages, and audited component versions. |
| Pacstrap fails | Network/mirror/signature error and selected repository/keyring; retain bounded retry behavior. |
| Installed system will not boot | Firmware mode, actual mounted boot filesystem, selected kernel artifacts, Limine config, and enrolled identities. |
| A default is absent for a new user | Correct overlay, copy order before `users`, final path, and file permissions. |
| An existing user keeps old defaults | Per-user persisted/copied configuration; distinguish new-install defaults from migration. |
| Rotation does nothing | Supported profile, active/unlocked session, sensor claim, panel topology, lock state, and parser output. |

Inspect a small relevant log excerpt rather than dumping entire logs or inventory.
Redact secrets if encountered. Do not remove failed output, suppress validation,
change trust policy, or reuse a stale success marker just to produce a green run.

## 15. Completion and handoff

Before calling a task complete:

1. Confirm the change implements the requested behavior in maintained source.
2. Review the diff for unrelated edits, generated content, accidental secrets,
   permission changes, and outdated documentation.
3. Run checks appropriate to the change and inspect their results. Report
   failures/skips and missing prerequisites; do not imply they passed.
4. Update public behavior docs and this guide when their contracts changed.
5. Confirm package checksums, release metadata, and provenance are consistent
   when their inputs changed.
6. Inspect `git diff --check`, `git diff --stat`, and `git status --short`.
   For newly created untracked files, inspect the file contents too; ordinary
   `git diff` does not include them until they are added to the index.
7. Leave unrelated work intact and generated outputs outside tracked source.

In the handoff, state what changed, why it matters, the checks actually run,
and any material limitation. Link the relevant source files and, for builds,
identify the run/artifact path. Distinguish unit tests, schema validation,
offscreen launch, filesystem validation, VM installation, and hardware testing.
Do not claim a release is ready solely because an ISO exists.

Commit, push, publish, or perform destructive installation only when that action
is within the user's authorized scope. A normal code or documentation task can
be completed with a reviewable working-tree diff and an accurate handoff.
