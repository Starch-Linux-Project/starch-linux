# Automatic screen rotation

Automatic gyro rotation is configured for Standard (Linux LTS) only:

| Profile | Rotation owner |
| --- | --- |
| Standard Plasma / live ISO | KWin + Qt Sensors |
| Standard COSMIC | Starch session helper + cosmic-randr |
| Starch Lite (Xfce) | No Starch automatic rotation integration |

Standard installs `iio-sensor-proxy`, using its packaged systemd/udev
activation. Lite does not request the sensor packages or install a custom
sensor service. Only Standard COSMIC receives the rotation helper, autostart
and rotation-lock launcher. Plasma keeps its native controls.

The COSMIC helper claims the accelerometer only in an active, unlocked session.
It debounces readings, retries sensor discovery and daemon restarts, and rotates
only one active internal eDP/LVDS/DSI panel. Docked, mirrored and ambiguous
layouts pause rotation. Resolution and refresh rate are preserved; COSMIC
owns touch mapping. The parser accepts cosmic-randr 1.11's space-padded refresh
rates (for example `@  60.000 Hz`).

Use **Toggle Rotation Lock** in the application menu, or:

```sh
python3 /usr/lib/starch/rotation.py lock
python3 /usr/lib/starch/rotation.py unlock
python3 /usr/lib/starch/rotation.py status
```

Settings persist in `~/.config/starch/rotation.json`. Optional connector and
mounting overrides: `{"locked": false, "output": "eDP-2", "offset": 0}`.
Offsets may be 0, 90, 180 or 270 degrees. Prefer upstream hwdb fixes for sensor
calibration. The helper follows orientation in laptop mode too; lock rotation
when needed.

## Verification

Unit tests cover profile selection and overlay isolation, padded display
reports, mode preservation and dock/mirror exclusion. The private D-Bus test
is `python3 tests/integration/rotation-dbus.py` (requires PyGObject and permission
to bind a temporary Unix socket). Hardware acceptance remains necessary:

1. Verify all four orientations with `monitor-sensor --accel` and `cosmic-randr list`.
2. Test touch at all screen corners, rotation lock, logout/login and suspend/resume.
3. Test inactive sessions, screen locking, daemon restart and dock/undock.
4. Confirm sensorless machines and external displays remain unaffected.

Maintained source: `packages/starch-rotation/root`. The installer stages it as
`rotation-overlay` and copies it only to Standard COSMIC before user creation.
The live Plasma session is unchanged.

Source interface: [COSMIC RandR 1.11 CLI](https://github.com/pop-os/cosmic-randr/blob/epoch-1.11.0/cli/src/main.rs).
