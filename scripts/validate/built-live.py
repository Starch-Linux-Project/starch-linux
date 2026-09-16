#!/usr/bin/env python3
"""Validate installed live-image artifacts without executing code from the image."""
import configparser
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
users = {row.split(":")[0]: row.split(":") for row in (root / "etc/passwd").read_text().splitlines()}
assert users["liveuser"][6] == "/usr/bin/fish", "Live user missing or wrong shell"
assert users["root"][6] == "/usr/bin/bash", "Root shell must be Bash"
home = root / users["liveuser"][5].lstrip("/")
assert home.is_dir() and home.stat().st_uid == int(users["liveuser"][2]), "Live home ownership incorrect"
for path in ["usr/share/wayland-sessions/plasma.desktop", "usr/bin/fish", "usr/bin/fastfetch", "usr/bin/konsole", "usr/bin/firefox", "usr/bin/nautilus", "usr/lib/systemd/system/sddm.service"]:
    assert (root / path).is_file(), f"Missing {path}"
settings = configparser.ConfigParser()
settings.optionxform = str
settings.read(home / ".config/kdeglobals")
assert settings["KDE"]["LookAndFeelPackage"] == "org.starch.desktop", "Starch Plasma theme is not selected"
assert settings["General"]["ColorScheme"] == "BreezeDark", "Breeze Dark is not selected"
layout = root / "usr/share/plasma/look-and-feel/org.starch.desktop/contents/layouts/org.kde.plasma.desktop-layout.js"
layout_text = layout.read_text()
for launcher in ("firefox.desktop", "org.gnome.Nautilus.desktop", "org.kde.konsole.desktop"):
    assert f"applications:{launcher}" in layout_text, f"Missing pinned launcher: {launcher}"
sudoers = root / "etc/sudoers.d/10-starch-live"
assert sudoers.stat().st_uid == 0 and sudoers.stat().st_mode & 0o777 == 0o440, "Unsafe sudoers permissions"
assert not (root / "etc/pacman.d/hooks/90-starch-live-user.hook").exists(), "Build-only hook left in image"
print("Built live filesystem validation passed")
for path in ["usr/bin/calamares", "usr/local/bin/starch-install", "etc/calamares/settings.conf",
             "usr/share/applications/starch-install.desktop", "usr/share/starch-installer/minimal-packages.txt",
             "usr/lib/starch-installer/runtime.py"]:
    assert (root / path).is_file(), f"Missing installer artifact: {path}"
for module in ["welcome", "locale", "keyboard", "partition", "users", "summary", "finished",
               "mount", "umount", "machineid", "fstab", "localecfg", "displaymanager", "bootloader",
               "starch-preflight", "starch-bootstrap", "starch-configure", "starch-validate"]:
    assert (root / "usr/lib/calamares/modules" / module / "module.desc").is_file(), f"Missing module: {module}"
assert (root / "usr/local/bin/starch-install").stat().st_mode & 0o111, "Installer launcher is not executable"
assert (home / "Desktop/starch-install.desktop").is_file(), "Live desktop installer shortcut is missing"
partition_modules = list((root / "usr/lib/calamares/modules/partition").glob("*.so"))
assert len(partition_modules) == 1 and b"Starch erase target:" in partition_modules[0].read_bytes(), "Calamares partition safety patch is missing"
print("Built installer filesystem validation passed")
