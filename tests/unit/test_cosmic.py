import configparser
import hashlib
import importlib.machinery
import importlib.util
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import tomllib
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import bootstrap
import configure
import cosmic
import lite
import media_defaults
import profiles
from test_desktop_selection import Storage


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


class CosmicTarget(unittest.TestCase):
    def test_staged_defaults_are_selected_before_user_creation_and_leave_live_unchanged(self):
        stage = load_module('cosmic_stage', ROOT / 'scripts/build/stage-installer.py')
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            profile = base / 'profile'
            shutil.copytree(ROOT / 'archiso/profile', profile, symlinks=True)
            stage.stage(profile)
            data = profile / 'airootfs/usr/share/starch-installer'
            self.assertEqual((data / 'rotation-overlay/usr/lib/starch/rotation.py').read_bytes(),
                             (ROOT / 'packages/starch-rotation/root/usr/lib/starch/rotation.py').read_bytes())
            self.assertEqual((profile / 'airootfs/usr/lib/starch-installer/cosmic.py').read_bytes(),
                             (ROOT / 'scripts/installer/cosmic.py').read_bytes())
            self.assertFalse(list((data / 'desktop-overlays').rglob('__pycache__')))
            self.assertFalse(list((data / 'desktop-overlays').rglob('*.pyc')))
            # Supply the external LUU fixture normally staged by release builds.
            appimage = data / 'target-overlay/usr/local/bin/linux-update-utility.AppImage'
            appimage.parent.mkdir(parents=True, exist_ok=True)
            appimage.touch()
            self.assertFalse((profile / 'airootfs/etc/skel/.config/cosmic').exists())
            for init, desktop in ((False, 'plasma'), (True, 'plasma'), (True, 'xfce'),
                                  (False, 'cosmic'), (True, 'cosmic')):
                root = base / (str(init) + desktop)
                root.mkdir()
                if desktop == 'xfce':
                    panel = root / 'usr/share/starch-lite/xfce-panel.xml'
                    panel.parent.mkdir(parents=True)
                    panel.write_text('<channel/>')
                if desktop == 'cosmic':
                    add_media_desktops(root)
                    mimeapps = root / media_defaults.MIMEAPPS
                    mimeapps.parent.mkdir(parents=True, exist_ok=True)
                    mimeapps.write_text('[Default Applications]\napplication/pdf=documents.desktop\n')
                with patch.object(bootstrap, 'DATA', data):
                    bootstrap.apply_defaults(root, Storage(starchLite=init, starchDesktop=desktop))
                self.assertEqual((root / 'etc/skel/.config/cosmic').is_dir(), desktop == 'cosmic')
                self.assertEqual((root / 'etc/skel/.config/kwinrc').is_file(), desktop == 'plasma')
                self.assertEqual((root / 'usr/lib/starch-cosmic/session').is_file(), init and desktop == 'cosmic')
                self.assertEqual((root / 'usr/lib/starch/rotation.py').is_file(),
                                 not init and desktop == 'cosmic')
                self.assertEqual((root / 'etc/xdg/autostart/starch-rotation.desktop').is_file(),
                                 not init and desktop == 'cosmic')
                osk = root / 'etc/skel/.local/state/cosmic/com.system76.CosmicOSK/v1/ime_activation'
                self.assertEqual(osk.is_file(), desktop == 'cosmic')
                if desktop == 'cosmic':
                    self.assertEqual(osk.read_text().strip(), 'false')
                    defaults = configparser.ConfigParser(interpolation=None)
                    defaults.read(root / media_defaults.MIMEAPPS)
                    self.assertEqual(defaults['Default Applications']['image/png'], media_defaults.VIEWER)
                    self.assertEqual(defaults['Default Applications']['image/gif'], media_defaults.VIEWER)
                    self.assertEqual(defaults['Default Applications']['video/mp4'], media_defaults.VLC)
                    self.assertEqual(defaults['Default Applications']['audio/mpeg'], media_defaults.VLC)
                    self.assertEqual(defaults['Default Applications']['image/vnd.rn-realpix'], media_defaults.VLC)
                    self.assertEqual(defaults['Default Applications']['application/pdf'], 'documents.desktop')
                    background = root / 'etc/skel/.config/cosmic/com.system76.CosmicBackground/v1/all'
                    self.assertIn('Path("/usr/share/backgrounds/starch/evergreen.jpg")',
                                  background.read_text())
                self.assertTrue((root / 'etc/nftables.conf').is_file())
                self.assertTrue((root / 'usr/share/starch/splash-starch.bmp').is_file())
                if desktop == 'plasma':
                    self.assertEqual((root / 'etc/skel/.config/kwinrc').read_bytes(),
                                     (ROOT / 'archiso/profile/airootfs/etc/skel/.config/kwinrc').read_bytes())

    def test_cosmic_uses_native_greeter_authenticated_session_and_unchanged_init(self):
        for is_lite in (False, True):
            with self.subTest(lite=is_lite), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / 'packages/starch-cosmic/root', root, dirs_exist_ok=True)
                session = root / 'usr/share/wayland-sessions/cosmic.desktop'
                session.parent.mkdir(parents=True)
                session.write_text('[Desktop Entry]\nExec=/usr/bin/start-cosmic\nDesktopNames=COSMIC\n')
                (root / 'etc/pam.d/sddm').write_text('auth include system-login\n-session optional pam_kwallet5.so auto_start\n')
                (root / 'etc/fstab').write_text('UUID=test / ext4 defaults 0 1\n')
                with patch.object(configure, 'target', return_value=root), \
                     patch.object(configure, 'chroot') as common, \
                     patch.object(lite, 'configure') as lite_configure, \
                     patch.object(cosmic, 'chroot') as calls:
                    configure.run(Storage(starchLite=is_lite, starchDesktop='cosmic', firmwareType='bios'))
                config = tomllib.loads((root / 'etc/greetd/cosmic-greeter.toml').read_text())
                # Account creation must finish before tmpfiles resolves its
                # ownership and before the greeter services are enabled.
                self.assertEqual(calls.call_args_list[0].args,
                                 (root, 'esysusers' if is_lite else 'systemd-sysusers',
                                  '/usr/lib/sysusers.d/cosmic-greeter.conf'))
                self.assertEqual(calls.call_args_list[1].args,
                                 (root, 'etmpfiles' if is_lite else 'systemd-tmpfiles',
                                  '--create', '/usr/lib/tmpfiles.d/cosmic-greeter.conf'))
                self.assertEqual(config['default_session']['command'], cosmic.GREETER_COMMAND)
                self.assertEqual(config['default_session']['user'], 'cosmic-greeter')
                self.assertEqual(config['general']['service'], 'starch-greetd')
                self.assertNotIn('initial_session', config)
                self.assertFalse((root / 'etc/sddm.conf').exists())
                self.assertFalse((root / 'etc/sddm.conf.d/10-starch.conf').exists())
                self.assertIn('session include system-local-login',
                              (root / 'etc/pam.d/starch-greetd').read_text())
                greeter = root / cosmic.GREETER_COMMAND.lstrip('/')
                self.assertTrue(os.access(greeter, os.X_OK))
                self.assertIn('cosmic-comp /usr/bin/cosmic-greeter', greeter.read_text())
                subprocess.run(['sh', '-n', str(greeter)], check=True)
                selected = (root / cosmic.SESSION_DIR / 'cosmic.desktop').read_text()
                self.assertIn('Exec=' + ('/usr/lib/starch-cosmic/session' if is_lite else '/usr/bin/start-cosmic'), selected)
                self.assertNotIn('plasma', selected)
                hooks = (root / 'etc/mkinitcpio.conf.d/10-starch.conf').read_text()
                self.assertEqual('systemd' in hooks, not is_lite)
                if is_lite:
                    lite_configure.assert_called_once_with(root, xfce=False, cosmic=True)
                    self.assertFalse(any('systemctl' in call.args for call in calls.call_args_list))
                    calls.assert_any_call(root, 'rc-update', 'add', 'cosmic-greeter', 'default')
                    calls.assert_any_call(root, 'rc-update', 'add', 'cosmic-greeter-daemon', 'default')
                else:
                    lite_configure.assert_not_called()
                    calls.assert_any_call(root, 'systemctl', 'mask', 'greetd.service', 'sddm.service', 'lightdm.service')
                    calls.assert_any_call(root, 'systemctl', 'enable', '--force', 'cosmic-greeter.service')
                    self.assertFalse(any('sddm.service' in c.args and 'enable' in c.args
                                         for c in common.call_args_list))
                    common.assert_any_call(
                        root, 'systemctl', 'enable', 'NetworkManager.service',
                        'nftables.service', 'power-profiles-daemon.service', 'bluetooth.service')
                    calls.assert_any_call(root, 'systemctl', '--global', 'enable', 'pipewire.socket',
                                          'pipewire-pulse.socket', 'wireplumber.service')

    def test_cosmic_validation_checks_assets_and_rejects_plasma_or_missing_pins(self):
        for is_lite in (False, True):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                shutil.copytree(ROOT / 'packages/starch-cosmic/root', root, dirs_exist_ok=True)
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
                if not is_lite:
                    for manager in ('greetd', 'sddm', 'lightdm'):
                        mask = root / ('etc/systemd/system/' + manager + '.service')
                        mask.parent.mkdir(parents=True, exist_ok=True)
                        mask.symlink_to('/dev/null')
                else:
                    for name in ('cosmic-greeter', 'cosmic-greeter-daemon'):
                        link = root / 'etc/runlevels/default' / name
                        link.parent.mkdir(parents=True, exist_ok=True)
                        link.symlink_to('/etc/init.d/' + name)
                with patch.object(cosmic, 'chroot') as calls:
                    cosmic.configure(root, lite=is_lite)
                    cosmic.validate(root, home, lite=is_lite)
                    credentials = ('setpriv', '--reuid=cosmic-greeter',
                                   '--regid=cosmic-greeter', '--init-groups', '--')
                    calls.assert_any_call(root, *credentials, 'test', '-x', cosmic.GREETER_COMMAND)
                    calls.assert_any_call(root, *credentials, 'sh', '-n', cosmic.GREETER_COMMAND)
                    self.assertFalse(any('runuser' in c.args for c in calls.call_args_list))
                    foreign = root / cosmic.SESSION_DIR / 'starch-lite.desktop'
                    foreign.write_text('[Desktop Entry]\nExec=startplasma-wayland\n')
                    with self.assertRaisesRegex(RuntimeError, 'only the installed COSMIC session'):
                        cosmic.validate(root, home, lite=is_lite)
                    foreign.unlink()
                    (home / '.config/kwinrc').write_text('[Wayland]\n')
                    with self.assertRaisesRegex(RuntimeError, 'Plasma defaults'):
                        cosmic.validate(root, home, lite=is_lite)
                    (home / '.config/kwinrc').unlink()
                    mimeapps = root / media_defaults.MIMEAPPS
                    valid_mimeapps = mimeapps.read_text()
                    mimeapps.write_text(valid_mimeapps.replace(
                        'image/png=com.system76.CosmicViewer.desktop', 'image/png=vlc.desktop'))
                    with self.assertRaisesRegex(RuntimeError, 'media defaults'):
                        cosmic.validate(root, home, lite=is_lite)
                    mimeapps.write_text(valid_mimeapps)
                    (root / 'usr/share/applications/firefox.desktop').unlink()
                    with self.assertRaisesRegex(RuntimeError, 'dock application'):
                        cosmic.validate(root, home, lite=is_lite)

    def test_greeter_launcher_remains_accessible_with_restrictive_installer_umask(self):
        for is_lite in (False, True):
            with self.subTest(lite=is_lite), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                desktop = root / cosmic.SESSION_DIR / 'cosmic.desktop'
                desktop.parent.mkdir(parents=True)
                desktop.write_text('[Desktop Entry]\nExec=/usr/bin/start-cosmic\n')
                # Match installed package parents before Calamares creates its
                # target-only launcher directory under a private umask.
                (root / 'usr/lib').mkdir(parents=True)
                previous = os.umask(0o077)
                try:
                    with patch.object(cosmic, 'chroot'):
                        cosmic.configure(root, lite=is_lite)
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
            self.assertIn('Requires=cosmic-greeter-daemon.service',
                          (root / 'etc/systemd/system/cosmic-greeter.service').read_text())

    def test_lite_cosmic_never_applies_plasma_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'packages/starch-lite/integration/root', root, dirs_exist_ok=True)
            (root / 'etc/hostname').write_text('cosmic-test\n')
            (root / 'etc/vconsole.conf').write_text('KEYMAP=us\n')
            (root / 'etc/conf.d').mkdir(parents=True, exist_ok=True)
            (root / 'etc/conf.d/agetty').write_text('term_type=linux\n')
            with patch.object(lite, 'chroot') as calls:
                lite.configure(root, cosmic=True)
            for name in ('startkderc', 'kwinrc', 'kdeglobals', 'autostart/starch-audio.desktop'):
                self.assertFalse((root / 'etc/xdg' / name).exists())
            self.assertFalse((root / 'etc/sddm.conf.d/20-starch-lite.conf').exists())
            self.assertFalse(any('sddm' in c.args for c in calls.call_args_list))
            calls.assert_any_call(root, 'rc-update', 'add', 'elogind', 'boot')
            self.assertFalse((root / 'etc/init.d/iio-sensor-proxy').exists())
            self.assertFalse(any('iio-sensor-proxy' in c.args for c in calls.call_args_list))
            self.assertFalse(any('systemctl' in call.args for call in calls.call_args_list))

    def test_legacy_lite_defaults_are_byte_for_byte_preserved(self):
        # Snapshot of the pre-COSMIC defaults; independent of repository HEAD.
        expected = {
            'autostart/starch-audio.desktop': '58e6b43a2bce6fb97bc7511daad890a594ba3ff0b6a448f3406c5929f1c56c31',
            'breezerc': '31b65f1205f438fa1e4de5cbdc2e668f8adda66d26cd63461ba65bcbf1b45f6b',
            'kalendaracrc': 'eda5a82185425485dc3d4e1767117848033d9e495efa8ae0941a202fc3d5ff33',
            'kdeglobals': '22c69c1a3f7ab4125df2a201d93d35e611f534b6c478aa809331ebd37eea83a5',
            'korgacrc': 'eda5a82185425485dc3d4e1767117848033d9e495efa8ae0941a202fc3d5ff33',
            'ksmserverrc': 'ecd26c749a1a5f132309ef12c43b6e4a5156033c26402052ea68ca99874a8094',
            'kwinrc': '667e0766ba1f91ccc37c16dd6738a4c8ba35da8b413087b888b0d3c2249034e3',
            'startkderc': '288fba7d21ac0e1ba74da8c046e18c7077f92d92028346467affc6ffe1db97dd',
        }
        location = ROOT / 'packages/starch-lite/integration/root/usr/share/starch-lite/legacy-desktop-config'
        self.assertEqual({path.relative_to(location).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in location.rglob('*') if path.is_file()}, expected)

    def test_supervisor_only_terminates_its_own_process_group(self):
        session = load_module('cosmic_session', ROOT / 'packages/starch-cosmic/lite-root/usr/lib/starch-cosmic/session')
        unrelated = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], start_new_session=True)
        try:
            session.stop(child)
            self.assertIsNotNone(child.poll())
            self.assertIsNone(unrelated.poll())
        finally:
            for proc in (child, unrelated):
                if proc.poll() is None:
                    os.killpg(proc.pid, signal.SIGKILL)
                    proc.wait()

    def test_profile_radios_are_exclusive_and_write_existing_storage_contract(self):
        page = (ROOT / 'packages/calamares/0005-starch-advanced-page.patch').read_text()
        self.assertIn('group->setExclusive( true );', page)
        self.assertIn('group->addButton( button );', page)
        self.assertIn('storage->insert( "starchDesktop", desktop );', page)
        for legacy_xfce in (False, True):
            with self.assertRaises(RuntimeError):
                profiles.validate_selection(Storage(starchLite=True, starchDesktop='cosmic', starchLiteXfce=legacy_xfce))


if __name__ == '__main__':
    unittest.main()
