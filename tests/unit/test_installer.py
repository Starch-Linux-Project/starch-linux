import importlib.util
import configparser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import runtime
import preflight
import configure
import limine
import validate


class InstallerSafety(unittest.TestCase):
    def test_installer_presentation_is_branded_and_erase_is_initial(self):
        branding = yaml.safe_load((ROOT / 'calamares/branding/starch/branding.desc').read_text())
        self.assertFalse(branding['welcomeStyleCalamares'])
        self.assertNotIn('test installer', branding['strings']['versionedName'].lower())
        self.assertTrue(branding['strings']['productUrl'].startswith('https://'))
        self.assertEqual(branding['strings']['supportUrl'], branding['strings']['productUrl'])
        self.assertEqual(branding['images']['productBanner'], 'banner.svg')

        for name in ('welcome.html', 'slideshow.html'):
            content = (ROOT / 'calamares/branding/starch' / name).read_text()
            self.assertIn('@PRODUCT_URL@', content)
            self.assertIn('news', content.lower())

        partition = yaml.safe_load((ROOT / 'calamares/modules/partition.conf').read_text())
        self.assertEqual(partition['initialPartitioningChoice'], 'erase')
        self.assertFalse(partition['allowManualPartitioning'])
        self.assertEqual(partition['userSwapChoices'], ['none'])

        presentation_patch = (ROOT / 'packages/calamares/0004-starch-installer-presentation.patch').read_text()
        self.assertIn('m_rightLayout->insertLayout( 2, m_drivesLayout )', presentation_patch)
        self.assertEqual(presentation_patch.count('setOpenExternalLinks( true )'), 2)

    def test_machine_id_validation_rejects_invalid_and_unlinked_ids(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'etc').mkdir()
            (root / 'var/lib/dbus').mkdir(parents=True)
            link = root / 'var/lib/dbus/machine-id'
            link.symlink_to('/etc/machine-id')
            for value in ('', 'uninitialized', '0' * 32, 'not-a-machine-id'):
                (root / 'etc/machine-id').write_text(value)
                with self.assertRaises(RuntimeError):
                    validate.validate_machine_id(root)
            (root / 'etc/machine-id').write_text('123456789abcdef0123456789abcdef0\n')
            validate.validate_machine_id(root)
            link.unlink()
            link.write_text('123456789abcdef0123456789abcdef0\n')
            with self.assertRaises(RuntimeError):
                validate.validate_machine_id(root)

    def test_installed_sddm_uses_live_wayland_compositor(self):
        class GS:
            def value(self, _):
                return 'bios'

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'etc').mkdir()
            (root / 'etc/sddm.conf').write_text('[Autologin]\nUser=example\nSession=plasma.desktop\nRelogin=true\n')
            with patch.object(configure, 'target', return_value=root), patch.object(configure, 'chroot'):
                configure.run(GS())
            installed = configparser.ConfigParser()
            installed.read(root / 'etc/sddm.conf.d/10-starch.conf')
            live = configparser.ConfigParser()
            live.read(ROOT / 'archiso/profile/airootfs/etc/sddm.conf.d/10-starch-live.conf')
            self.assertEqual(installed['General']['DisplayServer'], 'wayland')
            self.assertEqual(installed['Wayland']['CompositorCommand'], live['Wayland']['CompositorCommand'])
            self.assertEqual(installed['Wayland']['CompositorCommand'].split()[0], 'kwin_wayland')
            self.assertEqual(installed['Theme']['Current'], 'breeze')
            self.assertNotIn('Autologin', installed)
            installed.read(root / 'etc/sddm.conf')
            self.assertEqual(installed['Autologin']['User'], '')
            self.assertFalse(installed.getboolean('Autologin', 'Relogin'))

    def test_manifest_rejects_options_shell_text_duplicates_and_empty(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'packages'
            for invalid in ('--root\n', 'base; touch /tmp/bad\n', 'base\nbase\n', '# empty\n'):
                p.write_text(invalid)
                with self.assertRaises(RuntimeError):
                    runtime.read_manifest(p)
            p.write_text('base\n# comment\nlinux-lts\n')
            self.assertEqual(runtime.read_manifest(p), ['base', 'linux-lts'])

    def test_microcode_is_vendor_based_and_unknown_is_empty(self):
        self.assertEqual(runtime.microcode('vendor_id : AuthenticAMD\n'), ['amd-ucode'])
        self.assertEqual(runtime.microcode('vendor_id : GenuineIntel\n'), ['intel-ucode'])
        self.assertEqual(runtime.microcode('model name : Intel-looking mystery\n'), [])

    def test_rejects_busy_readonly_small_and_mapped_disks(self):
        disk = {'path': '/dev/vda', 'type': 'disk', 'size': 32 * 1024**3, 'ro': False, 'mountpoints': [None]}
        runtime.check_disk_tree({'blockdevices': [disk]}, '/dev/vda')
        for changes in ({'ro': True}, {'size': 1024}, {'type': 'part'},
                        {'mountpoints': ['/run/archiso/bootmnt']},
                        {'children': [{'type': 'part', 'mountpoints': ['[SWAP]']}]},
                        {'children': [{'type': 'crypt', 'mountpoints': [None]}]}):
            with self.assertRaises(RuntimeError):
                runtime.check_disk_tree({'blockdevices': [dict(disk, **changes)]}, '/dev/vda')
        with self.assertRaises(RuntimeError):
            runtime.check_disk_tree({'blockdevices': [disk]}, '/dev/vdb')

    def test_deactivates_selected_disk_consumers_deepest_first(self):
        tree = {'blockdevices': [{
            'path': '/dev/nvme0n1', 'type': 'disk', 'size': 32 * 1024**3,
            'ro': False, 'mountpoints': [None], 'children': [{
                'path': '/dev/nvme0n1p2', 'type': 'part', 'mountpoints': ['[SWAP]', '/mnt/data'],
                'children': [{
                    'path': '/dev/mapper/old-root', 'type': 'crypt',
                    'mountpoints': ['/mnt/data/home']
                }]
            }]
        }]}
        calls = []
        with patch.object(runtime, 'command', side_effect=lambda argv, timeout=0: calls.append(argv)):
            runtime.deactivate_disk(tree, '/dev/nvme0n1')
        self.assertEqual(calls, [
            ['umount', '--', '/mnt/data/home'],
            ['umount', '--', '/mnt/data'],
            ['cryptsetup', 'close', '/dev/mapper/old-root'],
            ['swapoff', '--', '/dev/nvme0n1p2'],
        ])

    def test_never_deactivates_live_disk(self):
        disk = {'path': '/dev/sda', 'type': 'disk', 'size': 32 * 1024**3, 'ro': False,
                'mountpoints': [None], 'children': [
                    {'path': '/dev/sda1', 'type': 'part', 'mountpoints': ['/run/archiso/bootmnt']}
                ]}
        with patch.object(runtime, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'running live system'):
                runtime.deactivate_disk({'blockdevices': [disk]}, '/dev/sda')
        command.assert_not_called()

    def test_selected_disk_may_be_one_of_multiple_lsblk_roots(self):
        selected = {'path': '/dev/nvme0n1', 'type': 'disk', 'size': 32 * 1024**3,
                    'ro': False, 'mountpoints': [None]}
        tree = {'blockdevices': [
            {'path': '/dev/mapper/holder', 'type': 'dm', 'mountpoints': [None]},
            selected,
        ]}
        with patch.object(runtime, 'command') as command:
            runtime.deactivate_disk(tree, '/dev/nvme0n1')
        command.assert_not_called()
        runtime.check_disk_tree(tree, '/dev/nvme0n1')

    def test_repeated_selected_disk_in_lsblk_tree_is_one_device(self):
        disk = {'path': '/dev/sda', 'type': 'disk', 'size': 32 * 1024**3,
                'ro': False, 'mountpoints': [None]}
        tree = {'blockdevices': [
            {'path': '/dev/mapper/path-a', 'type': 'mpath', 'mountpoints': [None],
             'children': [dict(disk)]},
            {'path': '/dev/mapper/path-b', 'type': 'mpath', 'mountpoints': [None],
             'children': [dict(disk)]},
        ]}
        self.assertEqual(runtime.selected_disk_node(tree, '/dev/sda')['path'], '/dev/sda')
        runtime.check_disk_tree(tree, '/dev/sda')

    def test_target_refuses_host_root_and_unmounted_directory(self):
        class GS:
            def value(self, _):
                return self.root
        gs = GS()
        with patch.object(runtime, 'require_live'):
            for value in ('/', '/home', '/tmp/calamares-root-does-not-exist', None):
                gs.root = value
                with self.assertRaises(RuntimeError):
                    runtime.target(gs)

    def test_failed_sync_stops_before_selection_is_saved(self):
        class GS:
            def value(self, _):
                return {'install': 'erase', 'swap': 'none'}
        with tempfile.TemporaryDirectory() as d:
            state = Path(d)
            with patch.object(preflight, 'STATE', state), patch.object(preflight, 'selected_disk', return_value='/dev/vda'), \
                 patch.object(preflight, 'output', return_value=json.dumps({'blockdevices': []})), \
                 patch.object(preflight, 'deactivate_disk'), patch.object(preflight, 'check_disk_tree'), \
                 patch.object(preflight, 'read_manifest', return_value=['base']), \
                 patch.object(Path, 'is_file', return_value=True), \
                 patch.object(preflight, 'command', side_effect=RuntimeError('network unavailable')):
                with self.assertRaisesRegex(RuntimeError, 'network unavailable'):
                    preflight.run(GS())
            self.assertFalse((state / 'selection.json').exists())

    def test_checked_command_failure_propagates(self):
        with tempfile.TemporaryDirectory() as d, patch.object(runtime, 'LOG', Path(d) / 'log'):
            with self.assertRaises(RuntimeError):
                runtime.command([sys.executable, '-c', 'raise SystemExit(7)'])

    def test_pipeline_checks_before_partition_and_success(self):
        settings = yaml.safe_load((ROOT / 'calamares/settings.conf').read_text())
        jobs = settings['sequence'][1]['exec']
        self.assertLess(jobs.index('starch-preflight'), jobs.index('partition'))
        self.assertLess(jobs.index('mount'), jobs.index('starch-bootstrap'))
        self.assertNotIn('bootloader', jobs)
        self.assertLess(jobs.index('starch-configure'), jobs.index('starch-limine'))
        self.assertLess(jobs.index('starch-limine'), jobs.index('starch-validate'))
        self.assertEqual(jobs[-1], 'umount')
        self.assertNotIn('unpackfs', jobs)
        self.assertTrue(settings['prompt-install'])
        packages = runtime.read_manifest(ROOT / 'manifests/minimal-packages.txt')
        self.assertIn('linux-lts', packages)
        self.assertIn('limine', packages)
        self.assertNotIn('grub', packages)
        self.assertFalse({'linux', 'calamares', 'archinstall', 'mkinitcpio-archiso', 'plasma-x11-session'} & set(packages))

    def test_limine_configuration_chainloads_installed_lts_kernel(self):
        uuid = '12345678-1234-1234-1234-123456789abc'
        self.assertEqual(limine.root_uuid(f'UUID={uuid} / ext4 rw,relatime 0 1\n'), uuid)
        config = limine.configuration(uuid)
        self.assertIn('protocol: efi', config)
        self.assertIn('path: boot():/EFI/Linux/starch-linux-lts.efi', config)
        self.assertNotIn('vmlinuz-linux-lts', config)
        with self.assertRaises(RuntimeError):
            limine.root_uuid('UUID=ESP /boot/efi vfat defaults 0 2\n')

    def test_uefi_configuration_builds_a_uki_on_the_esp(self):
        class GS:
            def value(self, _):
                return 'efi'

        uuid = '12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'etc').mkdir()
            (root / 'etc/fstab').write_text(f'UUID={uuid} / ext4 defaults 0 1\n')
            with patch.object(configure, 'target', return_value=root), patch.object(configure, 'chroot'):
                configure.run(GS())
            self.assertEqual((root / 'etc/kernel/cmdline').read_text(),
                             f'root=UUID={uuid} rw rootfstype=ext4\n')
            preset = (root / 'etc/mkinitcpio.d/linux-lts.preset').read_text()
            self.assertIn('default_uki="/boot/efi/EFI/Linux/starch-linux-lts.efi"', preset)
            self.assertTrue((root / 'boot/efi/EFI/Linux').is_dir())

    def test_limine_installs_uki_and_registers_efi_entry(self):
        class GS:
            values = {
                'firmwareType': 'efi',
                'partitions': [{'mountPoint': '/boot/efi', 'device': '/dev/vda1'}],
            }

            def value(self, name):
                return self.values.get(name)

        uuid = '12345678-1234-1234-1234-123456789abc'
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'usr/share/limine').mkdir(parents=True)
            (root / 'usr/share/limine/BOOTX64.EFI').write_bytes(b'limine')
            (root / 'boot/efi/EFI/Linux').mkdir(parents=True)
            (root / 'boot/efi/EFI/Linux/starch-linux-lts.efi').write_bytes(b'uki')
            (root / 'etc').mkdir()
            (root / 'etc/fstab').write_text(f'UUID={uuid} / ext4 defaults 0 1\n')
            with patch.object(limine, 'target', return_value=root), \
                 patch.object(limine, 'selected_disk', return_value='/dev/vda'), \
                 patch.object(limine, 'output', return_value='1'), \
                 patch.object(limine, 'chroot') as chroot:
                limine.run(GS())
            self.assertEqual((root / 'boot/efi/EFI/Limine/BOOTX64.EFI').read_bytes(), b'limine')
            self.assertEqual((root / 'boot/efi/EFI/BOOT/BOOTX64.EFI').read_bytes(), b'limine')
            self.assertIn('EFI/Linux/starch-linux-lts.efi',
                          (root / 'boot/efi/EFI/Limine/limine.conf').read_text())
            self.assertTrue((root / 'etc/pacman.d/hooks/99-starch-limine.hook').is_file())
            chroot.assert_called_once_with(
                root, 'efibootmgr', '--create', '--disk', '/dev/vda', '--part', '1',
                '--label', 'Starch Linux', '--loader', r'\EFI\Limine\BOOTX64.EFI')

    def test_staged_overlay_excludes_live_credentials_and_services(self):
        spec = importlib.util.spec_from_file_location('stage', ROOT / 'scripts/build/stage-installer.py')
        stage = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(stage)
        import shutil
        with tempfile.TemporaryDirectory() as d:
            profile = Path(d) / 'profile'
            shutil.copytree(ROOT / 'archiso/profile', profile, symlinks=True)
            stage.stage(profile)
            overlay = profile / 'airootfs/usr/share/starch-installer/target-overlay'
            for path in ('etc/passwd', 'etc/shadow', 'etc/sudoers.d/10-starch-live', 'etc/starch-live',
                         'etc/systemd/system', 'etc/NetworkManager', 'home/liveuser'):
                self.assertFalse((overlay / path).exists(), path)
            self.assertEqual((overlay / 'usr/share/starch/fastfetch-text').read_bytes(), (ROOT / 'fastfetch-text').read_bytes())
