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

Historical plans and validation reports are context, not present-day proof.
Some older documentation describes an Advanced acknowledgement gate or earlier
Lite desktop combinations. The current UI exposes three installation profiles,
and `validate_selection()` enforces the supported combinations. Compatibility
helpers and legacy session files do not establish support for more profiles.

## 2. Product and platform contract

Starch Linux is an x86_64 Linux distribution built with Archiso. One live ISO
provides a graphical, online, erase-disk installer using Calamares.

| Environment | Profile identity | Desktop and login | Kernel | Init | Repositories |
| --- | --- | --- | --- | --- | --- |
| Live ISO | Not a target profile | Plasma Wayland / SDDM | `linux` | systemd | Arch plus the staged local installer package |
| KDE Plasma LTS, default | `standard` | Plasma Wayland / SDDM | `linux-lts` | systemd | Arch |
| COSMIC LTS | `standard-cosmic` | COSMIC Wayland / COSMIC Greeter through greetd | `linux-lts` | systemd | Arch |
| Starch Lite | `lite-xfce` | Xfce X11 / LightDM | `linux-zen` | OpenRC | Artix `system`, `world`, `galaxy`, then Arch `extra` |

Shared installed-system behavior includes ext4, Limine, zram, NetworkManager,
PipeWire, Flatpak/Flathub, and Linux Update Utility. Fish is the standard user's
default shell. Flatpak applications are not preinstalled merely because Flathub
is configured.

Preserve these boundaries unless the task explicitly changes them:

- Installation downloads fresh target packages with `pacstrap`; it does not
  clone the live filesystem into the target.
- Installation erases the selected whole disk. There is no supported manual
  partitioning, install-alongside, or dual-boot workflow.
- UEFI and legacy BIOS are supported installation modes. Secure Boot is not a
  supported workflow.
- Full-disk encryption, offline installation, hibernation, snapshot rollback,
  ARM images, and 32-bit images are outside the documented scope.
- The live environment remains Plasma/systemd even when installing Lite.
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
| `calamares/pacman-lite.conf` | Lite target repository order and signature policy. |
| `manifests/minimal-packages.txt` | Baseline installed package requests; profile helpers transform this list. |
| `scripts/installer/` | Starch installer stages, validation, profile selection, and target configuration. |
| `scripts/build/stage-installer.py` | Copies maintained sources into a generated profile and assembles target overlays. |
| `scripts/build/calamares*.sh` | Isolated Calamares package construction and chroot operations. |
| `scripts/build/starch-lite*.sh` | Lite integration package and verified bundle construction. |
| `packages/calamares/` | Pinned PKGBUILD and Starch patches to upstream Calamares. |
| `packages/starch-lite/integration/` | Lite integration PKGBUILD, OpenRC banner/zram services and Xfce defaults; audio uses upstream Artix services. |
| `packages/starch-lite/artix-keyring.json` | Pinned bootstrap keyring source and checksum. |
| `packages/starch-cosmic/root/` | Supported COSMIC target overlay and account defaults. |
| `packages/starch-cosmic/lite-root/` | Compatibility material; not a separately supported selectable profile. |
| `packages/starch-rotation/root/` | Session rotation helper, autostart, and lock launcher. |
| `packages/linux-update-utility/` | Starch desktop integration for a separately supplied AppImage. |
| `fastfetch-text` | Maintained root artwork; staging refreshes the live copy from this file. |
| `wallpapers/` | Wallpaper source inputs and packaging guidance. |
| `scripts/validate/` | Schema checks, Calamares launch smoke test, and built-live filesystem checks. |
| `tests/unit/` | Python `unittest` suite using fixtures, temporary trees, and mocked system boundaries. |
| `tests/fixtures/installation-profiles.json` | Profile expectation fixtures. |
| `tests/calamares/` | Native Qt profile-selection test and its build instructions. |
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
- `build/calamares/repo/`: installer package, repository database, checksums,
  source archive, notices, and dependency records.
- `build/calamares/smoke.log`: installer launch smoke-test output.
- `build/starch-lite/artix-repo/`: verified Lite bundle and provenance artifacts.
- `starch-out/run-*`: normal build output and accompanying reports.

Edit maintained source, not files inside these generated trees. A change made
only in a staged profile or chroot will disappear on rebuild and will not be
reviewable as a source change.

## 4. Installer architecture and execution order

