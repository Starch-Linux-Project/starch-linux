#!/usr/bin/python3
"""Session-only rotation fallback for COSMIC Wayland and Xfce X11.

Plasma owns its native rotation. Never change a greeter, inactive session,
external panel, ambiguous panel selection, or a docked multi-monitor layout.
"""
import argparse
import fcntl
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys

ANGLES = {'normal': 0, 'left-up': 90, 'bottom-up': 180, 'right-up': 270}
MATRICES = {
    0: (1, 0, 0, 0, 1, 0, 0, 0, 1),
    90: (0, -1, 1, 1, 0, 0, 0, 0, 1),
    180: (-1, 0, 1, 0, -1, 1, 0, 0, 1),
    270: (0, 1, 0, -1, 0, 1, 0, 0, 1),
}
SENSOR = 'net.hadess.SensorProxy'
PROPERTIES = 'org.freedesktop.DBus.Properties'


def command(*args):
    return subprocess.check_output(args, text=True, timeout=8,
                                   stderr=subprocess.PIPE,
                                   env=dict(os.environ, LC_ALL='C'))


def settings_path():
    return Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'starch/rotation.json'


def settings():
    try:
        value = json.loads(settings_path().read_text())
    except FileNotFoundError:
        value = {}
    if (not isinstance(value, dict) or type(value.get('locked', False)) is not bool
            or value.get('offset', 0) not in (0, 90, 180, 270)
            or not isinstance(value.get('output', ''), str)):
        raise ValueError('Invalid rotation.json settings')
    return value


def backend(desktop, session):
    names = desktop.upper().split(':')
    if 'COSMIC' in names and session == 'wayland':
        return 'cosmic'
    if 'XFCE' in names and session == 'x11':
        return 'xfce'
    return None


def cosmic_outputs(text):
    """Read the pinned cosmic-randr 1.11 list format, ignoring ANSI colors."""
    text = re.sub(r'\x1b\[[0-9;]*m', '', text)
    result = []
    for block in re.split(r'(?=^\S+ \()', text, flags=re.M):
        head = re.match(r'(\S+) \(enabled\)\n', block)
        mode = re.search(r'^\s+(\d+)x(\d+) @\s+([\d.]+) Hz.*\(current\)', block, re.M)
        transform = re.search(r'^  Transform: (\w+)$', block, re.M)
        if head:
            if not mode or not transform:
                raise ValueError('Unrecognized COSMIC display report')
            result.append(dict(name=head[1], mode=mode.groups(), transform=transform[1]))
        elif re.match(r'\S+ \(mirroring ', block):
            # A mirror is also an active output, so selection will pause.
            result.append(dict(name=block.split()[0]))
    return result


def xfce_outputs(text):
    return [dict(name=m[1], geometry=tuple(map(int, m.group(2, 3, 4, 5))),
                 transform=m[6] or 'normal') for m in re.finditer(
        r'^(\S+) connected (?:primary )?(\d+)x(\d+)\+(\d+)\+(\d+) (normal|left|right|inverted)?',
        text, re.M)]


def select_output(outputs, preferred=''):
    # Keep desktop-managed dock/mirror layouts intact. Resume when undocked.
    if len(outputs) != 1:
        return None
    output = outputs[0]
    if preferred:
        return output if output['name'] == preferred else None
    return output if re.fullmatch(r'(?:eDP|LVDS|DSI)-?\d+(?:-\d+)*', output['name']) else None


def multiply(a, b):
    return tuple(sum(a[row * 3 + k] * b[k * 3 + col] for k in range(3))
                 for row in range(3) for col in range(3))


def touch_matrix(angle, geometry, screen):
    width, height, x, y = geometry
    sw, sh = screen
    viewport = (width / sw, 0, x / sw, 0, height / sh, y / sh, 0, 0, 1)
    return multiply(viewport, MATRICES[angle])


def touchscreens():
    """Identify actual touchscreens through udev, never touchpads or mice."""
    devices = []
    for device in command('xinput', 'list', '--id-only').splitlines():
        props = command('xinput', 'list-props', device)
        node = re.search(r'Device Node \(\d+\):\s+"(/dev/input/event\d+)"', props)
        if not node or 'Coordinate Transformation Matrix (' not in props:
            continue
        udev = command('udevadm', 'info', '--query=property', '--name', node[1]).splitlines()
        if 'ID_INPUT_TOUCHSCREEN=1' in udev:
            devices.append((device, node[1]))
    return devices


