#!/usr/bin/env python3
"""Validate installed live-image artifacts without executing code from the image."""
import pathlib
import re
import sys
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'installer'))
from cosmic import GREETER_COMMAND, PINS, validate_vendor_units
from media_defaults import validate_defaults
from profiles import check_cosmic_packages

root = pathlib.Path(sys.argv[1])
data = root / "usr/share/starch-installer"
packages = pathlib.Path(sys.argv[2]).read_text()
check_cosmic_packages(dict(line.split() for line in packages.splitlines() if line.strip()), live=True)
users = {row.split(":")[0]: row.split(":") for row in (root / "etc/passwd").read_text().splitlines()}
assert users["liveuser"][6] == "/usr/bin/fish", "Live user missing or wrong shell"
assert users["root"][6] == "/usr/bin/bash", "Root shell must be Bash"
home = root / users["liveuser"][5].lstrip("/")
uid, gid = map(int, users["liveuser"][2:4])
assert home.is_dir() and (home.stat().st_uid, home.stat().st_gid) == (uid, gid), "Live home ownership incorrect"
for path in ("usr/bin/start-cosmic", "usr/bin/cosmic-session", "usr/bin/cosmic-comp",
             "usr/bin/cosmic-greeter", "usr/bin/greetd", "usr/bin/fish", "usr/bin/fastfetch",
             "usr/bin/kdialog", "usr/lib/qt6/plugins/platforms/libqwayland.so",
             "usr/lib/qt6/plugins/platforminputcontexts/libqtvirtualkeyboardplugin.so"):
    assert (root / path).is_file(), f"Missing {path}"
for launcher in PINS:
    assert (root / "usr/share/applications" / (launcher + ".desktop")).is_file(), f"Missing pin: {launcher}"
sessions = root / "usr/share/wayland-sessions"
assert {p.name for p in sessions.glob("*.desktop")} == {"cosmic.desktop"}
assert not list((root / "usr/share/xsessions").glob("*.desktop"))
assert re.search(r"^Exec=/usr/bin/start-cosmic\s*$", (sessions / "cosmic.desktop").read_text(), re.M)
validate_vendor_units(root)
validate_defaults(root)
units = root / "etc/systemd/system"
assert (units / "display-manager.service").readlink().name == "cosmic-greeter.service"
assert (units / "greetd.service").readlink().as_posix() == "/dev/null"
config = tomllib.loads((root / "etc/greetd/cosmic-greeter.toml").read_text())
assert config["terminal"]["vt"] == 1
assert config["general"]["service"] == "starch-greetd"
assert config["initial_session"] == {"command": "/usr/bin/start-cosmic", "user": "liveuser"}
assert config["default_session"] == {"command": GREETER_COMMAND, "user": "cosmic-greeter"}
assert (root / GREETER_COMMAND.lstrip("/")).stat().st_mode & 0o777 == 0o755

desktop = data / "desktop-overlays/cosmic"
idle = pathlib.Path(".config/cosmic/com.system76.CosmicIdle/v1")
for key in ("screen_off_time", "suspend_on_ac_time", "suspend_on_battery_time"):
    assert (home / idle / key).read_text().strip() == "None", f"Live idle timer enabled: {key}"
    for target_overlay in (desktop, data / "target-overlay"):
        assert not (target_overlay / "etc/skel" / idle / key).exists(), f"Live idle policy in target: {key}"
for overlay in (desktop, data / "rotation-overlay"):
    for source in overlay.rglob("*"):
        if source.is_file():
            relative = source.relative_to(overlay)
            assert (root / relative).read_bytes() == source.read_bytes(), f"Live overlay mismatch: {relative}"
            if relative.is_relative_to("etc/skel"):
                installed = home / relative.relative_to("etc/skel")
                assert installed.read_bytes() == source.read_bytes(), f"Live skeleton mismatch: {relative}"
                info = installed.stat()
                assert (info.st_uid, info.st_gid) == (uid, gid), f"Wrong live ownership: {relative}"
                assert info.st_mode & 0o777 == source.stat().st_mode & 0o777, f"Wrong live mode: {relative}"
wallpapers = data / "target-overlay/usr/share/backgrounds/starch"
for source in wallpapers.glob("*"):
    assert (root / "usr/share/backgrounds/starch" / source.name).read_bytes() == source.read_bytes()
luu_modes = {
    "usr/local/bin/linux-update-utility.AppImage": 0o755,
    "usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg": 0o644,
    "usr/share/applications/linux-update-utility.desktop": 0o644,
}
for path, mode in luu_modes.items():
    artifact = root / path
    assert artifact.is_file(), f"Missing Linux Update Utility artifact: {path}"
    assert artifact.stat().st_mode & 0o777 == mode, f"Wrong mode for {path}"
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
             "usr/lib/starch-installer/runtime.py", "usr/lib/starch-installer/additional.py"]:
    assert (root / path).is_file(), f"Missing installer artifact: {path}"
for module in ["welcome", "locale", "keyboard", "partition", "users", "summary", "finished",
               "starchsoftware", "mount", "umount", "machineid", "fstab", "localecfg", "bootloader",
               "starch-preflight", "starch-bootstrap", "starch-configure", "starch-limine", "starch-validate"]:
    assert (root / "usr/lib/calamares/modules" / module / "module.desc").is_file(), f"Missing module: {module}"
assert (root / "usr/local/bin/starch-install").stat().st_mode & 0o111, "Installer launcher is not executable"
assert (root / "usr/local/lib/starch/smoke-installer").stat().st_mode & 0o111, "Live smoke test is not executable"
launcher = (root / "usr/local/bin/starch-install").read_text()
assert "kdialog --title" in launcher and 'standard "Standard keyboard" on' in launcher and "unset QT_IM_MODULE" in launcher, "Installer has no standard-keyboard chooser default"
assert "--on-screen-keyboard" in launcher and "export QT_IM_MODULE=qtvirtualkeyboard" in launcher, "Installer has no optional Qt Virtual Keyboard mode"
assert (home / "Desktop/starch-install.desktop").is_file(), "Live desktop installer shortcut is missing"
partition_modules = list((root / "usr/lib/calamares/modules/partition").glob("*.so"))
assert len(partition_modules) == 1, "Expected one partition module"
partition_plugin = partition_modules[0].read_bytes()
assert b"Starch erase target:" in partition_plugin and b"starchDiskSequence" in partition_plugin, "Calamares disk identity guard is missing"
assert not (root / "usr/lib/calamares/modules/starchadvanced").exists()
print("Built installer filesystem validation passed")
