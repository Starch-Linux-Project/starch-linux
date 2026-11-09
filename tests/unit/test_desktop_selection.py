import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import bootstrap
import preflight
import profiles
from runtime import read_manifest


class Storage:
    def __init__(self, **values):
        self.values = values

    def value(self, name):
        return self.values.get(name)


class DesktopSelection(unittest.TestCase):
    def test_existing_package_sets_and_identities_are_preserved(self):
        base = read_manifest(ROOT / 'manifests/minimal-packages.txt')
        for lite, desktop, identity in (
                (False, 'plasma', 'standard'), (True, 'plasma', 'lite'),
                (True, 'xfce', 'lite-xfce')):
            with self.subTest(profile=identity):
                gs = Storage(starchLite=lite, starchDesktop=desktop)
                expected = profiles.lite_packages(base, xfce=desktop == 'xfce') if lite else base
                self.assertEqual(profiles.selected_packages(base, gs), expected)
                self.assertEqual(profiles.profile_name(gs), identity)
                self.assertEqual(profiles.kernel_name(gs), 'linux-zen' if lite else 'linux-lts')
                self.assertEqual(profiles.pacman_config(ROOT, gs).name,
                                 'pacman-lite.conf' if lite else 'pacman.conf')

    def test_legacy_selection_remains_compatible(self):
        for values, desktop in (({}, 'plasma'), ({'starchLite': True}, 'plasma'),
                                ({'starchLite': True, 'starchLiteXfce': True}, 'xfce')):
            gs = Storage(**values)
            profiles.validate_selection(gs)
            self.assertEqual(profiles.desktop_name(gs), desktop)

    def test_invalid_and_contradictory_state_stops_before_disk_access(self):
        cases = (
            {'starchDesktop': 'unknown'}, {'starchDesktop': ''},
            {'starchDesktop': ['plasma']}, {'starchDesktop': 'xfce'},
            {'starchLiteXfce': True},
            {'starchLite': True, 'starchDesktop': 'plasma', 'starchLiteXfce': True},
            {'starchLite': True, 'starchDesktop': 'cosmic', 'starchLiteXfce': True},
        )
        for values in cases:
            with self.subTest(values=values), patch.object(preflight, 'selected_disk') as disk, \
                    patch.object(preflight, 'command') as command:
                with self.assertRaises(RuntimeError):
                    preflight.run(Storage(**values))
                disk.assert_not_called()
                command.assert_not_called()

    def test_both_cosmic_profiles_exclude_other_desktops_and_preserve_init(self):
        base = read_manifest(ROOT / 'manifests/minimal-packages.txt')
        for lite in (False, True):
            gs = Storage(starchLite=lite, starchDesktop='cosmic')
            selected = set(profiles.selected_packages(base, gs))
            self.assertEqual(profiles.profile_name(gs), 'lite-cosmic' if lite else 'standard-cosmic')
            self.assertEqual(profiles.kernel_name(gs), 'linux-zen' if lite else 'linux-lts')
            self.assertTrue(set(profiles.COSMIC_PACKAGES) <= selected)
            self.assertFalse(profiles.COSMIC_FORBIDDEN & selected)
            self.assertNotIn('nautilus', selected)
            self.assertNotIn('sddm', selected)
            self.assertNotIn('sddm-openrc', selected)
            self.assertIn('greetd', selected)
            self.assertEqual('greetd-openrc' in selected, lite)
            self.assertIn('linux-zen' if lite else 'linux-lts', selected)
            self.assertEqual('openrc' in selected, lite)
            self.assertEqual('elogind' in selected, lite)
            self.assertEqual('dbus-broker-units' in selected, not lite)
            self.assertTrue({'firefox', 'flatpak', 'nftables', 'networkmanager'} <= selected)

    def test_cosmic_keeps_bluetooth_daemon_without_blueman(self):
        base = read_manifest(ROOT / 'manifests/minimal-packages.txt')
        for lite in (False, True):
            with self.subTest(lite=lite):
                selected = profiles.selected_packages(
                    base, Storage(starchLite=lite, starchDesktop='cosmic'))
                self.assertIn('bluez', selected)
                self.assertNotIn('blueman', selected)
                resolved = '\n'.join('galaxy ' + name + ' 1:1.11.0-1'
                                     for name in profiles.COSMIC_PACKAGES if name != 'bluez')
                if lite:
                    resolved += '\nworld greetd-openrc 20231222-1'
                with self.assertRaisesRegex(RuntimeError, 'Missing COSMIC packages: bluez'):
                    profiles.check_cosmic_closure(resolved, lite=lite)

    def test_dependency_closure_rejects_other_desktops_systemd_and_wrong_origins(self):
        resolved = '\n'.join('galaxy ' + name + ' 1:1.11.0-1' for name in profiles.COSMIC_PACKAGES)
        with self.assertRaisesRegex(RuntimeError, 'Missing COSMIC packages: greetd-openrc'):
            profiles.check_cosmic_closure(resolved, lite=True)
        resolved += '\nworld greetd-openrc 20231222-1'
        profiles.check_cosmic_closure(resolved, lite=True)
        for bad in ('galaxy kwin 6.8-1', 'galaxy xfce4-session 4.20-1',
                    'extra systemd 258-1', 'extra systemd-libs 258-1'):
            with self.assertRaises(RuntimeError):
                profiles.check_cosmic_closure(resolved + '\n' + bad, lite=True)
        for bad in (resolved.replace('galaxy cosmic-session', 'extra cosmic-session'),
                    resolved.replace('1.11.0', '1.12.0'), '', 'invalid'):
            with self.assertRaises(RuntimeError):
                profiles.check_cosmic_closure(bad, lite=True)

    def test_bootstrap_rejects_profile_changes_before_package_installation(self):
        for gs in (Storage(starchLite=True, starchDesktop='plasma'),
                   Storage(starchLite=True, starchDesktop='xfce')):
            with tempfile.TemporaryDirectory() as directory:
                state = Path(directory)
                (state / 'selection.json').write_text(json.dumps({
                    'profile': 'standard', 'desktop': 'plasma', 'packages': ['base']}))
                with patch.object(bootstrap, 'STATE', state), \
                        patch.object(bootstrap, 'target', return_value=state), \
                        patch.object(bootstrap, 'pacstrap') as pacstrap:
                    with self.assertRaisesRegex(RuntimeError, 'changed after preflight'):
                        bootstrap.run(gs)
                    pacstrap.assert_not_called()


if __name__ == '__main__':
    unittest.main()