class Display:
    def __init__(self, kind):
        self.kind = kind
        self.last = None
        self.touch_device = None

    def apply(self, orientation, config):
        angle = (ANGLES[orientation] + config.get('offset', 0)) % 360
        if self.kind == 'cosmic':
            outputs = cosmic_outputs(command('cosmic-randr', 'list'))
            desired = 'normal' if angle == 0 else f'rotate{angle}'
        else:
            report = command('xrandr', '--query')
            outputs = xfce_outputs(report)
            desired = {0: 'normal', 90: 'left', 180: 'inverted', 270: 'right'}[angle]
        output = select_output(outputs, config.get('output', ''))
        if output is None:
            self.last = None
            if self.kind == 'xfce':
                # Docking changes the virtual screen even though rotation is
                # paused. Remap touch to the panel, not the entire desktop.
                panels = [o for o in outputs if select_output([o], config.get('output', ''))]
                if len(panels) == 1:
                    self.map_touch(panels[0], report, known_only=True)
            return
        if self.kind == 'cosmic':
            if output['transform'] != desired:
                width, height, refresh = output['mode']
                command('cosmic-randr', 'mode', output['name'], width, height,
                        '--refresh', refresh, '--transform', desired)
        else:
            if len(touchscreens()) > 1:
                return
            if output['transform'] != desired:
                command('xrandr', '--output', output['name'], '--rotate', desired)
                report = command('xrandr', '--query')
                output = select_output(xfce_outputs(report), config.get('output', ''))
            if output:
                self.map_touch(output, report)

    def reconcile_touch(self, config):
        if self.kind != 'xfce' or self.touch_device is None:
            return
        report = command('xrandr', '--query')
        panels = [o for o in xfce_outputs(report) if select_output([o], config.get('output', ''))]
        if len(panels) == 1:
            self.map_touch(panels[0], report, known_only=True)

    def map_touch(self, output, report, known_only=False):
        devices = touchscreens()
        # Multiple touchscreens cannot safely be associated by device name.
        if len(devices) != 1:
            return
        if known_only and self.touch_device != devices[0]:
            return
        size = re.search(r'current (\d+) x (\d+)', report)
        if not size:
            raise ValueError('Missing X11 screen dimensions')
        angle = {'normal': 0, 'left': 90, 'inverted': 180, 'right': 270}[output['transform']]
        matrix = touch_matrix(angle, output['geometry'], tuple(map(int, size.groups())))
        identity = (devices[0], matrix)
        if self.last != identity:
            # Absolute CTM avoids accumulating rotations across daemon restarts.
            # Driver/libinput calibration is a separate property and is retained.
            command('xinput', 'set-prop', devices[0][0], 'Coordinate Transformation Matrix',
                    *map(str, matrix))
            self.last = identity
            self.touch_device = devices[0]


