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
