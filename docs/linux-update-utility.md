# Linux Update Utility

Linux Update Utility is included in the live environment and installed system.
Open it from the application menu or its pinned Plasma or Starch Lite Xfce
panel icon.

The Xfce panel launcher references `/usr/share/applications/linux-update-utility.desktop`
directly. That entry uses the installed SVG's absolute path, so the launcher
does not depend on menu discovery or a refreshed icon-theme cache after staging.
On an existing Xfce installation, edit the Linux Update Utility launcher in the
panel's Properties and set its icon to
`/usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg`.
If the launcher is empty, add Linux Update Utility to it again. Xfce keeps a
per-user copy of launcher entries, so rebuilding the ISO does not repair an
existing user's copy. This concerns the pinned launcher; a missing icon on a
running window requires checking the AppImage's window icon separately.

The utility is bundled as an AppImage from a separately built project.
Starch provides its desktop integration. Existing installations do not receive
replacement AppImages through a Starch package repository or dedicated update
channel; new bundled versions require a new ISO.

Distribution of the AppImage and artwork is subject to the
[licensing and provenance requirements](licensing.md).
