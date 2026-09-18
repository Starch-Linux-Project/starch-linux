import configparser
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
PROFILE = ROOT / "archiso/profile"
FS = PROFILE / "airootfs"

class LiveProfile(unittest.TestCase):
    def test_starch_identity_is_consistent(self):
        profiledef = (PROFILE / "profiledef.sh").read_text()
        self.assertIn('iso_name="starch-linux"', profiledef)
        self.assertIn('iso_label="STARCH_', profiledef)
        os_release = (FS / "etc/os-release").read_text()
        self.assertIn('NAME="Starch Linux"', os_release)
        self.assertIn('PRETTY_NAME="Starch Linux Live"', os_release)
        self.assertIn('ID=starch', os_release)
        self.assertEqual((FS / "etc/hostname").read_text().strip(), "starch-live")
        self.assertTrue((FS / "etc/issue").read_text().startswith("Starch Linux Live"))
        self.assertEqual((FS / "etc/issue.net").read_text().strip(), "Starch Linux Live")
        visible_boot_files = [
            PROFILE / "grub/grub.cfg",
            PROFILE / "grub/loopback.cfg",
            PROFILE / "efiboot/loader/entries/01-archiso-linux.conf",
            PROFILE / "efiboot/loader/entries/02-archiso-speech-linux.conf",
            PROFILE / "syslinux/archiso_head.cfg",
            PROFILE / "syslinux/archiso_sys-linux.cfg",
            PROFILE / "syslinux/archiso_pxe-linux.cfg",
        ]
        for path in visible_boot_files:
            text = path.read_text()
            self.assertIn("Starch Linux", text, path)
            self.assertNotIn("Arch Linux", text, path)

    def test_desktop_boot_and_account_hook(self):
        units = FS / "etc/systemd/system"
        self.assertEqual((units / "default.target").readlink().name, "graphical.target")
        self.assertEqual((units / "display-manager.service").readlink().name, "sddm.service")
        cfg = configparser.ConfigParser()
        cfg.read(FS / "etc/sddm.conf.d/10-starch-live.conf")
        self.assertEqual(cfg["Autologin"]["Session"], "plasma.desktop")
        self.assertEqual(cfg["Autologin"]["User"], "liveuser")
        hook = configparser.ConfigParser(strict=False)
        hook.read(FS / "etc/pacman.d/hooks/90-starch-live-user.hook")
        script = hook["Action"]["Exec"].split()[-1]
        setup_script = FS / script.lstrip("/")
        self.assertTrue(setup_script.is_file())
        self.assertIn("'liveuser:root' | chpasswd", setup_script.read_text())
        self.assertFalse((units / "getty@tty1.service.d/autologin.conf").exists())
        self.assertIn("root:/root:/usr/bin/bash", (FS / "etc/passwd").read_text())

    def test_network_manager_has_no_competing_enabled_backend(self):
        units = FS / "etc/systemd/system"
        self.assertEqual((units / "multi-user.target.wants/NetworkManager.service").readlink().name, "NetworkManager.service")
        for unit in ("systemd-networkd.service", "systemd-networkd.socket", "iwd.service"):
            self.assertEqual(str((units / unit).readlink()), "/dev/null")
        self.assertTrue((units / "multi-user.target.wants/systemd-resolved.service").is_symlink())
        self.assertTrue((FS / "etc/resolv.conf").is_symlink())

    def test_artwork_and_manifest_contract(self):
        config = json.loads((FS / "etc/fastfetch/config.jsonc").read_text())
        artwork = FS / config["logo"]["source"].lstrip("/")
        self.assertEqual(artwork.read_bytes(), (ROOT / "fastfetch-text").read_bytes())
        self.assertEqual(config["logo"]["position"], "top")
        packages = [line.strip() for line in (PROFILE / "packages.x86_64").read_text().splitlines() if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(len(packages), len(set(packages)))
        self.assertTrue({"fish", "fuse2", "fastfetch", "sddm", "plasma-workspace", "plasma-desktop", "networkmanager", "konsole", "firefox", "nautilus"}.issubset(packages))
        self.assertIn("xorg-xwayland", packages)
        self.assertNotIn("plasma-x11-session", packages)

    def test_installer_uses_xwayland_across_sudo(self):
        launcher = (FS / "usr/local/bin/starch-install").read_text()
        self.assertIn("--preserve-env=DISPLAY,XAUTHORITY", launcher)
        self.assertIn("export QT_QPA_PLATFORM=xcb", launcher)
        self.assertNotIn("--preserve-env=WAYLAND_DISPLAY,XDG_RUNTIME_DIR", launcher)

    def test_linux_update_utility_archiso_permissions(self):
        profiledef = (PROFILE / "profiledef.sh").read_text()
        expected = {
            "/usr/local/bin/linux-update-utility.AppImage": "0:0:755",
            "/usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg": "0:0:644",
            "/usr/share/applications/linux-update-utility.desktop": "0:0:644",
        }
        for path, ownership_and_mode in expected.items():
            self.assertIn(f'["{path}"]="{ownership_and_mode}"', profiledef)

    def test_plasma_dark_theme_and_default_launchers(self):
        kdeglobals = configparser.ConfigParser()
        kdeglobals.optionxform = str
        kdeglobals.read(FS / "etc/skel/.config/kdeglobals")
        self.assertEqual(kdeglobals["KDE"]["LookAndFeelPackage"], "org.starch.desktop")
        self.assertEqual(kdeglobals["General"]["ColorScheme"], "BreezeDark")
        theme = FS / "usr/share/plasma/look-and-feel/org.starch.desktop"
        self.assertTrue((theme / "metadata.json").is_file())
        layout = (theme / "contents/layouts/org.kde.plasma.desktop-layout.js").read_text()
        self.assertIn('applications:firefox.desktop', layout)
        self.assertIn('applications:org.gnome.Nautilus.desktop', layout)
        self.assertIn('applications:org.kde.konsole.desktop', layout)
