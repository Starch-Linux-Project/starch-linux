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
for path in ["usr/share/wayland-sessions/plasma.desktop", "usr/bin/fish", "usr/bin/fastfetch", "usr/bin/konsole", "usr/bin/kdialog", "usr/bin/firefox", "usr/bin/nautilus", "usr/bin/plasma-keyboard", "usr/share/applications/org.kde.plasma.keyboard.desktop", "usr/lib/qt6/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so", "usr/lib/systemd/system/sddm.service"]:
    assert (root / path).is_file(), f"Missing {path}"
luu_modes = {
    "usr/local/bin/linux-update-utility.AppImage": 0o755,
    "usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg": 0o644,
    "usr/share/applications/linux-update-utility.desktop": 0o644,
}
for path, mode in luu_modes.items():
    artifact = root / path
    assert artifact.is_file(), f"Missing Linux Update Utility artifact: {path}"
    assert artifact.stat().st_mode & 0o777 == mode, f"Wrong mode for {path}"
settings = configparser.ConfigParser()
settings.optionxform = str
settings.read(home / ".config/kdeglobals")
assert settings["KDE"]["LookAndFeelPackage"] == "org.starch.desktop", "Starch Plasma theme is not selected"
assert settings["General"]["ColorScheme"] == "BreezeDark", "Breeze Dark is not selected"
kwinrc = configparser.ConfigParser()
kwinrc.read(home / ".config/kwinrc")
assert kwinrc["Wayland"]["InputMethod[$e]"] == "/usr/share/applications/org.kde.plasma.keyboard.desktop", "Plasma Keyboard is not configured for the live session"
sddm = configparser.ConfigParser()
sddm.read(root / "etc/sddm.conf.d/10-starch-live.conf")
assert "--inputmethod plasma-keyboard" in sddm["Wayland"]["CompositorCommand"], "SDDM has no Plasma Keyboard input method"
layout = root / "usr/share/plasma/look-and-feel/org.starch.desktop/contents/layouts/org.kde.plasma.desktop-layout.js"
layout_text = layout.read_text()
for launcher in ("firefox.desktop", "org.gnome.Nautilus.desktop", "org.kde.konsole.desktop"):
    assert f"applications:{launcher}" in layout_text, f"Missing pinned launcher: {launcher}"
sudoers = root / "etc/sudoers.d/10-starch-live"
assert sudoers.stat().st_uid == 0 and sudoers.stat().st_mode & 0o777 == 0o440, "Unsafe sudoers permissions"
assert not (root / "etc/pacman.d/hooks/90-starch-live-user.hook").exists(), "Build-only hook left in image"
firewall = root / "etc/nftables.conf"
assert firewall.is_file() and "table inet starch_filter" in firewall.read_text(), "Missing nftables ruleset"
nftables_service = root / "etc/systemd/system/multi-user.target.wants/nftables.service"
assert nftables_service.is_symlink() and nftables_service.readlink().as_posix() == "/usr/lib/systemd/system/nftables.service", "nftables service is not enabled"
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
launcher = (root / "usr/local/bin/starch-install").read_text()
assert "kdialog --title" in launcher and 'standard "Standard keyboard" on' in launcher and "unset QT_IM_MODULE" in launcher, "Installer has no standard-keyboard chooser default"
assert "--on-screen-keyboard" in launcher and "export QT_IM_MODULE=qtvirtualkeyboard" in launcher, "Installer has no optional Qt Virtual Keyboard mode"
assert (home / "Desktop/starch-install.desktop").is_file(), "Live desktop installer shortcut is missing"
partition_modules = list((root / "usr/lib/calamares/modules/partition").glob("*.so"))
assert len(partition_modules) == 1 and b"Starch erase target:" in partition_modules[0].read_bytes(), "Calamares partition safety patch is missing"
print("Built installer filesystem validation passed")