`calamares/settings.conf` is the authority for execution order. The current
visible pages are welcome, locale, keyboard, partition, users,
`starchadvanced`, `starchsoftware` (Additional Software), and summary. The module name `starchadvanced` persists even
though the public page is Installation Profiles.

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
11. `displaymanager`
12. `starch-configure`
13. `starch-limine`
14. `starch-validate`
15. `starchsoftware` (optional software; warning-only failures)
16. `umount`

The Additional Software page preserves raw entries in `starchSoftware_pacman`
and `starchSoftware_flathub`; its native job deduplicates requests and shows
separate progress. Skip waits for the active transaction, then drops pending
requests. Optional failures are warnings and never fail the OS job queue.
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
| `profiles.py` | Canonical profile/desktop identity, valid combinations, package transforms, COSMIC dependency audit, kernel choice, and Lite bundle verification. |
| `preflight.py` | Validate selection and erase mode, inspect/deactivate selected-disk consumers, resolve packages and trust, recheck the disk, and save the resolved selection. |
| `bootstrap.py` | Validate saved identity and Lite inputs, run bounded `pacstrap` retries, install verified local integration, and seed overlays before account creation. |
| `configure.py` | Configure the installed system and dispatch profile-specific setup. |
| `cosmic.py` | COSMIC login/session/default configuration and validation. |
| `lite.py` | OpenRC service/session setup, EFI stub handling, and Lite validation. |
| `graphics.py` | Display-device identification and kernel-aware graphics package selection. |
| `repositories.py` | Isolated Lite signing trust bootstrap. |
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
- Fail before mutation when profile state is contradictory, a required bundle
  is missing, trust is invalid, or mounted-target identity cannot be established.

Use disposable VM disks for installation tests. A request to change installer
code is not permission to erase a host disk. Do not infer destructive approval
from a device name, an apparently empty disk, or a previous unrelated test.

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

## 6. Profiles, packages, repositories, and signing

### Profile selection is a cross-layer contract

Profile changes can affect the native Qt page, Calamares global storage,
`profiles.py`, preflight, bootstrap, configuration, validation, fixtures, and
documentation. Review the whole path rather than changing only a label.

- KDE Plasma LTS is the default.
- Selection is mutually exclusive, survives navigation, and appears in Summary.
- Lite is included in normal builds and disabled when its required bundle is
  unavailable. Stale stored selection must still be rejected by Python stages.
- `starchLite`, `starchDesktop`, and the compatibility key `starchLiteXfce` must
  resolve consistently. Keep `validate_selection()` ahead of disk operations.
- Reject unsupported combinations even if helper functions can name them.
  Legacy Plasma/OpenRC or COSMIC/OpenRC code is not an invitation to expose a
  fourth profile without an explicitly scoped feature change.
- Remove unwanted desktop packages before dependency resolution; hiding their
  login sessions after installation is insufficient isolation.

### Package sources and transaction checks

Keep live requests in `archiso/profile/packages.x86_64` and baseline target
requests in `manifests/minimal-packages.txt`. Use `profiles.py` for target
transformations. The manifest parser rejects duplicates, empty manifests,
options, and invalid package names; preserve that behavior.

Standard targets use Arch repositories. Lite uses Artix repositories before
Arch `extra`, with Arch `core` disabled. Do not inherit unrelated host repository
settings or allow host mirror configuration to silently change this boundary.

COSMIC uses explicit package roots and an audit of the resolved transaction,
including transitive dependencies. The current audit pins specified components
to upstream version `1.11.0` after handling package epoch/release syntax. A new
version requires review of defaults, startup, greeter/locking, portals, keyboard,
and display command formats. Do not simply remove the version check to make a
new repository transaction pass.

Graphics selection must remain based on display hardware and the target kernel.
Review unknown vendors, hybrid GPUs, unsupported NVIDIA IDs, fallback behavior,
and matching headers/DKMS requirements for Linux Zen. Keep CPU microcode
selection vendor-based and conservative for unknown input.

### Lite bundle and trust

- The current bundle format is `3`, with repository identity
  `artix-arch-extra` and the expected `starch-lite` and `artix-keyring` entries.
- Verify allowed package names, basenames, regular-file status, non-symlink
  inputs, and SHA-256 checksums before using a bundle. Inspect the actual Lite
  archive identity (`0.2.2-16`) and reject retired audio/PAM payloads. Update the
  reviewed package version in `profiles.verify_lite_archive()` on package releases.
