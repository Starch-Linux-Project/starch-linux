import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import bootstrap
import cosmic
import media_defaults


def load_module(name, path):
    loader = importlib.machinery.SourceFileLoader(name, str(path))
    spec = importlib.util.spec_from_loader(name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def add_media_desktops(root):
    applications = root / 'usr/share/applications'
    applications.mkdir(parents=True, exist_ok=True)
    (applications / media_defaults.VLC).write_text(
        '[Desktop Entry]\nType=Application\nMimeType=video/mp4;audio/mpeg;image/vnd.rn-realpix;\n')
    (applications / media_defaults.VIEWER).write_text(
        '[Desktop Entry]\nType=Application\nMimeType=image/png;image/jpeg;image/gif;\n')


ARCH_FIXTURE = ROOT / 'tests/fixtures/cosmic-arch-1.11.0/root'


def add_vendor_files(root):
    # Unmodified files extracted from the reviewed official Arch archive.
    shutil.copytree(ARCH_FIXTURE, root, dirs_exist_ok=True)
    (root / 'etc/pam.d').mkdir(parents=True, exist_ok=True)


def copy_cosmic_overlay(root):
    shutil.copytree(ROOT / 'packages/starch-cosmic/root', root, dirs_exist_ok=True)


class CosmicTarget(unittest.TestCase):
    def test_live_and_installed_user_defaults_use_the_same_overlay(self):
        stage = load_module('cosmic_stage', ROOT / 'scripts/build/stage-installer.py')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            profile = base / 'profile'
            shutil.copytree(ROOT / 'archiso/profile', profile, symlinks=True)
            stage.stage(profile)
            live = profile / 'airootfs'
            data = live / 'usr/share/starch-installer'
            target = base / 'target'
            for root in (live, target):
                add_media_desktops(root)
            media_defaults.write_defaults(live)
            previous = os.umask(0o077)
            try:
                with patch.object(bootstrap, 'DATA', data):
                    bootstrap.apply_defaults(target)
            finally:
                os.umask(previous)
            self.assertEqual((target / media_defaults.MIMEAPPS).stat().st_mode & 0o777, 0o644)
            installed_login = target / 'etc/greetd/cosmic-greeter.toml'
            cosmic.write_login(target)
            config = tomllib.loads((live / installed_login.relative_to(target)).read_text())
            self.assertEqual(config.pop('initial_session'),
                             {'command': '/usr/bin/start-cosmic', 'user': 'liveuser'})
            self.assertEqual(config, tomllib.loads(installed_login.read_text()))
            for root in (live, target):
                shutil.copytree(root / 'etc/skel', root / 'home/test')
            for overlay in ('desktop-overlays/cosmic', 'rotation-overlay'):
                source = data / overlay
                for path in source.rglob('*'):
                    if path.is_file():
                        for root in (live, target):
                            relative = path.relative_to(source)
                            self.assertEqual((root / relative).read_bytes(), path.read_bytes())
                            if relative.is_relative_to('etc/skel'):
                                self.assertEqual((root / 'home/test' / relative.relative_to('etc/skel')).read_bytes(),
                                                 path.read_bytes())
            self.assertEqual((live / media_defaults.MIMEAPPS).read_bytes(),
                             (target / media_defaults.MIMEAPPS).read_bytes())
            self.assertEqual((target / 'etc/pam.d/starch-greetd').read_bytes(),
                             (live / 'etc/pam.d/starch-greetd').read_bytes())
            self.assertFalse((target / 'etc/starch-live').exists())
            self.assertFalse((target / 'etc/sudoers.d/10-starch-live').exists())

    def test_cosmic_validation_checks_assets_and_rejects_plasma_or_missing_pins(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            add_vendor_files(root)
            copy_cosmic_overlay(root)
            home = root / 'home/test'
            shutil.copytree(root / 'etc/skel', home)
            for name in ('usr/share/wayland-sessions/cosmic.desktop',
                         'usr/share/xdg-desktop-portal/portals/cosmic.portal',
                         'usr/share/xdg-desktop-portal/cosmic-portals.conf',
                         'usr/share/dbus-1/services/org.freedesktop.secrets.service',
                         'usr/share/dbus-1/system.d/com.system76.CosmicGreeter.conf',
                         'usr/lib/sysusers.d/cosmic-greeter.conf',
                         'usr/lib/tmpfiles.d/cosmic-greeter.conf',
                         'usr/share/dbus-1/services/org.freedesktop.impl.portal.desktop.cosmic.service'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('fixture')
            (root / 'usr/share/wayland-sessions/cosmic.desktop').write_text(
                '[Desktop Entry]\nExec=/usr/bin/start-cosmic\n')
            for entry in cosmic.PINS:
                path = root / 'usr/share/applications' / (entry + '.desktop')
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('[Desktop Entry]\n')
            add_media_desktops(root)
            media_defaults.write_defaults(root)
            (root / 'etc/pam.d/sddm').write_text('auth include system-login\n')
            for manager in ('greetd', 'sddm', 'lightdm'):
                mask = root / ('etc/systemd/system/' + manager + '.service')
                mask.parent.mkdir(parents=True, exist_ok=True)
                mask.symlink_to('/dev/null')
            with patch.object(cosmic, 'chroot') as calls:
                cosmic.configure(root)
                cosmic.validate(root, home)
                credentials = ('setpriv', '--reuid=cosmic-greeter',
                               '--regid=cosmic-greeter', '--init-groups', '--')
                calls.assert_any_call(root, *credentials, 'test', '-x', cosmic.GREETER_COMMAND)
                calls.assert_any_call(root, *credentials, 'sh', '-n', cosmic.GREETER_COMMAND)
                self.assertFalse(any('runuser' in c.args for c in calls.call_args_list))
                calls.assert_any_call(root, 'test', '-r', '/etc/pam.d/login')
                calls.assert_any_call(root, 'test', '-x', '/usr/bin/cosmic-osd')
                calls.assert_any_call(root, 'test', '/etc/systemd/system/display-manager.service',
                                      '-ef', '/usr/lib/systemd/system/cosmic-greeter.service')
                for removed in ('auth include system-local-login',
                                'account include system-local-login',
                                'session include system-local-login',
                                'auth optional pam_gnome_keyring.so',
                                'session optional pam_gnome_keyring.so auto_start'):
                    pam_path = root / 'etc/pam.d/starch-greetd'
                    original = pam_path.read_text()
                    pam_path.write_text(original.replace(removed, '# missing'))
                    with self.assertRaisesRegex(RuntimeError, 'PAM'):
                        cosmic.validate(root, home)
                    pam_path.write_text(original)
                agent = root / 'etc/xdg/autostart/polkit-gnome-authentication-agent-1.desktop'
                agent.parent.mkdir(parents=True, exist_ok=True)
                agent.write_text('[Desktop Entry]')
                with self.assertRaisesRegex(RuntimeError, 'Redundant GNOME polkit'):
                    cosmic.validate(root, home)
                agent.unlink()
                foreign = root / cosmic.SESSION_DIR / 'starch-lite.desktop'
                foreign.write_text('[Desktop Entry]\nExec=startplasma-wayland\n')
                with self.assertRaisesRegex(RuntimeError, 'only the installed COSMIC session'):
                    cosmic.validate(root, home)
                foreign.unlink()
                (home / '.config/kwinrc').write_text('[Wayland]\n')
                with self.assertRaisesRegex(RuntimeError, 'Plasma defaults'):
                    cosmic.validate(root, home)
                (home / '.config/kwinrc').unlink()
                mimeapps = root / media_defaults.MIMEAPPS
                valid_mimeapps = mimeapps.read_text()
                mimeapps.write_text(valid_mimeapps.replace(
                    'image/png=com.system76.CosmicViewer.desktop', 'image/png=vlc.desktop'))
                with self.assertRaisesRegex(RuntimeError, 'media defaults'):
                    cosmic.validate(root, home)
                mimeapps.write_text(valid_mimeapps)
                (root / 'usr/share/applications/firefox.desktop').unlink()
                with self.assertRaisesRegex(RuntimeError, 'dock application'):
                    cosmic.validate(root, home)

    def test_greeter_launcher_remains_accessible_with_restrictive_installer_umask(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            add_vendor_files(root)
            desktop = root / cosmic.SESSION_DIR / 'cosmic.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('[Desktop Entry]\nExec=/usr/bin/start-cosmic\n')
            # Match installed package parents before Calamares creates its
            # target-only launcher directory under a private umask.
            (root / 'usr/lib').mkdir(parents=True, exist_ok=True)
            previous = os.umask(0o077)
            try:
                with patch.object(cosmic, 'chroot'):
                    cosmic.configure(root)
            finally:
                os.umask(previous)
            launcher = root / cosmic.GREETER_COMMAND.lstrip('/')
            self.assertEqual(launcher.parent.stat().st_mode & 0o777, 0o755)
            self.assertEqual(launcher.stat().st_mode & 0o777, 0o755)
            self.assertTrue(launcher.stat().st_mode & 0o004)

    @unittest.skipUnless(shutil.which('systemctl'), 'requires offline systemctl')
    def test_native_greeter_can_be_enabled_as_systemd_display_manager(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            add_vendor_files(root)
            desktop = root / cosmic.SESSION_DIR / 'cosmic.desktop'
            desktop.parent.mkdir(parents=True)
            desktop.write_text('[Desktop Entry]\nExec=/usr/bin/start-cosmic\n')
            old = root / 'etc/systemd/system/display-manager.service'
            old.parent.mkdir(parents=True)
            old.symlink_to('/usr/lib/systemd/system/sddm.service')
            with patch.object(cosmic, 'chroot'):
                cosmic.configure(root)
            masked = subprocess.run(['systemctl', '--root', str(root), 'mask',
                                     'sddm.service', 'lightdm.service', 'greetd.service'],
                                    capture_output=True, text=True)
            self.assertEqual(masked.returncode, 0, masked.stderr)
            result = subprocess.run(['systemctl', '--root', str(root), 'enable', '--force',
                                     'cosmic-greeter.service'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            alias = root / 'etc/systemd/system/display-manager.service'
            self.assertTrue(alias.is_symlink())
            self.assertTrue(str(alias.readlink()).endswith('/cosmic-greeter.service'))
            for manager in ('sddm', 'lightdm', 'greetd'):
                self.assertEqual((root / ('etc/systemd/system/' + manager + '.service')).readlink(),
                                 Path('/dev/null'))
            self.assertEqual(str(alias.readlink()), '/usr/lib/systemd/system/cosmic-greeter.service')
            for unit in ('cosmic-greeter.service', 'cosmic-greeter-daemon.service'):
                self.assertFalse((root / 'etc/systemd/system' / unit).exists())
                self.assertEqual((root / 'usr/lib/systemd/system' / unit).read_bytes(),
                                 (ARCH_FIXTURE / 'usr/lib/systemd/system' / unit).read_bytes())
            vendor = (root / 'usr/lib/systemd/system/cosmic-greeter.service').read_text()
            self.assertIn('Wants=cosmic-greeter-daemon.service', vendor)
            self.assertIn('kmsconvt@tty1.service', vendor)

    def test_vendor_units_reject_missing_files_and_preserve_local_overrides(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(RuntimeError, 'Missing packaged'):
                cosmic.validate_vendor_units(root)
            add_vendor_files(root)
            cosmic.validate_vendor_units(root)
            for directory in ('etc/systemd/system', 'run/systemd/system'):
                override = root / directory / 'cosmic-greeter.service'
                override.parent.mkdir(parents=True, exist_ok=True)
                override.write_text('administrator configuration')
                with self.assertRaisesRegex(RuntimeError, 'Review existing'):
                    cosmic.validate_vendor_units(root)
                self.assertEqual(override.read_text(), 'administrator configuration')
                override.unlink()
                override.symlink_to('/nonexistent')
                with self.assertRaisesRegex(RuntimeError, 'Review existing'):
                    cosmic.validate_vendor_units(root)
                self.assertTrue(override.is_symlink())
                override.unlink()


if __name__ == '__main__':
    unittest.main()
