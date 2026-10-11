import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import graphics
import runtime


class SharedStorageSafety(unittest.TestCase):
    def test_shared_or_unknown_backing_is_rejected_before_any_mutation(self):
        for kind in ('raid1', 'lvm', 'crypt', 'dm', 'mpath'):
            for disks in (('/dev/sda', '/dev/sdb'), (), ('/dev/sdb',)):
                with self.subTest(kind=kind, disks=disks):
                    tree = {'blockdevices': [{
                        'path': '/dev/sda', 'type': 'disk', 'size': 32 * 1024**3,
                        'ro': False, 'mountpoints': [None], 'children': [{
                            'path': '/dev/sda1', 'type': 'part', 'mountpoints': ['/mnt/local'],
                            'children': [{'path': '/dev/mapper/shared', 'type': kind,
                                          'mountpoints': ['/mnt/shared']}]}]}]}
                    backing = {'blockdevices': [{'path': name, 'type': 'disk'} for name in disks]}
                    with patch.object(runtime, 'output', return_value=json.dumps(backing)), \
                         patch.object(runtime, 'command') as command:
                        with self.assertRaisesRegex(RuntimeError, 'shared or unidentified'):
                            runtime.deactivate_disk(tree, '/dev/sda')
                    command.assert_not_called()

    def test_inverse_lookup_failure_does_not_unmount_anything(self):
        tree = {'blockdevices': [{'path': '/dev/sda', 'type': 'disk',
                'size': 32 * 1024**3, 'ro': False, 'children': [
                    {'path': '/dev/mapper/root', 'type': 'crypt', 'mountpoints': ['/mnt/data']}]}]}
        with patch.object(runtime, 'output', side_effect=RuntimeError('lsblk failed')), \
             patch.object(runtime, 'command') as command:
            with self.assertRaisesRegex(RuntimeError, 'lsblk failed'):
                runtime.deactivate_disk(tree, '/dev/sda')
        command.assert_not_called()

    def test_every_json_disk_query_requests_a_tree(self):
        # PATH alone makes lsblk return a flat JSON list. This regression
        # would hide mounted partitions from safety checks and BIOS discovery.
        import ast
        for name in ('runtime.py', 'preflight.py', 'limine.py'):
            tree = ast.parse((ROOT / 'scripts/installer' / name).read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.List):
                    args = [item.value for item in node.elts if isinstance(item, ast.Constant)]
                    if args[:2] == ['lsblk', '--json']:
                        self.assertIn('--tree', args, name)


class BiosMountSafety(unittest.TestCase):
    def test_bios_boot_must_be_fat32_mounted_and_on_selected_disk(self):
        for failure in (None, 'missing', 'ext4', 'other-disk', 'wrong-mount', 'unmounted'):
            with self.subTest(failure=failure), tempfile.TemporaryDirectory(prefix='calamares-root-') as directory:
                root = Path(directory)
                (root / 'selection.json').write_text(json.dumps({'disk': '/dev/vda'}))
                boot = {'mountPoint': '/boot', 'fs': 'ext4' if failure == 'ext4' else 'fat32',
                        'device': '/dev/vda2'}
                values = {'rootMountPoint': directory, 'firmwareType': 'bios',
                          'bootLoader': {'installPath': '/dev/vda'},
                          'partitions': [{'mountPoint': '/', 'fs': 'ext4', 'device': '/dev/vda3'}]
                                        + ([] if failure == 'missing' else [boot])}
                class GS:
                    def value(self, key):
                        return values.get(key)
                def output(argv):
                    if 'PATH' in argv:
                        return '/dev/vdb' if failure == 'other-disk' and argv[-1] == '/dev/vda2' else '/dev/vda'
                    if argv[-1] in ('/dev/vda2', root / 'boot'):
                        return '254:9' if failure == 'wrong-mount' and argv[-1] == root / 'boot' else '254:2'
                    return '254:3'
                def is_mount(path):
                    return not (failure == 'unmounted' and path == root / 'boot')
                with patch.object(runtime, 'require_live'), patch.object(runtime, 'STATE', root), \
                     patch.object(runtime, 'selected_disk', return_value='/dev/vda'), \
                     patch.object(runtime, 'output', side_effect=output), patch.object(Path, 'is_mount', is_mount):
                    if failure:
                        with self.assertRaises(RuntimeError):
                            runtime.target(GS())
                    else:
                        self.assertEqual(runtime.target(GS()), root)


