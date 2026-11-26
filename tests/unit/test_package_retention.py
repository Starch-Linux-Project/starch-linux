import hashlib
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import preflight


class PackageRetention(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.state = pathlib.Path(directory.name)
        self.cache = self.state / 'cache'
        self.sync = self.state / 'db/sync'
        self.sync.mkdir(parents=True)
        (self.sync / 'core.db').write_bytes(b'original database')
        for key, value in [('STATE', self.state), ('PACKAGE_CACHE', self.cache)]:
            self.enterContext(patch.object(preflight, key, value))
        self.enterContext(patch.object(preflight, 'output', side_effect=['ext4', 'core']))
        self.payload = b'signed package contents'
        self.filename = 'sample-1.0-1-any.pkg.tar.zst'

    def retain(self):
        archives = {self.filename: (len(self.payload), hashlib.sha256(self.payload).hexdigest())}
        preflight.retain_packages(['pacman'], self.sync.parent, ['sample'], archives)

    def test_bootstrap_uses_only_retained_mirror_and_signed_package_policy(self):
        def download(argv):
            self.assertIn('-Sw', argv)
            (self.cache / self.filename).write_bytes(self.payload)

        with patch.object(preflight, 'command', side_effect=download):
            self.retain()
        config = (self.state / 'retained-pacman.conf').read_text()
        self.assertEqual([line for line in config.splitlines() if line.startswith('Server')],
                         ['Server = ' + self.cache.as_uri()])
        self.assertIn('SigLevel = Required DatabaseOptional', config)
        self.assertEqual((self.cache / 'core.db').read_bytes(), b'original database')

    def test_incomplete_or_changed_download_prevents_bootstrap(self):
        with patch.object(preflight, 'command',
                          side_effect=lambda argv: (self.cache / self.filename).write_bytes(b'other')):
            with self.assertRaisesRegex(RuntimeError, 'differs'):
                self.retain()
        self.assertFalse((self.state / 'retained-pacman.conf').exists())
        self.assertFalse((self.cache / self.filename).exists())

    def test_out_of_space_stops_before_download(self):
        with patch.object(preflight.shutil, 'disk_usage') as usage, patch.object(preflight, 'command') as download:
            usage.return_value.free = 1
            with self.assertRaisesRegex(RuntimeError, 'Insufficient live storage'):
                self.retain()
            download.assert_not_called()
