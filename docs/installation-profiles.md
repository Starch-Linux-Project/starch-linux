# Installation Profiles

The existing single online-install ISO now offers exactly three exclusive choices:

| Visible profile | Existing installation identity | Desktop / login | Kernel / init |
| --- | --- | --- | --- |
| KDE Plasma LTS — Recommended (default) | `standard` | Plasma / SDDM | Linux LTS / systemd |
| COSMIC LTS | `standard-cosmic` | COSMIC / greetd | Linux LTS / systemd |
| Starch Lite — For experienced users | `lite-xfce` | Xfce / LightDM | Linux Zen / OpenRC |

The three choices preserve their previous ordered package selections, repositories,
configuration overlays, services, bootloader and post-installation behavior.
Shared applications already present in these configurations remain present.
Lite's zram service, service trimming, Xfce defaults, audio supervisor and Artix
integration are unchanged. No installation payload files were removed.

## Selection implementation and compatibility

The existing `starchadvanced` Qt Widgets plugin now presents Installation Profiles,
with three radio buttons in one exclusive QButtonGroup. The internal module name
and patch filename remain stable so staging and packaging need no migration.
KDE is checked when the page is created. The same page instance retains selection
when navigating back and forward. The selected profile is also shown in summary.

The page writes the existing `starchDesktop`, `starchLite`, and `starchLiteXfce`
keys. Lite always writes XFCE; the two LTS profiles always write non-Lite state.
The Advanced acknowledgement and separate desktop/init checkboxes are removed.
Preflight and bootstrap reject all other combinations, including stale Lite/KDE
and Lite/COSMIC state. Bundle verification still happens before disk operations.
An ISO missing its Lite bundle shows Lite disabled, as before; normal ISO builds
continue to stage the bundle and enable all three choices.

Pinned Calamares 3.3.14 source was inspected locally. Its packagechooser module
can select a default radio item, but writes packagechooser/netinstall state,
not Starch's existing desktop/init contract. It is excluded from this package's
build. Reusing the already shipped native module is the smaller change and
requires no new dependencies, QML support, or additional Calamares fork.
The Calamares package release is bumped to 13 and its patch checksum updated.

Legacy low-level desktop integration helpers remain where shared with existing
payloads or audit tests; they do not expose additional installer selections.

## Validation performed

- All 99 Python unit tests passed.
- Regression fixture `tests/fixtures/installation-profiles.json` captures the
  original ordered package lists from the pre-change committed implementation.
  Tests compare all three retained profiles exactly, and check kernels and
  repository configuration selection.
- All Calamares packaging patches applied to pristine pinned 3.3.14 source.
- All 12 configured upstream module schemas validated against that source.
- `./build.sh --check` passed; `git diff --check` passed.
- The changed native plugin compiled with Qt 6 and existing Calamares 3.3.14
  libraries. The offscreen native test passed for KDE default, all pairwise
  transitions, repeated clicks, page reuse, storage values and disabled Lite.
  This was a direct plugin build, not a complete package or ISO rebuild.

## Remaining manual acceptance

Rebuild the Calamares package and ISO before shipping. In the real installer,
check readability at the minimum supported resolution and back/forward navigation
through summary. Perform fresh online installations and reboots for each row:

| Profile | Required live ISO / VM checks |
| --- | --- |
| KDE Plasma LTS | LTS kernel, systemd services, SDDM/Plasma login, existing customization, networking, audio, UEFI and BIOS boot |
| COSMIC LTS | LTS kernel, systemd services, greetd/COSMIC login and lock, networking, audio, UEFI and BIOS boot |
| Starch Lite | Zen kernel, OpenRC boot/runlevels, LightDM/Xfce login, networking, audio, zram, service trimming, Artix updates, UEFI and BIOS boot |

No fresh installation, installed-system boot, or hardware desktop acceptance was
performed for this change.

## Changed files

- `packages/calamares/0005-starch-advanced-page.patch`, `packages/calamares/PKGBUILD`
- `calamares/modules/starchadvanced.conf`, `calamares/branding/starch/stylesheet.qss`
- `scripts/installer/profiles.py`, `scripts/installer/preflight.py`
- `tests/calamares/advanced-selection.cpp`, `tests/calamares/README.md`
- `tests/unit/test_desktop_selection.py`, `tests/unit/test_cosmic.py`,
  `tests/unit/test_starch_lite.py`, `tests/unit/test_rotation.py`
- New `tests/fixtures/installation-profiles.json`
- `README.md`, `docs/starch-lite.md`, `docs/cosmic.md`, `docs/rotation.md`,
  `docs/virtual-keyboard.md`, and this new document

No files removed.
