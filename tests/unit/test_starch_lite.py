import hashlib
import configparser
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import bootstrap
import configure
import graphics
import limine
import lite
import preflight
import profiles
import repositories

spec = importlib.util.spec_from_file_location('stage_lite_test', ROOT / 'scripts/build/stage-installer.py')
stage = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


class Storage:
    def __init__(self, **values):
        self.values = values

    def value(self, name):
        return self.values.get(name)


def bundle(root):
    root.mkdir(parents=True, exist_ok=True)
    entries = []
    for name in profiles.LITE_BUNDLE_PACKAGES:
        filename = f'{name}-1.0-1-x86_64.pkg.tar.zst'
        content = name.encode()
        (root / filename).write_bytes(content)
        entries.append(dict(name=name, filename=filename, sha256=hashlib.sha256(content).hexdigest()))
    (root / 'bundle.json').write_text(json.dumps(dict(format=2, repositories='artix-arch-extra', packages=entries)))
    return entries


class LiteProfile(unittest.TestCase):
    def test_openrc_validation_allows_only_intentionally_removed_gettys(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binary = root / 'usr/bin/openrc'
            binary.parent.mkdir(parents=True)
            binary.touch()
            tty1 = root / 'etc/runlevels/default/agetty.tty1'
            tty1.parent.mkdir(parents=True)
            tty1.symlink_to('/etc/init.d/agetty.tty1')
            files = ['/usr/bin/openrc'] + [f'/etc/runlevels/default/agetty.tty{n}' for n in range(1, 7)]
            with patch.object(lite, 'output', return_value='\n'.join(files)):
                lite.validate_openrc_files(root)
                binary.unlink()
                with self.assertRaisesRegex(RuntimeError, 'Missing OpenRC package file: /usr/bin/openrc'):
                    lite.validate_openrc_files(root)
                binary.touch()
                tty1.unlink()
                with self.assertRaisesRegex(RuntimeError, 'agetty.tty1'):
                    lite.validate_openrc_files(root)

    def test_xfce_extension_requires_lite_and_changes_selection_identity(self):
        self.assertFalse(profiles.has_xfce(Storage(starchLite=False, starchLiteXfce=True)))
        self.assertEqual(profiles.profile_name(Storage(starchLite=True)), 'lite')
        self.assertEqual(profiles.profile_name(Storage(starchLite=True, starchLiteXfce=True)), 'lite-xfce')
        base = ['linux-lts', 'plasma-desktop']
        self.assertNotIn('xfce4-session', profiles.lite_packages(base))
        selected = profiles.lite_packages(base, xfce=True)
        self.assertNotIn('plasma-desktop', selected)
        self.assertTrue(profiles.PLASMA_PACKAGES.isdisjoint(selected))
        for package in ('linux-zen', 'xfce4-session', 'xorg-server',
                        'network-manager-applet', 'xfce4-screensaver'):
            self.assertIn(package, selected)

    def test_xfce_replaces_all_plasma_packages_in_real_manifest(self):
        base = preflight.read_manifest(ROOT / 'manifests/minimal-packages.txt')
        plasma = profiles.lite_packages(base)
        xfce = profiles.lite_packages(base, xfce=True)
        self.assertTrue(profiles.PLASMA_PACKAGES.isdisjoint(xfce))
        self.assertTrue(profiles.PLASMA_PACKAGES.issubset(plasma))
        for package in ('pipewire', 'wireplumber', 'networkmanager', 'nftables',
                        'sddm', 'firefox', 'linux-zen'):
            self.assertIn(package, xfce)
        for package in ('xfce4-terminal', 'thunar', 'polkit-gnome', 'xdg-desktop-portal-gtk'):
            self.assertIn(package, xfce)
        self.assertNotIn('nautilus', xfce)

    def test_xfce_configuration_enables_only_xfce(self):
        import shutil
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copytree(ROOT / 'packages/starch-lite/integration/root', root, dirs_exist_ok=True)
            (root / 'etc/hostname').write_text('starch-test\n')
            (root / 'etc/vconsole.conf').write_text('KEYMAP=us\n')
            native = root / 'usr/share/xsessions/xfce.desktop'
            native.parent.mkdir(parents=True)
            native.write_text('[Desktop Entry]\nExec=startxfce4\nDesktopNames=XFCE\n')
            (root / 'etc/conf.d').mkdir(parents=True, exist_ok=True)
            (root / 'etc/conf.d/agetty').write_text('term_type=linux\n')
            (root / 'etc/sddm.conf').write_text(
                '[Autologin]\nUser=\nSession=\nRelogin=false\n'
                '[Wayland]\nSessionDir=/usr/share/wayland-sessions\n')
            with patch.object(lite, 'chroot') as calls:
                lite.configure(root, xfce=True)
            self.assertEqual((root / 'usr/share/starch-lite/xsessions/starch-xfce.desktop').read_text(),
                             native.read_text())
            self.assertTrue((root / 'etc/conf.d/agetty.tty2').is_file())
            calls.assert_any_call(root, 'rc-update', 'add', 'agetty.tty2', 'boot')
            self.assertNotIn('agetty.tty1', lite.enabled_services(True)['default'])
            self.assertIn('SessionDir=/usr/share/starch-lite/xsessions',
                          (root / 'etc/sddm.conf.d/30-starch-xfce.conf').read_text())
            self.assertEqual((root / 'var/lib/sddm/state.conf').read_text(),
                             '[Last]\nSession=starch-xfce.desktop\n')
            self.assertIn('OnlyShowIn=KDE;XFCE;',
                          (root / 'etc/xdg/autostart/starch-audio.desktop').read_text())
            self.assertFalse((root / 'usr/share/starch-lite/wayland-sessions/starch-lite.desktop').exists())
            self.assertIn('DisplayServer=x11', (root / 'etc/sddm.conf.d/10-starch.conf').read_text())
            config = configparser.ConfigParser()
            config.read(root / 'etc/sddm.conf')
            self.assertEqual(config['Wayland']['SessionDir'],
                             '/usr/share/starch-lite/no-wayland-sessions')
            self.assertEqual(config['X11']['SessionDir'], '/usr/share/starch-lite/xsessions')
            self.assertEqual(config['Autologin']['User'], '')
            self.assertEqual(list((root / 'usr/share/starch-lite/no-wayland-sessions').iterdir()), [])

    def test_audio_supervisor_starts_services_in_dependency_order(self):
        package_root = ROOT / 'packages/starch-lite/integration/root'
        desktop = configparser.ConfigParser(interpolation=None)
        desktop.read(package_root / 'etc/xdg/autostart/starch-audio.desktop')
        entry = desktop['Desktop Entry']
        self.assertEqual(entry['OnlyShowIn'], 'KDE;')
        self.assertEqual(entry['TryExec'], entry['Exec'])
        supervisor = package_root / entry['Exec'].lstrip('/')
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            binaries = root / 'bin'
            runtime = root / 'run'
            home = root / 'home'
            binaries.mkdir()
            runtime.mkdir()
            home.mkdir()
            service = binaries / 'audio-fake'
            service.write_text(
                '#!/usr/bin/python3\n'
                'import os, pathlib, signal, sys, time\n'
                'name = pathlib.Path(sys.argv[0]).name\n'
                'with open(os.environ["EVENT_LOG"], "a") as log: log.write(name + "\\n")\n'
                'signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n'
                'while True: time.sleep(1)\n')
            service.chmod(0o755)
            for name in ('pipewire', 'pipewire-pulse', 'wireplumber'):
                (binaries / name).symlink_to(service)
            for name in ('pw-cli', 'pactl'):
                probe = binaries / name
                probe.write_text('#!/bin/sh\nexit 0\n')
                probe.chmod(0o755)
            events = root / 'events'
            env = os.environ | {
                'PATH': f'{binaries}:/usr/bin', 'HOME': str(home),
                'XDG_RUNTIME_DIR': str(runtime), 'EVENT_LOG': str(events),
            }
            process = subprocess.Popen([supervisor], env=env)
            log = home / '.local/state/starch/audio-session.log'
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    if log.is_file() and 'are ready' in log.read_text():
                        break
                    time.sleep(0.1)
                self.assertIn('are ready', log.read_text())
                # Plasma autostart must be harmless when the wrapper already
                # owns the stack, and must not terminate that owner's children.
                duplicate = subprocess.run([supervisor], env=env, timeout=3)
                self.assertEqual(duplicate.returncode, 0)
                self.assertIsNone(process.poll())
                self.assertEqual(events.read_text().splitlines(),
                                 ['pipewire', 'pipewire-pulse', 'wireplumber'])
            finally:
                process.terminate()
                process.wait(timeout=8)
            self.assertIn('are ready', log.read_text())
            self.assertEqual(events.read_text().splitlines()[:3],
                             ['pipewire', 'pipewire-pulse', 'wireplumber'])

    def test_normal_iso_build_always_builds_and_stages_lite(self):
        build = (ROOT / 'build.sh').read_text()
        stage_script = (ROOT / 'scripts/build/stage-installer.py').read_text()
        self.assertIn('scripts/build/starch-lite.sh\" --ensure', build)
        self.assertNotIn('STARCH_EXPERIMENTAL_LITE', build)
        self.assertIn("SOURCE / 'build/starch-lite/artix-repo'", stage_script)
        self.assertNotIn('STARCH_EXPERIMENTAL_LITE', stage_script)
        self.assertIn('liteEnabled: true',
                      (ROOT / 'calamares/modules/starchadvanced.conf').read_text())

    def test_repository_and_signing_selection_is_lite_only(self):
        original_is_file = Path.is_file
        for enabled in (False, True):
            with self.subTest(lite=enabled), tempfile.TemporaryDirectory() as directory:
                state = Path(directory)
                bundle(state / 'lite')
                for name in ('pacman.conf', 'pacman-lite.conf'):
                    (state / name).write_text((ROOT / 'calamares' / name).read_text())
                gs = Storage(starchLite=enabled, starchAdvancedAcknowledged=True,
                             firmwareType='efi', partitionChoices={'install': 'erase', 'swap': 'none'})
                def is_file(path):
                    # Lite must work even before the live keyring exists.
                    if path == Path('/etc/pacman.d/gnupg/pubring.gpg'):
                        return not enabled
                    return original_is_file(path)
                with patch.object(preflight, 'DATA', state), patch.object(preflight, 'STATE', state), \
                     patch.object(preflight, 'selected_disk', return_value='/dev/vda'), \
                     patch.object(preflight, 'output', return_value='{}'), \
                     patch.object(preflight, 'deactivate_disk'), patch.object(preflight, 'check_disk_tree'), \
                     patch.object(preflight, 'read_manifest', return_value=['base', 'linux-lts']), \
                     patch.object(preflight, 'microcode', return_value=[]), \
                     patch.object(preflight, 'select_packages', return_value=[]), \
                     patch.object(Path, 'is_file', autospec=True, side_effect=is_file), \
                     patch.object(preflight, 'prepare_lite_keyring', return_value=state / 'lite-gnupg') as trust, \
                     patch.object(preflight, 'command') as commands:
                    preflight.run(gs)
                sync = next(c.args[0] for c in commands.call_args_list if '-Sy' in c.args[0])
                config = Path(sync[sync.index('--config') + 1])
                self.assertEqual(config.name, 'pacman-lite.conf' if enabled else 'pacman.conf')
                self.assertEqual('--gpgdir' in sync, enabled)
                self.assertEqual(trust.call_count, int(enabled))
                repos = [line[1:-1] for line in config.read_text().splitlines()
                         if line.startswith('[') and line != '[options]']
                self.assertEqual(repos, ['system', 'world', 'galaxy', 'extra'] if enabled else ['core', 'extra'])
                selection = json.loads((state / 'selection.json').read_text())
                self.assertEqual('artix-keyring' in selection['packages'], enabled)
                self.assertIn('linux-zen' if enabled else 'linux-lts', selection['packages'])

    def test_lite_trust_never_populates_the_live_keyring(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(repositories, 'command') as commands:
            state = Path(directory)
            archives = [state / 'starch-lite-1-1-x86_64.pkg.tar.zst',
                        state / 'artix-keyring-1-1-any.pkg.tar.zst']
            keyring = repositories.prepare_lite_keyring(archives, state)
            for call in commands.call_args_list:
                argv = call.args[0]
                if argv[0] == 'pacman-key':
                    self.assertIn('--gpgdir', argv)
                    self.assertEqual(argv[argv.index('--gpgdir') + 1], keyring)
            self.assertEqual(keyring, state / 'lite-gnupg')

    def test_default_and_package_selection(self):
        self.assertEqual(profiles.profile_name(Storage()), 'standard')
        self.assertEqual(profiles.kernel_name(Storage()), 'linux-lts')
        original = ['base', 'linux-lts', 'dbus-broker-units', 'zram-generator', 'limine']
        packages = profiles.lite_packages(original)
        self.assertIn('linux-zen', packages)
        self.assertIn('dbus-openrc', packages)
        self.assertIn('artix-archlinux-support', packages)
        self.assertNotIn('starch-lite-openrc', packages)
        self.assertNotIn('linux-lts', packages)
        self.assertNotIn('dbus-broker-units', packages)
        self.assertNotIn('zram-generator', packages)
        self.assertEqual(original[1], 'linux-lts')

    def test_zen_nvidia_uses_dkms_and_matching_headers(self):
        selected = graphics.package_selection([(0x10de, 0x1e90, 0, 0)], {(0x1e90,)}, kernel='linux-zen')
        self.assertIn('nvidia-open-dkms', selected)
        self.assertIn('linux-zen-headers', selected)
        self.assertNotIn('nvidia-open-lts', selected)

    def test_bundle_integrity_identity_and_path_checks(self):
        for invalid in ('checksum', 'traversal', 'symlink', 'package-set', 'old-format', None):
            with self.subTest(invalid=invalid), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                entries = bundle(root)
                archive = root / entries[0]['filename']
                if invalid == 'checksum':
                    archive.write_bytes(b'changed')
                elif invalid == 'traversal':
                    entries[0]['filename'] = '../outside.pkg.tar.zst'
                elif invalid == 'symlink':
                    archive.unlink()
                    archive.symlink_to('/etc/passwd')
                elif invalid == 'package-set':
                    entries.pop()
                (root / 'bundle.json').write_text(json.dumps(dict(format=2, repositories='artix-arch-extra', packages=entries)))
                if invalid == 'old-format':
                    (root / 'bundle.json').write_text(json.dumps(dict(format=1, packages=entries)))
                if invalid:
                    with self.assertRaises(RuntimeError):
                        profiles.verified_bundle(root)
                else:
                    self.assertEqual(len(profiles.verified_bundle(root)), 2)

    def test_missing_bundle_and_missing_acknowledgement_stop_before_disk_access(self):
        for acknowledged in (False, True):
            with tempfile.TemporaryDirectory() as directory, patch.object(preflight, 'DATA', Path(directory)), \
                 patch.object(preflight, 'selected_disk') as selected_disk, patch.object(preflight, 'command') as command:
                with self.assertRaises(RuntimeError):
                    preflight.run(Storage(starchLite=True, starchAdvancedAcknowledged=acknowledged))
                selected_disk.assert_not_called()
                command.assert_not_called()

    def test_bundle_change_after_preflight_stops_before_pacstrap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle(root / 'lite')
            (root / 'selection.json').write_text(json.dumps(dict(packages=['base'], lite_bundle_sha256='old')))
            with patch.object(bootstrap, 'target', return_value=root), \
                 patch.object(bootstrap, 'DATA', root), patch.object(bootstrap, 'STATE', root), \
                 patch.object(bootstrap, 'command') as command:
                with self.assertRaisesRegex(RuntimeError, 'changed after preflight'):
                    bootstrap.run(Storage(starchLite=True))
                command.assert_not_called()

    def test_configure_lite_selects_openrc_without_systemctl(self):
        for firmware in ('efi', 'bios'):
            with self.subTest(firmware=firmware), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / 'etc').mkdir()
                (root / 'etc/fstab').write_text('UUID=abc / ext4 defaults 0 1\n')
                (root / 'etc/hostname').write_text('starch-test\n')
                (root / 'etc/vconsole.conf').write_text('KEYMAP=us\n')
                (root / 'etc/init.d').mkdir(parents=True)
                (root / 'etc/conf.d').mkdir(parents=True)
                (root / 'etc/conf.d/agetty').write_text('term_type=linux\n')
                runlevel = root / 'etc/runlevels/default'
                runlevel.mkdir(parents=True)
                for number in range(1, 7):
                    (runlevel / f'agetty.tty{number}').symlink_to(f'/etc/init.d/agetty.tty{number}')
                session = root / 'usr/share/wayland-sessions/starch-lite.desktop'
                session.parent.mkdir(parents=True)
                session.write_text('[Desktop Entry]\nExec=/usr/lib/starch-lite/plasma-session\n')
                gs = Storage(starchLite=True, firmwareType=firmware)
                with patch.object(configure, 'target', return_value=root), \
                     patch.object(configure, 'chroot') as calls, patch.object(lite, 'chroot') as lite_calls:
                    configure.run(gs)
                commands = [call.args[1] for call in calls.call_args_list + lite_calls.call_args_list]
                self.assertNotIn('systemctl', commands)
                self.assertIn('rc-update', commands)
                self.assertEqual((root / 'var/lib/sddm/state.conf').read_text(),
                                 '[Last]\nSession=starch-lite.desktop\n')
                for number in range(2, 7):
                    lite_calls.assert_any_call(root, 'rc-update', 'del', f'agetty.tty{number}', 'default')
                lite_calls.assert_any_call(root, 'rc-update', 'add', 'agetty.tty1', 'default')
                self.assertIn('mkinitcpio', commands)
                hooks = (root / 'etc/mkinitcpio.conf.d/10-starch.conf').read_text()
                self.assertNotIn('systemd', hooks)
                self.assertIn('udev', hooks)
                self.assertIn('ID=starch\n', (root / 'etc/os-release').read_text())
                self.assertNotIn('VARIANT_ID', (root / 'etc/os-release').read_text())
                if firmware == 'efi':
                    self.assertIn('init=/usr/bin/openrc-init', (root / 'etc/kernel/cmdline').read_text())
                    self.assertIn('starch-linux-zen.efi', (root / 'etc/mkinitcpio.d/linux-zen.preset').read_text())
                self.assertFalse((root / 'etc/mkinitcpio.d/linux-lts.preset').exists())

    def test_limine_efi_selects_profile_kernel(self):
        self.assertIn('starch-linux-lts.efi', limine.configuration('abc'))
        lite_config = limine.configuration('abc', 'linux-zen')
        self.assertIn('/Starch Linux\n', lite_config)
        self.assertNotIn('/Starch Lite', lite_config)
        self.assertIn('starch-linux-zen.efi', lite_config)
        self.assertNotIn('linux-lts', lite_config)

    def test_staging_requires_explicit_bundle_and_never_installs_lite_into_live_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            fs = root / 'airootfs'
            (fs / 'etc/calamares/modules').mkdir(parents=True)
            stage.stage_lite(fs, None)
            self.assertIn('false', (fs / 'etc/calamares/modules/starchadvanced.conf').read_text())
            bundle(root / 'repo')
            stage.stage_lite(fs, root / 'repo')
            self.assertIn('true', (fs / 'etc/calamares/modules/starchadvanced.conf').read_text())
            self.assertEqual(len(profiles.verified_bundle(fs / 'usr/share/starch-installer/lite')), 2)
            self.assertFalse((fs / 'usr/bin/openrc-init').exists())


if __name__ == '__main__':
    unittest.main()
