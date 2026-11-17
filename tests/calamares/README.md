# Native Installation Profiles test

`advanced-selection.cpp` loads the built `starchadvanced` plugin and operates
its actual radio buttons. It checks the KDE default, every pair of profile
transitions, repeated clicks, page reuse, missing-bundle fallback, global storage
and mutual exclusion without
running partition or installation jobs.

First build Calamares and run `bash scripts/validate/calamares-smoke.sh`, which
installs that package in the isolated Calamares chroot. Copy this test and the
`src/libcalamares` and `src/libcalamaresui` header directories from the pinned
3.3.14 source into `build/calamares/chroot/starch/advanced-test/` using the
repository's rootless user-namespace mechanism. Inside that chroot, run:

```sh
cd /starch/advanced-test
g++ -fPIC advanced-selection.cpp -Ilibcalamares -Ilibcalamaresui \
    $(pkg-config --cflags --libs Qt6Widgets) -lcalamares -lcalamaresui \
    -o advanced-selection
QT_QPA_PLATFORM=offscreen ./advanced-selection
```

Expected output: `Installation Profiles radio transitions passed.`
This tests installer selection, not an installed desktop session.

## Additional Software

After building the package and running the launch smoke check, run:

```sh
bash scripts/validate/calamares-software.sh
```

This compiles `software-selection.cpp` against the pinned headers and loads the
actual `starchsoftware` plugin offscreen. It covers empty defaults, raw entry
persistence across navigation and page recreation, Summary escaping, stable
deduplication, continued processing after warnings, empty-selection no-op, and
skip waiting for a transaction to finish before omitting remaining requests.

The runner uses a private mount namespace to substitute `software-helper.py`
inside the build chroot. The fake helper records transaction boundaries and
never invokes a package manager. The substitution disappears on exit. These
checks do not establish successful pacman/Flatpak installation or first boot;
exercise those on disposable VM disks for each target repository profile.