- Preserve the pinned Artix keyring acquisition record and checksum.
- Lite trust initialization is isolated; it must not populate or weaken the
  live Arch signing database.
- Bootstrap rechecks the saved bundle and repository-configuration hashes
  against preflight state. Do not replace those checks with mere file existence.
- Any relaxed local-file signature setting is scoped to already verified local
  archives. Preserve required signature policy for repository transactions and
  the installed configuration.
- Do not generalize the build's local installer repository trust settings to
  public package repositories or the installed system.

## 7. Live image, overlays, and account defaults

The live filesystem contains conveniences that must not leak into installed
systems: its user account, sudo policy, autologin, power/lock behavior, network
state, and build-only hooks. Preserve the explicit staging allowlist and the
distinction between shared target and desktop-specific overlays.

`stage-installer.py` currently assembles shared `target-overlay`, separate
desktop overlays, and a `rotation-overlay`. `bootstrap.apply_defaults()` applies
them according to the selected profile before user creation.

When changing a default:

1. Identify whether it belongs to the live session, all installed systems, one
   desktop, one init system, or a new user's home.
2. Edit the maintained source for that scope.
3. Check how staging copies it and which profile receives it.
4. Check required permissions in `profiledef.sh`, package installation, and
   bootstrap. Archiso can normalize nested overlay modes.
5. Check that account defaults are seeded before the account is created.
6. Check that later login does not overwrite the user's own settings.
7. Describe existing-installation effects accurately; new `/etc/skel` defaults
   do not retrofit existing homes.

Use `configure.py` for installed OS identity and
`archiso/profile/airootfs/etc/os-release` for live identity. Review both when
changing distribution naming or release information.

### Plasma and installer launch

The live installer launcher is
`archiso/profile/airootfs/usr/local/bin/starch-install`. It launches elevated
Calamares through XWayland using Qt's `xcb` backend, preserving the necessary
display authentication environment. The live image includes `xorg-xwayland`.

The launcher offers standard keyboard mode by default and an optional
on-screen-keyboard mode for installer fields. Keep that choice scoped to the
installer. Plasma's own keyboard, login screen, and lock screen use their
desktop integration; do not globally force a keyboard panel open for all users.
Installed-system autologin must remain disabled and validated.

### COSMIC

COSMIC uses greetd/COSMIC Greeter and dedicated overlay defaults. Preserve the
separation from Plasma and Lite display managers, sessions, and configuration.

COSMIC LTS uses Arch's vendor greeter units, with no full `/etc` replacements or
Starch service drop-ins. Keep the custom greeter launcher provisionally until its
bus/environment equivalence is tested; retain scoped `starch-greetd` PAM/keyring
integration. The reviewed Arch greeter 1:1.11.0-1 selects `login` for locking via
its packaging revert. COSMIC OSD supplies polkit; the GNOME fallback and unused
lock PAM overlay now live only in the dormant `lite-root` compatibility input.
Arch greeter/OSD package releases are audited exactly before fresh installation.
Do not turn installer configuration into an installed-system migration. See
`docs/cosmic.md` and the reversible procedure in `docs/cosmic-migration.md`.


The on-screen keyboard uses manual activation. Its default is the `false` value
at `/etc/skel/.local/state/cosmic/com.system76.CosmicOSK/v1/ime_activation`.
This is a state path, not a `.config` path. Validate that it reaches the created
user's home and preserve subsequent user changes.

### Lite

Lite uses OpenRC/elogind, LightDM, Xfce, Thunar, and Artix OpenRC user audio
services. Select pipewire-openrc, pipewire-pulse-openrc, wireplumber-openrc and
dbus-openrc. Seed ~/.config/rc/runlevels before account creation: dbus in boot,
audio services in default. Upstream pam_elogind and pam_openrc establish the
runtime directory and user-manager lifecycle. Do not restore the retired audio
supervisor, audio autostart, PAM helper or pacman hook. Validate the actual
user's runlevels/ownership and upstream PAM/service files without rewriting
them. Offline checks do not establish login/recovery/logout behavior: follow
docs/starch-lite-audio-migration.md in a disposable VM. Preserve the recovery
text login. Xfce compositing and session
restoration are off by default; account initialization should respect existing
user settings.

### Rotation

