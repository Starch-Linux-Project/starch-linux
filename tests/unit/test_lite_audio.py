"""Offline contracts for upstream Artix audio; runtime acceptance requires a VM."""
import io
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import bootstrap
import lite
import profiles

FIXTURE = ROOT / 'tests/fixtures/lite-artix-user-services'
PAYLOAD = ROOT / 'packages/starch-lite/integration/root'


class UpstreamAudio(unittest.TestCase):
    def target(self, root):
        shutil.copytree(FIXTURE / 'etc', root / 'etc')
        shutil.copytree(PAYLOAD, root, dirs_exist_ok=True)
        for path in (root / 'etc/user/init.d').iterdir():
            path.chmod(0o755)
        lite.seed_user_services(root)

    def test_reviewed_upstream_services_and_pam_validate_without_rewrites(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(lite, 'chroot') as calls:
            root = Path(directory)
            self.target(root)
            before = {p.name: p.read_bytes() for p in (root / 'etc/pam.d').iterdir()}
            lite.validate_user_services(root)
            self.assertEqual(before, {p.name: p.read_bytes() for p in (root / 'etc/pam.d').iterdir()})
            calls.assert_any_call(root, 'test', '-f', '/usr/lib/security/pam_openrc.so')
            self.assertFalse(any('systemctl' in str(c) for c in calls.call_args_list))

    @unittest.skipUnless(shutil.which('pacman'), 'pacman is required')
    def test_intentionally_removed_getty_does_not_fail_audio_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.target(root)
            database = root / 'db'
            package = database / 'local/openrc-1-1'
            package.mkdir(parents=True)
            (database / 'local/ALPM_DB_VERSION').write_text('9\n')
            (package / 'desc').write_text('%NAME%\nopenrc\n\n%VERSION%\n1-1\n\n%DESC%\nTest\n\n%ARCH%\nx86_64\n')
            (package / 'files').write_text('%FILES%\nusr/bin/openrc\netc/runlevels/default/agetty.tty1\n')
            binary = root / 'usr/bin/openrc'
            binary.parent.mkdir(parents=True)
            binary.touch()
            result = subprocess.run(['pacman', '--root', str(root), '--dbpath', str(database),
                                     '-Qk', 'openrc'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1, result.stderr)
            self.assertIn('agetty.tty1', result.stderr)
            def chroot(target, *args):
                if args[:2] == ('pacman', '-Qk') and 'openrc' in args[2:]:
                    raise RuntimeError('openrc has intentionally removed getty links')
            with patch.object(lite, 'chroot', side_effect=chroot):
                lite.validate_user_services(root)
            with patch.object(lite, 'output', return_value='/usr/bin/openrc\n/etc/runlevels/default/agetty.tty1\n'):
                lite.validate_openrc_files(root)
                binary.unlink()
                with self.assertRaises(RuntimeError):
                    lite.validate_openrc_files(root)

    def test_missing_pam_dependency_or_supervision_and_stale_files_fail(self):
        cases = {
            'pam': ('etc/pam.d/system-login', 'pam_openrc.so', 'missing.so'),
            'elogind': ('etc/pam.d/system-login', 'pam_elogind.so', 'missing.so'),
            'lightdm': ('etc/pam.d/lightdm', 'session     include     system-login', '# removed'),
            'dependency': ('etc/user/init.d/wireplumber', 'need pipewire dbus', 'need dbus'),
            'supervisor': ('etc/user/init.d/pipewire', 'supervisor=supervise-daemon', '# disabled'),
            'disabled': ('etc/rc.conf', '#rc_autostart_user="YES"', 'rc_autostart_user="NO"'),
        }
        for case, (name, old, new) in cases.items():
            with self.subTest(case=case), tempfile.TemporaryDirectory() as directory, patch.object(lite, 'chroot'):
                root = Path(directory)
                self.target(root)
                p = root / name
                self.assertIn(old, p.read_text())
                p.write_text(p.read_text().replace(old, new))
                with self.assertRaises(RuntimeError):
                    lite.validate_user_services(root)
        for name in ('usr/lib/starch-lite/audio-session', 'etc/xdg/autostart/starch-audio.desktop',
                     'etc/skel/.config/autostart/custom.desktop'):
            with self.subTest(stale=name), tempfile.TemporaryDirectory() as directory, patch.object(lite, 'chroot'):
                root = Path(directory)
                self.target(root)
                p = root / name
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_text('Exec=/usr/lib/starch-lite/audio-session\n')
                with self.assertRaises(RuntimeError):
                    lite.validate_user_services(root)

    def test_competing_direct_autostart_and_system_audio_service_are_rejected(self):
        for system in (False, True):
            with self.subTest(system=system), tempfile.TemporaryDirectory() as directory, patch.object(lite, 'chroot'):
                root = Path(directory)
                self.target(root)
                if system:
                    path = root / 'etc/runlevels/default/pipewire'
                    path.parent.mkdir(parents=True)
                    path.symlink_to('/etc/init.d/pipewire')
                else:
                    path = root / 'etc/xdg/autostart/pipewire.desktop'
                    path.parent.mkdir(parents=True)
                    path.write_text('[Desktop Entry]\nExec=/usr/bin/pipewire\n')
                with self.assertRaises(RuntimeError):
                    lite.validate_user_services(root)

    def test_user_runlevels_survive_account_copy_and_repeated_seeding(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.target(root)
            lite.seed_user_services(root)
            home = root / 'home/test'
            shutil.copytree(root / 'etc/skel', home, symlinks=True)
            lite.validate_user_runlevels(root, home, os.getuid(), os.getgid())
            with self.assertRaises(RuntimeError):
                lite.validate_user_runlevels(root, home, os.getuid() + 1, os.getgid())
            link = home / '.config/rc/runlevels/default/pipewire'
            link.unlink()
            link.symlink_to('/etc/init.d/pipewire')
            with self.assertRaises(RuntimeError):
                lite.validate_user_runlevels(root, home)
            seed = root / 'etc/skel/.config/rc/runlevels/boot/dbus'
            seed.unlink()
            seed.write_text('administrator setting')
            with self.assertRaises(RuntimeError):
                lite.seed_user_services(root)
            self.assertEqual(seed.read_text(), 'administrator setting')

    def test_bootstrap_seeds_before_users_without_starting_services(self):
        class Selection:
            def value(self, name):
                return {'starchLite': True, 'starchDesktop': 'xfce'}.get(name)
        with tempfile.TemporaryDirectory() as directory, patch.object(lite, 'chroot') as calls:
            root = Path(directory) / 'target'
            data = Path(directory) / 'data'
            self.target(root)
            binary = data / 'target-overlay/usr/local/bin/linux-update-utility.AppImage'
            binary.parent.mkdir(parents=True)
            binary.touch()
            with patch.object(bootstrap, 'DATA', data):
                bootstrap.apply_defaults(root, Selection())
            lite.validate_user_runlevels(root, root / 'etc/skel')
            calls.assert_not_called()

    def test_payload_keeps_unrelated_defaults_and_no_old_audio_references(self):
        for name in ('etc/init.d/starch-banner', 'etc/init.d/starch-zram',
                     'etc/sysctl.d/99-low-ram.conf', 'etc/rc.conf.d/starch.conf',
                     'usr/lib/starch-lite/xfce-defaults',
                     'usr/share/xfce4/helpers/starch-cosmic-terminal.desktop'):
            self.assertTrue((PAYLOAD / name).is_file(), name)
            original = subprocess.check_output(['git', 'show', 'HEAD:packages/starch-lite/integration/root/' + name], cwd=ROOT)
            self.assertEqual((PAYLOAD / name).read_bytes(), original)
        for p in PAYLOAD.rglob('*'):
            if p.is_file():
                self.assertNotIn('starch-lite/audio-session', p.read_text(), str(p))
                self.assertNotEqual(p.name, 'starch-audio.desktop')

    def test_archive_rejects_old_version_and_removed_payload_even_with_new_identity(self):
        for version, stale in [('0.2.2-16', None), ('0.2.2-17', 'usr/lib/starch-lite/audio-session'),
                               ('0.2.2-17', 'usr/share/starch-lite/xfce-config/autostart/starch-audio.desktop'),
                               ('0.2.2-17', None)]:
            with self.subTest(version=version, stale=stale), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / 'starch-lite.pkg.tar'
                with tarfile.open(path, 'w') as archive:
                    data = f'pkgname = starch-lite\npkgver = {version}\n'.encode()
                    info = tarfile.TarInfo('.PKGINFO')
                    info.size = len(data)
                    archive.addfile(info, io.BytesIO(data))
                    if stale:
                        archive.addfile(tarfile.TarInfo(stale))
                if version.endswith('-16') or stale:
                    with self.assertRaises(RuntimeError):
                        profiles.verify_lite_archive(path)
                else:
                    profiles.verify_lite_archive(path)
