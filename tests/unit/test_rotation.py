import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('rotation', ROOT / 'packages/starch-rotation/root/usr/lib/starch/rotation.py')
rotation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rotation)
sys.path.insert(0, str(ROOT / 'scripts/installer'))
import profiles
from runtime import read_manifest

COSMIC = '''eDP-2 (enabled)
  Model: Internal
  Transform: normal

  Modes:
    1920x1200 @  60.000 Hz (current) (preferred)
    1920x1200 @  48.000 Hz
HDMI-A-1 (disabled)
  Model: External
'''
XRANDR = '''Screen 0: minimum 8 x 8, current 1920 x 1200, maximum 32767 x 32767
eDP1 connected primary 1920x1200+0+0 (normal left inverted right x axis y axis) 290mm x 180mm
HDMI1 disconnected (normal left inverted right x axis y axis)
'''


class Rotation(unittest.TestCase):
    def test_only_supported_sessions_have_fallback(self):
        for desktop, session, expected in [('KDE', 'wayland', None), ('COSMIC', 'wayland', 'cosmic'),
                                           ('XFCE', 'x11', 'xfce'), ('XFCE', 'wayland', None),
                                           ('COSMIC', 'x11', None), ('GNOME', 'wayland', None)]:
            self.assertEqual(rotation.backend(desktop, session), expected)

    def test_selects_internal_panel_without_hardcoding_number(self):
        for name in ('eDP-1', 'eDP-2', 'eDP1', 'LVDS-1', 'DSI-1'):
            self.assertEqual(rotation.select_output([{'name': name}]), {'name': name})
        self.assertIsNone(rotation.select_output([{'name': 'HDMI-A-1'}]))
        self.assertIsNone(rotation.select_output([{'name': 'eDP-1'}, {'name': 'HDMI-A-1'}]))
        self.assertEqual(rotation.select_output([{'name': 'special'}], 'special'), {'name': 'special'})
        self.assertIsNone(rotation.select_output([]))

    def test_cosmic_preserves_mode_and_refresh(self):
        calls = []
        def command(*argv):
            calls.append(argv)
            return COSMIC if argv == ('cosmic-randr', 'list') else ''
        with patch.object(rotation, 'command', side_effect=command):
            rotation.Display('cosmic').apply('left-up', {})
        self.assertEqual(calls[-1], ('cosmic-randr', 'mode', 'eDP-2', '1920', '1200',
                                    '--refresh', '60.000', '--transform', 'rotate90'))
        self.assertEqual(len(rotation.cosmic_outputs(COSMIC)), 1)
        with self.assertRaisesRegex(ValueError, 'Unrecognized'):
            rotation.cosmic_outputs(COSMIC.replace('(current)', ''))

    def test_cosmic_skips_docked_mirrored_and_unchanged_displays(self):
        for report in (COSMIC, COSMIC + 'DP-1 (mirroring "eDP-2")\n',
                       COSMIC.replace('HDMI-A-1 (disabled)', 'HDMI-A-1 (enabled)') +
                       '  Transform: normal\n  1920x1080 @  60.000 Hz (current)\n'):
            with patch.object(rotation, 'command', return_value=report) as command:
                rotation.Display('cosmic').apply('normal', {})
                self.assertEqual(command.call_count, 1)

    def test_four_touch_transforms_and_docked_viewport(self):
        expected = {0: (0.2, 0.3), 90: (0.7, 0.2), 180: (0.8, 0.7), 270: (0.3, 0.8)}
        for angle, point in expected.items():
            m = rotation.touch_matrix(angle, (1200, 1920, 0, 0), (1200, 1920))
            actual = (m[0] * .2 + m[1] * .3 + m[2], m[3] * .2 + m[4] * .3 + m[5])
            for a, b in zip(actual, point):
                self.assertAlmostEqual(a, b)
        m = rotation.touch_matrix(0, (1920, 1200, 1920, 0), (3840, 1200))
        self.assertEqual(m, (.5, 0, .5, 0, 1, 0, 0, 0, 1))

    def test_xfce_rotates_touch_and_does_not_accumulate_matrices(self):
        rotated = XRANDR.replace('current 1920 x 1200', 'current 1200 x 1920').replace(
            '1920x1200+0+0 (normal', '1200x1920+0+0 left (normal')
        calls = []
        def command(*argv):
            calls.append(argv)
            if argv == ('xrandr', '--query'):
                return rotated if any('--rotate' in c for c in calls) else XRANDR
            return ''
        with patch.object(rotation, 'command', side_effect=command), \
                patch.object(rotation, 'touchscreens', return_value=[('12', '/dev/input/event7')]):
            display = rotation.Display('xfce')
            display.apply('left-up', {})
            display.apply('left-up', {})
        touch = [c for c in calls if c[0] == 'xinput']
        self.assertEqual(len(touch), 1)
        self.assertEqual(tuple(map(float, touch[0][4:])), rotation.MATRICES[90])

    def test_touchscreen_discovery_ignores_touchpads(self):
        def command(*argv):
            if argv == ('xinput', 'list', '--id-only'):
                return '10\n11\n'
            if argv[0] == 'xinput':
                return ('Device Node (1): "/dev/input/event' + argv[-1] + '"\n'
                        'Coordinate Transformation Matrix (2): 1, 0, 0, 0, 1, 0, 0, 0, 1\n')
            return 'ID_INPUT_TOUCHSCREEN=1\n' if argv[-1].endswith('10') else 'ID_INPUT_TOUCHPAD=1\n'
        with patch.object(rotation, 'command', side_effect=command):
            self.assertEqual(rotation.touchscreens(), [('10', '/dev/input/event10')])

    def test_docking_remaps_only_previously_associated_touchscreen(self):
        report = XRANDR.replace('current 1920 x 1200', 'current 3840 x 1200')
        output = rotation.xfce_outputs(report)[0]
        display = rotation.Display('xfce')
        with patch.object(rotation, 'touchscreens', return_value=[('12', '/dev/input/event7')]), \
                patch.object(rotation, 'command') as command:
            display.map_touch(output, report, known_only=True)
            command.assert_not_called()
            display.touch_device = ('12', '/dev/input/event7')
            display.map_touch(output, report, known_only=True)
            self.assertEqual(tuple(map(float, command.call_args.args[4:])),
                             (.5, 0, 0, 0, 1, 0, 0, 0, 1))

    def test_only_lts_profiles_request_rotation_sensors(self):
        base = read_manifest(ROOT / 'manifests/minimal-packages.txt')
        for lite, desktop in ((False, 'plasma'), (True, 'plasma'), (True, 'xfce'),
                              (False, 'cosmic'), (True, 'cosmic')):
            class Storage:
                def value(self, key):
                    return {'starchLite': lite, 'starchDesktop': desktop}.get(key)
            selected = profiles.selected_packages(base, Storage())
            self.assertEqual('iio-sensor-proxy' in selected, not lite)
            self.assertEqual('qt6-sensors' in selected, desktop == 'plasma' and not lite)
            if desktop != 'plasma':
                self.assertIn('python-gobject', selected)
                self.assertIn('libnotify', selected)
            self.assertEqual('xorg-xinput' in selected, desktop == 'xfce')


if __name__ == '__main__':
    unittest.main()