def run(kind):
    from gi.repository import Gio, GLib
    bus = Gio.bus_get_sync(Gio.BusType.SYSTEM, None)
    loop = GLib.MainLoop()
    display = Display(kind)
    claimed_owner = None
    pending = None
    last_error = None

    def call(name, path, interface, method, signature=None, values=()):
        return bus.call_sync(name, path, interface, method,
                             GLib.Variant(signature, values) if signature else None,
                             None, Gio.DBusCallFlags.NONE, 3000, None).unpack()

    def properties(name, path, interface):
        return call(name, path, PROPERTIES, 'GetAll', '(s)', (interface,))[0]

    def session_state():
        name = 'org.freedesktop.login1'
        manager = '/org/freedesktop/login1'
        interface = 'org.freedesktop.login1.Session'
        session_id = os.environ.get('XDG_SESSION_ID')
        if session_id:
            path = call(name, manager, name + '.Manager', 'GetSession', '(s)', (session_id,))[0]
            return properties(name, path, interface)
        try:
            path = call(name, manager, name + '.Manager', 'GetSessionByPID', '(u)', (os.getpid(),))[0]
            return properties(name, path, interface)
        except GLib.Error:
            # systemd user autostart units may live outside the session scope.
            # Only infer ownership when there is exactly one graphical session
            # for this user; never control a second concurrently logged-in seat.
            candidates = []
            sessions = call(name, manager, name + '.Manager', 'ListSessions')[0]
            for _id, uid, _user, _seat, path in sessions:
                if uid == os.getuid():
                    state = properties(name, path, interface)
                    if state.get('Type') in ('x11', 'wayland'):
                        candidates.append(state)
            expected = 'wayland' if kind == 'cosmic' else 'x11'
            if len(candidates) == 1 and candidates[0].get('Type') == expected:
                return candidates[0]
            return {'Active': False}

    def release():
        nonlocal claimed_owner
        if claimed_owner:
            try:
                call(SENSOR, '/net/hadess/SensorProxy', SENSOR, 'ReleaseAccelerometer')
            except GLib.Error:
                pass
            claimed_owner = None

    def update():
        nonlocal claimed_owner, last_error
        try:
            config = settings()
            state = session_state()
            if not state.get('Active') or state.get('LockedHint'):
                release()
                return True
            if config.get('locked', False):
                release()
                display.reconcile_touch(config)
                return True
            sensor = properties(SENSOR, '/net/hadess/SensorProxy', SENSOR)
            if not sensor.get('HasAccelerometer'):
                release()
                return True
            owner = call('org.freedesktop.DBus', '/org/freedesktop/DBus',
                         'org.freedesktop.DBus', 'GetNameOwner', '(s)', (SENSOR,))[0]
            if claimed_owner != owner:
                call(SENSOR, '/net/hadess/SensorProxy', SENSOR, 'ClaimAccelerometer')
                claimed_owner = owner
                # Wait for a fresh reading after claiming the sensor.
                return True
            orientation = sensor.get('AccelerometerOrientation')
            if orientation in ANGLES:
                display.apply(orientation, config)
            last_error = None
        except (GLib.Error, OSError, ValueError, subprocess.SubprocessError) as error:
            message = str(error)
            if message != last_error:
                print('starch-rotation:', message, file=sys.stderr, flush=True)
                last_error = message
        return True

    def changed(*_args):
        nonlocal pending
        if pending:
            GLib.source_remove(pending)
        def settle():
            nonlocal pending
            pending = None
            update()
            return False
        pending = GLib.timeout_add(650, settle)

    bus.signal_subscribe(SENSOR, PROPERTIES, 'PropertiesChanged',
                         '/net/hadess/SensorProxy', SENSOR, Gio.DBusSignalFlags.NONE, changed)
    # Periodic reconciliation handles lock/config changes, late devices, daemon
    # restarts, docking and resume without polling raw sensor hardware.
    GLib.timeout_add_seconds(5, update)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, sig, lambda: (loop.quit(), False)[1])
    update()
    try:
        loop.run()
    finally:
        release()


def main():
    parser = argparse.ArgumentParser(description='Starch automatic screen rotation')
    parser.add_argument('action', choices=('run', 'toggle', 'lock', 'unlock', 'status'), nargs='?', default='run')
    args = parser.parse_args()
    if args.action != 'run':
        config = settings()
        if args.action != 'status':
            config['locked'] = (not config.get('locked', False) if args.action == 'toggle'
                                else args.action == 'lock')
            path = settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = path.with_suffix('.tmp')
            temporary.write_text(json.dumps(config) + '\n')
            temporary.replace(path)
        message = 'Rotation locked' if config.get('locked', False) else 'Automatic rotation enabled'
        print(message)
        if args.action == 'toggle':
            try:
                command('notify-send', '--app-name=Starch', 'Screen Rotation', message)
            except (OSError, subprocess.SubprocessError):
                pass
        return
    kind = backend(os.environ.get('XDG_CURRENT_DESKTOP', ''), os.environ.get('XDG_SESSION_TYPE', ''))
    if not kind or os.getuid() == 0:
        return
    # Keep the lock descriptor open for the lifetime of this session helper.
    runtime = Path(os.environ['XDG_RUNTIME_DIR'])
    with (runtime / 'starch-rotation.lock').open('w') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        run(kind)


if __name__ == '__main__':
    main()