class GraphicsSelection(unittest.TestCase):
    intel = (0x8086, 0x9a49, 0, 0)
    amd = (0x1002, 0x73bf, 0, 0)
    nvidia = (0x10de, 0x1e90, 0x1028, 0x08ec)
    old_nvidia = (0x10de, 0x1b80, 0, 0)
    readme = '| GPU | PCI ID |\n| Example | 1E90 |\n| Specific board | 1F02 1028 1234 |\n'

    def test_modaliases_include_only_display_devices(self):
        with tempfile.TemporaryDirectory() as directory:
            pci = Path(directory)
            for name, alias in {
                'gpu': 'pci:v000010DEd00001E90sv00001028sd000008ECbc03sc00i00',
                'audio': 'pci:v000010DEd000010F7sv00001028sd000008ECbc04sc03i00',
                'network': 'pci:v00008086d00001234sv00000000sd00000000bc02sc00i00',
            }.items():
                (pci / name).mkdir()
                (pci / name / 'modalias').write_text(alias)
            self.assertEqual(graphics.display_devices(pci), [self.nvidia])

    def test_vendor_hybrid_and_fallback_packages(self):
        supported = graphics.supported_nvidia_ids(self.readme)
        self.assertEqual(graphics.package_selection([], supported), [])
        self.assertEqual(graphics.package_selection([(0x1234, 1, 0, 0)], supported), [])
        self.assertEqual(graphics.package_selection([self.amd], supported), ['vulkan-radeon'])
        self.assertEqual(graphics.package_selection([self.nvidia], supported), ['nvidia-open-lts', 'nvidia-utils'])
        hybrid = graphics.package_selection([self.intel, self.nvidia], supported)
        self.assertIn('vulkan-intel', hybrid)
        self.assertIn('intel-media-driver', hybrid)
        self.assertIn('nvidia-prime', hybrid)
        self.assertNotIn('vulkan-radeon', hybrid)
        self.assertEqual(graphics.package_selection([self.old_nvidia], supported), ['vulkan-nouveau'])
        self.assertEqual(graphics.package_selection([self.nvidia, self.old_nvidia], supported), ['vulkan-nouveau'])
        self.assertEqual(graphics.package_selection([(0x10de, 0x1f02, 0x1028, 0x1234)], supported),
                         ['nvidia-open-lts', 'nvidia-utils'])
        self.assertEqual(graphics.package_selection([(0x10de, 0x1f02, 0x1028, 0xffff)], supported),
                         ['vulkan-nouveau'])
        with self.assertRaises(RuntimeError):
            graphics.supported_nvidia_ids('unexpected upstream format')

    def test_non_nvidia_needs_no_metadata_download(self):
        with patch.object(graphics, 'display_devices', return_value=[self.amd]), \
             patch.object(graphics, 'command') as command:
            self.assertEqual(graphics.select_packages(['pacman'], Path('/unused')), ['vulkan-radeon'])
        command.assert_not_called()

    def test_nvidia_uses_signed_package_table_and_checks_driver_version(self):
        for version in ('1.2.3', '1.2.4'):
            with self.subTest(version=version), tempfile.TemporaryDirectory() as directory:
                def download(argv):
                    self.assertIn('-Swdd', argv)
                    self.assertNotIn('--nosignature', argv)
                    (Path(argv[argv.index('--cachedir') + 1]) / 'nvidia-open-dkms-1.2.3-1.pkg.tar.zst').touch()
                def output(argv):
                    if '-tf' in argv:
                        return 'usr/src/nvidia-1.2.3/README.md\nusr/src/nvidia-1.2.3/Makefile'
                    if '-xOf' in argv:
                        return self.readme
                    return f'nvidia-open-lts 1:1.2.3-1\nnvidia-utils {version}-1\nlinux-lts 9.0-1'
                with patch.object(graphics, 'display_devices', return_value=[self.nvidia]), \
                     patch.object(graphics, 'command', side_effect=download), \
                     patch.object(graphics, 'output', side_effect=output):
                    if version == '1.2.3':
                        self.assertEqual(graphics.select_packages(['pacman'], Path(directory)),
                                         ['nvidia-open-lts', 'nvidia-utils'])
                    else:
                        with self.assertRaisesRegex(RuntimeError, 'out of sync'):
                            graphics.select_packages(['pacman'], Path(directory))
