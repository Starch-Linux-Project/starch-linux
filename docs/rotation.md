# Automatic screen rotation

Starch supplies `iio-sensor-proxy` in the live Plasma ISO and all five installed
profiles. The daemon uses the kernel's supported sensors and upstream udev/hwdb
orientation corrections. No model-specific accelerometer driver is forced and
no raw input device permissions are relaxed.

| Profile | Sensor startup | Rotation owner |
| --- | --- | --- |
| Standard Plasma / live ISO | Packaged systemd/udev activation | KWin + Qt Sensors |
| Lite Plasma | Starch OpenRC service | KWin + Qt Sensors |
| Standard COSMIC | Packaged systemd/udev activation | Starch session helper + cosmic-randr |
| Lite COSMIC | Starch OpenRC service | Same COSMIC adapter |
| Lite Xfce (X11) | Starch OpenRC service | Starch helper + xrandr/xinput |

Artix's inspected sensor archive contains `/usr/lib/iio-sensor-proxy`, udev
rules and D-Bus/polkit policy but no OpenRC startup script. The installer writes
and enables a supervised service after D-Bus. Standard uses the package's udev
activation; there is no second custom systemd sensor daemon.

## Behavior and controls

Plasma retains its native automatic orientation and tablet-mode controls in
Display Configuration. `qt6-sensors` is explicit in both Plasma manifests.
The Starch helper never runs in Plasma or the greeter.

COSMIC and Xfce start an unprivileged XDG session helper. It claims orientation
through SensorProxy only for an active, unlocked logind/elogind session with
an accelerometer. It releases the claim when rotation is locked or the session
is inactive, and on normal exit. It retries sensor discovery and daemon
restarts, ignores undefined orientations, and debounces sensor notifications
for 650 ms. A five-second reconciliation also handles settings, resume,
late devices and docking. Machines without sensors do not run display commands.

The fallback rotates a single active internal eDP/LVDS/DSI panel. It recognizes
connector numbers dynamically. Rotation pauses with multiple active displays,
mirroring, or an ambiguous panel; external displays are not automatically
rotated. It resumes after undocking. COSMIC retains the current resolution and
refresh rate and delegates touch mapping to the compositor. Xfce applies an
absolute coordinate matrix to a single detected touchscreen, preserving the
separate libinput calibration property. When docked, it maps that touchscreen
to the internal panel's portion of the virtual desktop, provided it was already
associated while undocked. It does not guess a new touchscreen association in
a docked layout. Multiple touchscreens
pause Xfce automatic rotation because their output association is ambiguous.
Custom X11 Coordinate Transformation Matrix settings are owned by this helper;
use libinput calibration for hardware calibration, or disable the helper.

Unlike Plasma's native tablet-mode policy, the COSMIC/Xfce fallback follows
orientation whenever unlocked, including in laptop mode. It does not read raw
keyboard/input events or assume that every convertible reports a hinge switch.
Keyboard/touchpad disabling and on-screen-keyboard behavior remain desktop
responsibilities. Lock rotation while using the device as a laptop if needed.

On COSMIC and Xfce, launch **Toggle Rotation Lock** from the application menu;
a notification confirms the new state. CLI equivalents:

```sh
python3 /usr/lib/starch/rotation.py lock
python3 /usr/lib/starch/rotation.py unlock
python3 /usr/lib/starch/rotation.py status
```

Settings persist in `$XDG_CONFIG_HOME/starch/rotation.json` (normally
`~/.config/starch/rotation.json`). Optional overrides for unusual connector
names or panel mounting:

```json
{"locked": false, "output": "eDP-2", "offset": 0}
```

`offset` may be 0, 90, 180 or 270 degrees. Prefer correcting a genuinely wrong
sensor mount matrix through a device-specific upstream hwdb entry; a rotation
offset is not a general replacement for sensor calibration. An explicit output
still requires a single active display. Malformed settings stop rotation and
are reported to session stderr, rather than selecting a different display.

## Verification and limits

This is implemented integration, **not hardware-certified support**. Unit tests
cover desktop selection, package selection, internal output discovery, COSMIC
mode/refresh preservation, dock/mirror exclusion, touchscreen identification,
four orientation matrices and X11 viewport mapping. No physical accelerometer,
touch panel, or compositor acceptance test is available in the build workspace.
Kernel/firmware support and correct sensor mounting remain hardware-dependent.

All five package profiles resolved against the cached repository databases with
the sensor package present and without systemd/dinit runtimes on Lite. The
private D-Bus integration test passed absent/late sensors, claim/release,
screen-lock/unlock, systemd user-service session discovery and graceful cleanup.
Run it with `python3 tests/integration/rotation-dbus.py`; it requires PyGObject,
`dbus-daemon` and permission to bind a temporary Unix socket, but does not use
host services or change displays. The unit suite has two pre-existing Fastfetch
artwork equality failures unrelated to rotation.

Build a new ISO and test each profile on real convertibles:

1. Run `monitor-sensor --accel`; verify all four physical orientations.
2. Check Plasma automatic rotation and its tablet-mode policy. In COSMIC/Xfce,
   verify portrait/landscape, screen corners with touch, and rotation lock.
3. Verify logout/login, inactive VT, screen lock, suspend/resume and sensor
   service restart. No other logged-in session should rotate the display.
4. Dock/undock; verify external displays stay fixed and touch stays on the panel.
5. Test a machine without sensors and one with an unusual internal connector.
6. Verify the default orientation on devices with portrait-native panels;
   record any required hwdb correction or explicit offset by hardware model.

Diagnostic commands:

```sh
monitor-sensor --accel
# Standard:
systemctl status iio-sensor-proxy
# Lite:
rc-service iio-sensor-proxy status
# COSMIC:
cosmic-randr list
# Xfce:
xrandr --query
xinput list
```

Source contracts reviewed:

- [SensorProxy D-Bus API](https://hadess.pages.freedesktop.org/iio-sensor-proxy/gdbus-net.hadess.SensorProxy.html)
- [COSMIC RandR 1.11 CLI](https://github.com/pop-os/cosmic-randr/blob/epoch-1.11.0/cli/src/main.rs)
- [COSMIC orientation mapping reference](https://github.com/sondresj/cosmic-iio/blob/main/src/core/transform.rs)

The maintained implementation is `packages/starch-rotation/root`; staging copies
it into the installed-system overlay. Python is invoked explicitly, so archiso's
normal 0644 overlay modes do not make the helper unlaunchable. COSMIC/Xfce alone
request its GObject and notification dependencies.
