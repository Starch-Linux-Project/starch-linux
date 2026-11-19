"""Lite panel defaults; visual and launcher execution acceptance needs an X11 VM."""
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from test_starch_lite import ROOT, Storage, bootstrap, preflight, profiles, stage

PAYLOAD = ROOT / 'packages/starch-lite/integration/root'
PANEL = PAYLOAD / 'usr/share/starch-lite/xfce-panel.xml'
USER_PANEL = Path('.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml')


def prop(node, name):
    return node.find(f"property[@name='{name}']")


def values(node):
    return [v.get('value') for v in node.findall('value')]


class XfcePanel(unittest.TestCase):
    def setUp(self):
        self.channel = ET.parse(PANEL).getroot()
        self.panels = prop(self.channel, 'panels')
        self.plugins = prop(self.channel, 'plugins')

    def test_two_panels_with_complete_unique_plugin_references(self):
        self.assertEqual(self.channel.attrib, {'name': 'xfce4-panel', 'version': '1.0'})
        self.assertEqual(values(self.panels), ['1', '2'])
        self.assertEqual([p.get('name') for p in self.panels.findall('property')],
                         ['panel-1', 'panel-2'])
        refs = [v for p in self.panels.findall('property') for v in values(prop(p, 'plugin-ids'))]
        definitions = [p.get('name') for p in self.plugins]
        self.assertEqual(len(refs), len(set(refs)))
        self.assertEqual(len(definitions), len(set(definitions)))
        self.assertEqual(set(definitions), {'plugin-' + v for v in refs})
        # Only layout and plugin settings: inherit GTK appearance without overrides.
        self.assertEqual({p.get('name') for p in self.channel}, {'configver', 'panels', 'plugins'})
        allowed = {'position', 'position-locked', 'size', 'length', 'length-adjust',
                   'autohide-behavior', 'plugin-ids'}
        for panel in self.panels.findall('property'):
            self.assertLessEqual({p.get('name') for p in panel}, allowed)

    def test_top_taskbar_keeps_functionality_and_order(self):
        panel = prop(self.panels, 'panel-1')
        # xfce4-panel 4.20.5 panel-window.c: NC=9, SC=10; never=0, intelligent=1.
        for name, kind, value in [('position', 'string', 'p=9;x=0;y=0'),
                                  ('position-locked', 'bool', 'true'), ('size', 'uint', '36'),
                                  ('length', 'double', '100'), ('autohide-behavior', 'uint', '0')]:
            self.assertEqual(prop(panel, name).attrib, {'name': name, 'type': kind, 'value': value})
        ids = values(prop(panel, 'plugin-ids'))
        self.assertEqual(ids, ['1', '8', '2', '3', '4', '5', '6', '7'])
        self.assertEqual([prop(self.plugins, 'plugin-' + i).get('value') for i in ids],
                         ['whiskermenu', 'launcher', 'tasklist', 'separator', 'systray',
                          'pulseaudio', 'clock', 'actions'])
        self.assertEqual(values(prop(prop(self.plugins, 'plugin-8'), 'items')),
                         ['/usr/share/applications/linux-update-utility.desktop'])
        self.assertEqual(prop(prop(self.plugins, 'plugin-3'), 'expand').get('value'), 'true')
        self.assertEqual(prop(prop(self.plugins, 'plugin-3'), 'style').get('value'), '0')

    def test_dock_geometry_and_launchers_match_selected_packages(self):
        panel = prop(self.panels, 'panel-2')
        for name, kind, value in [('position', 'string', 'p=10;x=0;y=0'),
                                  ('position-locked', 'bool', 'true'), ('size', 'uint', '48'),
                                  ('length', 'double', '1'), ('length-adjust', 'bool', 'true'),
                                  ('autohide-behavior', 'uint', '1')]:
            self.assertEqual(prop(panel, name).attrib, {'name': name, 'type': kind, 'value': value})
        # Reviewed system desktop filenames: Thunar package file list and installed
        # Firefox/COSMIC Terminal entries. No private per-launcher files are needed.
        entries = [('thunar', 'thunar.desktop'), ('cosmic-terminal', 'com.system76.CosmicTerm.desktop'),
                   ('firefox', 'firefox.desktop')]
        selected = profiles.selected_packages(preflight.read_manifest(ROOT / 'manifests/minimal-packages.txt'),
                                             Storage(starchLite=True, starchDesktop='xfce'))
        ids = values(prop(panel, 'plugin-ids'))
        self.assertEqual(len(ids), len(entries))
        for plugin_id, (package, entry) in zip(ids, entries):
            self.assertIn(package, selected)
            plugin = prop(self.plugins, 'plugin-' + plugin_id)
            self.assertEqual(plugin.get('value'), 'launcher')
            self.assertEqual(values(prop(plugin, 'items')), ['/usr/share/applications/' + entry])

    def test_staging_and_bootstrap_seed_only_lite_without_touching_existing_home(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            profile = base / 'profile'
            shutil.copytree(ROOT / 'archiso/profile', profile, symlinks=True)
            stage.stage(profile)
            fs = profile / 'airootfs'
            self.assertFalse((fs / 'etc/skel' / USER_PANEL).exists())
            data = fs / 'usr/share/starch-installer'
            binary = data / 'target-overlay/usr/local/bin/linux-update-utility.AppImage'
            binary.parent.mkdir(parents=True, exist_ok=True)
            binary.touch()
            # Plasma exercises the non-Xfce branch; COSMIC isolation is also covered
            # by test_cosmic's real staged overlay/bootstrap matrix.
            for desktop, is_lite in [('xfce', True), ('plasma', False)]:
                root = base / desktop
                shutil.copytree(PAYLOAD, root)
                existing = root / 'home/existing' / USER_PANEL
                existing.parent.mkdir(parents=True)
                existing.write_text('custom panel settings')
                with patch.object(bootstrap, 'DATA', data):
                    bootstrap.apply_defaults(root, Storage(starchLite=is_lite, starchDesktop=desktop))
                seeded = root / 'etc/skel' / USER_PANEL
                self.assertEqual(seeded.exists(), is_lite)
                self.assertEqual(existing.read_text(), 'custom panel settings')
                if is_lite:
                    self.assertEqual(seeded.read_bytes(), PANEL.read_bytes())
                    self.assertEqual(seeded.stat().st_mode & 0o777, 0o644)
                    shutil.copytree(root / 'etc/skel', root / 'home/new', symlinks=True)
                    self.assertEqual((root / 'home/new' / USER_PANEL).read_bytes(), PANEL.read_bytes())
            execution = (ROOT / 'calamares/settings.conf').read_text().split('  - exec:', 1)[1]
            self.assertLess(execution.index('- starch-bootstrap'), execution.index('- users'))
