# Native Additional Software test

After building the package and running the launch smoke check, run:

```sh
bash scripts/validate/calamares-software.sh
```

This compiles `software-selection.cpp` against the pinned headers and loads the
actual `starchsoftware` plugin offscreen through the real Calamares JobQueue. It covers empty defaults, raw entry
persistence across navigation and page recreation, Summary escaping, stable
deduplication, continued processing after warnings, empty-selection no-op, and
skip waiting for a transaction to finish before omitting remaining requests,
live package-output display, and suppression after an essential job failure.

The runner uses a private mount namespace to substitute `software-helper.py`
inside the build chroot. The fake helper records transaction boundaries and
never invokes a package manager. The substitution disappears on exit. These
checks do not establish successful pacman/Flatpak installation or first boot;
exercise those on disposable VM disks using the Arch repositories.
