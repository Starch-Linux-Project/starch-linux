# Starch Calamares package

This package builds Calamares 3.3.14 from its signed-release archive with a
small Qt 6 module set for the Starch installer. It intentionally omits QML,
web-view, package chooser, telemetry, encryption, initramfs, OpenRC, OEM and
demo modules.

The build enables these modules:

`welcome locale keyboard partition users summary finished mount fstab
localecfg machineid hwclock bootloader shellprocess services-systemd
displaymanager umount`

The source release contains pybind11 2.11.1. The package replaces that bundled
copy at configure time with Arch's `pybind11` build dependency so the Python
module bridge builds against the same Python 3.14 toolchain as the package.
Pybind11 is header-only and is not a runtime dependency.

Run `scripts/build/calamares.sh --build`. The script creates or updates an
isolated rootless Arch build root using only the repository's official
`core`/`extra` pacman configuration. Packages, the local repository database,
the exact upstream source archive, license notices, dependency manifests and
checksums are emitted beneath `build/calamares/repo/`.

The Starch patch set keeps the installer erase-only, disables unnecessary OS
probing, hides installed-system autologin, and adds the native-Qt welcome and
installation content surfaces. Their news text lives in the branding directory,
so content updates do not require editing the C++ patch. Installed SDDM
autologin is also cleared by the target configuration stage and checked before
success.

In the live Plasma Wayland session, `/usr/local/bin/starch-install` elevates
Calamares with `sudo` and runs its Qt interface through XWayland. The launcher
preserves `DISPLAY` and `XAUTHORITY` and selects the `xcb` Qt backend. Do not
switch it back to a preserved `XDG_RUNTIME_DIR`: that directory belongs to the
live user, and current Qt rejects it after the process becomes root, leaving the
desktop shortcut with no installer window. The Archiso package list therefore
includes `xorg-xwayland` explicitly.
