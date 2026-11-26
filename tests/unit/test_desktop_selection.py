import json
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import preflight
import profiles
from runtime import read_manifest


class Storage:
    def __init__(self, **values):
        self.values = values

    def value(self, key):
        return self.values.get(key)


class DesktopSelection(unittest.TestCase):
    def test_manifest_preserves_original_cosmic_requests(self):
        fixture = json.loads((ROOT / 'tests/fixtures/installation-profiles.json').read_text())
        self.assertEqual(read_manifest(ROOT / 'manifests/minimal-packages.txt'),
                         fixture[profiles.PROFILE])

    def test_absent_selection_is_valid_and_old_choices_fail_before_disk_access(self):
        profiles.validate_selection(Storage())
        profiles.validate_selection(Storage(starchDesktop='cosmic'))
        for values in ({'starchDesktop': 'plasma'}, {'starchDesktop': 'xfce'},
                       {'starchLite': True}, {'starchLiteXfce': True},
                       {'starchDesktop': ['cosmic']}):
            with self.subTest(values=values), patch.object(preflight, 'selected_disk') as disk:
                with self.assertRaisesRegex(RuntimeError, 'only the Starch Linux COSMIC desktop'):
                    preflight.run(Storage(**values))
                disk.assert_not_called()

    def test_resolved_desktop_is_audited(self):
        packages = {name: f'extra {name} 1:1.11.0-1' for name in profiles.COSMIC_PACKAGES}
        resolved = '\n'.join(packages.values())
        profiles.check_cosmic_closure(resolved)
        for changed in (resolved + '\nextra kwin 6.8-1',
                        resolved.replace(packages['bluez'], ''),
                        resolved.replace(packages['cosmic-comp'], 'extra cosmic-comp 1:1.12.0-1'),
                        resolved.replace(packages['cosmic-greeter'], 'extra cosmic-greeter 1:1.11.0-2')):
            with self.assertRaises(RuntimeError):
                profiles.check_cosmic_closure(changed)
        installer = resolved + '\nextra qt6-virtualkeyboard 6.12.1-1\nextra kwallet 6.32.0-1'
        versions = {name: version for _, name, version in map(str.split, installer.splitlines())}
        profiles.check_cosmic_packages(versions, live=True)
        with self.assertRaises(RuntimeError):
            profiles.check_cosmic_closure(installer)
