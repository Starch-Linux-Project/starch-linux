# Starch Lite

Starch Lite is an optional configuration of Starch Linux 1.3 with the same
identity and branding. It is included in normal builds; fresh boot and desktop
validation remain required.

Select **Starch Lite — For experienced users** on the **Installation Profiles** page.
KDE Plasma LTS is the default until another profile is selected.

| Component | Lite configuration |
| --- | --- |
| Kernel | Linux Zen |
| Init and sessions | Artix OpenRC and elogind |
| Desktop | Xfce on X11, LightDM |
| Boot and storage | Limine, ext4, and compressed zram swap |
| Package sources | Artix system, world, and galaxy; Arch extra |

This preserves the previous Lite + Xfce installation. Xfce uses Thunar and has
animations, compositing, and session restoration off by default. Users can
customize desktop settings after installation. Lite with Plasma or COSMIC is
no longer selectable. Historical implementation details below may describe
retained shared integration files for those former combinations.

Lite provides a recovery text login on **Ctrl+Alt+F2**. Networking, audio,
Bluetooth, and the firewall are configured through OpenRC and session services.
No fixed memory saving or performance improvement is promised.

Runtime packages update from Artix and Arch extra through `pacman -Syu`.
Starch's Lite configuration package has no dedicated binary update repository.
The standard installation and live desktop use Arch packages and systemd.

## Repository and user-directory fixes

The shared `calamares/pacman-lite.conf` previously included
`/etc/pacman.d/mirrorlist` under `[extra]`. That path contains Arch mirrors in
the live environment but Artix mirrors in an installed Lite system. The same
template is staged as `/usr/share/starch-installer/pacman-lite.conf`, used by
preflight and pacstrap, and copied to the target's `/etc/pacman.conf` by
`scripts/installer/bootstrap.py`. Consequently, Arch's `extra.db` could be
requested from Artix mirrors after installation. The explicit Arch fallback
servers explain why synchronization could still succeed despite the errors.
This code defect is confirmed; the tester's installed files were not available
for direct inspection. There is only one `[extra]` declaration in the template,
and no maintained Lite first-boot script rewrites it. The live-only mirror
helper and uncomment hook are excluded from the installed overlay.

The fix removes the ambiguous include and keeps the existing explicit servers
for both distributions, in the existing `system`, `world`, `galaxy`, `extra`
order. No new mirror URLs, mirror-copying logic, or signing changes are needed.
Simply changing the include to `mirrorlist-arch` would also require ensuring
that file exists in the Arch live environment before preflight.
Artix's [repository documentation](https://wiki.artixlinux.org/Main/Repositories)
was requested during investigation but returned HTTP 429, so current wiki
guidance could not be independently checked in this environment.

`scripts/installer/profiles.py` now explicitly selects `xdg-user-dirs` for
Lite Xfce. Neither the shared minimal manifest nor the previous Xfce extension
requested it explicitly. KDE's working directories were reported by the tester;
its exact transitive dependency path was not verified here. Calamares creates
the account after bootstrap seeds `/etc/skel`. Lite uses the native
`startxfce4` launcher, whose [upstream startup script](https://raw.githubusercontent.com/xfce-mirror/xfce4-session/master/scripts/xinitrc.in)
already invokes `xdg-user-dirs-update` as the session user. The package also
supplies an XDG autostart entry. No additional service or root-run directory
initialization is introduced. Standard Starch LTS is unchanged.

### Validation

- `python -m unittest discover -s tests/unit`: all 69 tests passed.
- The repository regression test resolves the template with real `pacman-conf`
  against temporary Arch-like and Artix-like mirrorlist fixtures. Both resolve
  only the existing Arch servers for `extra`, and only Artix for the other
  three repositories, preserving priority.
- The real Xfce package selection is checked for `xdg-user-dirs`.
- Running the installed `xdg-user-dirs-update` in a temporary home as an
  unprivileged user created Documents, Music, Pictures, and Videos with that
  user's ownership. A second run preserved a custom Documents location.
  Projects was not created; it is not a standard XDG directory.
- Direct mirror HTTP checks could not run because shell network DNS was
  unavailable. No host package operations, clean, or ISO build were run.

Before release, build a new ISO and install both Lite editions in disposable
VMs. On first login and again after reboot, run `pacman-conf --repo-list` and
`pacman-conf -r extra Server`; the latter must list only Arch mirrors. Run
`sudo pacman -Syu` inside those VMs and check for mirror errors. In Xfce, run
`pacman -Q xdg-user-dirs`, query DOCUMENTS/MUSIC/PICTURES/VIDEOS with
`xdg-user-dir`, and check that each returned directory exists and belongs to
the regular user. Actual Artix package contents and desktop first-login
behavior still need this installation validation.

### Repair an existing installation

On the affected Lite system, first back up and inspect the configuration:

```sh
sudo cp -a /etc/pacman.conf /etc/pacman.conf.before-lite-fix
sudoedit /etc/pacman.conf
```

In **only the `[extra]` section**, remove
`Include = /etc/pacman.d/mirrorlist`. For an unmodified Starch Lite installation,
retain the two existing lines:

```ini
[extra]
Server = https://geo.mirror.pkgbuild.com/$repo/os/$arch
Server = https://mirrors.kernel.org/archlinux/$repo/os/$arch
```

Preserve other repositories, settings, and any intentional custom Arch mirrors.
Do not remove the Artix mirrorlist or change Artix repository includes.
Check the result before updating:

```sh
pacman-conf --repo-list
pacman-conf -r extra Server
sudo pacman -Syu
```

For the Xfce directory fix, install the missing package with a full upgrade:

```sh
sudo pacman -Syu xdg-user-dirs
```

Then run `xdg-user-dirs-update` in the affected user's own desktop terminal,
**without sudo**, or log out and back in. Do not use `--force` or delete
`~/.config/user-dirs.dirs`; preserve existing custom directory choices.
If a directory was previously disabled (its entry points to `$HOME`), normal
initialization respects that choice. Inspect `~/.config/user-dirs.dirs` and
explicitly choose a new location if desired, for example:

```sh
mkdir -p "$HOME/Documents"
xdg-user-dirs-update --set DOCUMENTS "$HOME/Documents"
```

Repeat only for directories the user wants to restore, using their preferred
names and locations. Projects can be created manually if desired.

### Release note

Fixed Starch Lite KDE and Xfce attempting to fetch Arch repository databases
from Artix mirrors. Lite Xfce now explicitly installs the component that
creates standard user folders on first login.