Plasma uses KWin and Qt Sensors. Standard COSMIC receives Starch's session
helper and `cosmic-randr`. Lite does not receive Starch automatic rotation
integration or its sensor packages.

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
  kernel/initramfs files, and the matching profile-specific kernel arguments.
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
scripts/build/starch-lite.sh --check
```

The top-level check requires Archiso/pacman tooling, Python, checksum/logging
utilities, valid source inputs, safe generated paths, and at least 20 GiB free.
The package sub-builds have additional tool checks, including chroot/bootstrap
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

This prepares/reuses verified Calamares and Lite package outputs, creates a fresh
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
scripts/build/starch-lite.sh --build
```

Both scripts also support `--ensure`, which reuses output only when input
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
Calamares/Lite source and notice artifacts. Preserve accompanying reports when
evaluating or handing off an ISO. `--compile` leaves reports in its work run,
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
not clean `starch-out`, `build/calamares`, or `build/starch-lite`; do not invent
unsupported cleanup arguments or replace it with broad recursive deletion.

## 10. Calamares packaging and upstream changes

The current package baseline is Calamares `3.3.14`, built with Qt 6 and a reduced
module set. The source's bundled pybind11 is replaced with the Arch build
dependency for the package's Python toolchain. Preserve the isolated official
Arch build configuration and the pinned upstream archive checksum.

Starch patches cover erase-only partitioning, OS-prober avoidance, live-only
autologin policy, installer presentation, profile selection, and optional software. When changing
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
| `test_starch_lite.py` | Artix/Arch separation, bundle/trust checks, OpenRC/session integration, Xfce, and Lite staging. |
| `test_rotation.py` | Display parsing, orientation behavior, mode preservation, and profile isolation. |
| `test_release_fixes.py` | Shared storage, BIOS mount safety, graphics selection, and Limine maintenance. |

Use temporary roots and mocked subprocess/system boundaries. Never turn a unit
test into a real host partition, service, package, or bootloader operation.
Useful negative cases include malformed state, changed disk identity, missing
mounts, symlink inputs, bundle tampering, unsupported profiles, dependency drift,
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

### Installer launch and native profile selection

After building the package:

```sh
bash scripts/validate/calamares-smoke.sh
```

This stages configuration, installs the package into the isolated Calamares
chroot, and launches the GUI offscreen. It does not execute installation jobs,
but it does modify generated chroot state. The timeout status indicates that
the GUI remained open; inspect `build/calamares/smoke.log` for module errors.
A successful launch does not prove a successful installation.

For native profile UI changes, follow `tests/calamares/README.md`. Its C++ test
loads the actual plugin and checks defaults, every profile transition, repeated
clicks, page reuse, missing-bundle fallback, global storage, and exclusion.
Compile it with the matching source headers/libraries in the prepared chroot.
Do not substitute a Python-only state test for checking the actual Qt controls.

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

For changes affecting installation or boot, test affected profiles and firmware
modes on disposable VM disks. Exercise the relevant cases rather than claiming
coverage from a single successful default installation:

- BIOS and UEFI live boot, installer launch, installation, and installed reboot.
- Default selection, every supported profile, back navigation, Summary, and
  missing-Lite-bundle behavior where the build/test fixture supports it.
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

Preserve both live and target delivery. Xfce's panel uses the installed desktop
entry directly, including the absolute icon path. Existing users can retain
copied launcher entries; a new ISO does not repair their local panel state.
Treat a panel icon issue separately from the AppImage's running-window icon.

Wallpaper inputs are packaged for Plasma and, for compatible formats, copied
for COSMIC discovery. Read `wallpapers/README.md` and the supported suffix sets
in staging before adding formats. The optional Evergreen source has an explicit
mapping; its absence should preserve upstream default behavior rather than
break all wallpaper discovery.

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
| Add/remove an installed app | Manifest, profile transforms, resolved dependencies, launcher/MIME defaults, and relevant target tests. |
| Change the live desktop | Live packages, `airootfs` defaults, permissions, staging allowlist, and built-live validation. |
| Change a profile | Qt patch, storage keys, profile helpers, preflight/bootstrap, configuration/validation, fixture, native test, and public profile docs. |
| Change a package source | Pacman configs, isolated keyring handling, preflight resolution, bundle identity/checksums, and provenance. |
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
| Lite is missing/disabled | Verified bundle availability, staging configuration, manifest identity, and checksums. |
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
