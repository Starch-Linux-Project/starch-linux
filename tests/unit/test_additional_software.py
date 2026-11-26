import io
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch, call

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import additional


class AdditionalSoftware(unittest.TestCase):
    def setUp(self):
        self.gs = SimpleNamespace(value={'starchEssentialComplete': True}.get)
        self.root = Path('/tmp/calamares-root-test')

    def test_target_repositories_and_literal_arguments(self):
        with patch.object(additional, 'target', return_value=self.root) as target, \
             patch.object(additional, 'chroot') as run, \
             patch.object(additional, 'preserve_logs'):
            additional.install(self.gs, 'pacman', 'some-package+git')
        target.assert_called_once_with(self.gs)
        self.assertEqual(run.call_args_list, [
            call(self.root, 'pacman', '-Si', '--', 'some-package+git'),
            call(self.root, 'pacman', '-S', '--needed', '--noconfirm', '--', 'some-package+git'),
            call(self.root, 'pacman', '-Q', '--', 'some-package+git')])

    def test_flathub_is_system_wide_and_app_only(self):
        with patch.object(additional, 'target', return_value=self.root), \
             patch.object(additional, 'chroot') as run, \
             patch.object(additional, 'preserve_logs'):
            additional.install(self.gs, 'flathub', 'org.example.App')
        self.assertEqual(run.call_args_list, [
            call(self.root, 'flatpak', 'remote-add', '--system', '--if-not-exists',
                 'flathub', 'https://dl.flathub.org/repo/flathub.flatpakrepo'),
            call(self.root, 'flatpak', 'install', '--system', '--noninteractive',
                 '--assumeyes', '--or-update', 'flathub', 'app/org.example.App'),
            call(self.root, 'flatpak', 'info', '--system', 'app/org.example.App')])

    def test_invalid_inputs_never_touch_target(self):
        for kind, name in [('pacman', '--root=/'), ('pacman', 'repo/pkg'),
                           ('pacman', 'x;touch /tmp/pwn'), ('pacman', '$(id)'),
                           ('pacman', '../file'), ('pacman', ''),
                           ('flathub', 'https://example.org/app'), ('flathub', '--user'),
                           ('flathub', 'org.example.App/stable'), ('aur', 'foo')]:
            with self.subTest(kind=kind, name=name), \
                 patch.object(additional, 'target') as target:
                with self.assertRaises(ValueError):
                    additional.install(self.gs, kind, name)
                target.assert_not_called()

    def test_essential_gate_and_mount_failure_prevent_commands(self):
        with patch.object(additional, 'target', return_value=self.root), \
             patch.object(additional, 'chroot') as run:
            with self.assertRaises(RuntimeError):
                additional.install(SimpleNamespace(value={}.get), 'pacman', 'foo')
            run.assert_not_called()
        with patch.object(additional, 'target', side_effect=RuntimeError('wrong disk')), \
             patch.object(additional, 'chroot') as run:
            with self.assertRaises(RuntimeError):
                additional.install(self.gs, 'pacman', 'foo')
            run.assert_not_called()

    def test_failed_resolution_does_not_install_and_preserves_logs(self):
        with patch.object(additional, 'target', return_value=self.root), \
             patch.object(additional, 'chroot', side_effect=RuntimeError('not found')) as run, \
             patch.object(additional, 'preserve_logs') as logs:
            with self.assertRaises(RuntimeError):
                additional.install(self.gs, 'pacman', 'missing')
        self.assertEqual(run.call_count, 1)
        logs.assert_called_once_with(self.root)

    def test_helper_reports_warning_without_traceback(self):
        request = {'state': {}, 'kind': 'pacman', 'name': 'foo'}
        with patch('sys.stdin', io.StringIO(json.dumps(request))), \
             patch('sys.stdout', new_callable=io.StringIO) as stdout, \
             patch.object(additional, 'install', side_effect=RuntimeError('offline')), \
             patch.object(additional, 'record_result') as record:
            self.assertEqual(additional.main(), 1)
        self.assertEqual(stdout.getvalue(), 'Warning: offline\n')
        record.assert_called_once_with(request, 'warning', 'offline')

    def test_page_and_final_job_order(self):
        sequence = yaml.safe_load((ROOT / 'calamares/settings.conf').read_text())['sequence']
        pages = sequence[0]['show']
        self.assertEqual(pages[pages.index('users') + 1], 'starchsoftware')
        self.assertEqual(sequence[1]['exec'][-3:], ['starch-validate', 'starchsoftware', 'umount'])

    def test_verification_failure_is_not_success(self):
        with patch.object(additional, 'target', return_value=self.root), \
             patch.object(additional, 'chroot', side_effect=[None, None, RuntimeError('missing')]), \
             patch.object(additional, 'preserve_logs'):
            with self.assertRaisesRegex(RuntimeError, 'missing'):
                additional.install(self.gs, 'pacman', 'discord')

    def test_outcome_is_saved_in_target_log(self):
        import tempfile
        with tempfile.TemporaryDirectory() as directory, \
             patch.object(additional, 'LOG', Path(directory) / 'installer.log'), \
             patch.object(additional, 'require_live'), \
             patch.object(additional, 'target', return_value=self.root), \
             patch.object(additional, 'preserve_logs') as preserve:
            additional.record_result({'kind': 'pacman', 'name': 'missing'}, 'warning', 'not found')
            saved = json.loads((Path(directory) / 'installer.log').read_text())
            self.assertEqual(saved['optionalSoftware'], 'warning')
            self.assertEqual(saved['name'], 'missing')
            preserve.assert_called_once_with(self.root)
