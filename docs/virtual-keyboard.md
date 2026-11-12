# Virtual keyboard

The Plasma desktop, login screen, and lock screen use Plasma's on-screen
keyboard. Its visibility follows Plasma's touch and text-input behavior;
physical-keyboard systems do not have a keyboard panel forced open. Use the
login screen's virtual-keyboard button when needed.

Before Calamares starts, choose **standard keyboard** (the default) or
**on-screen keyboard**. The on-screen option supplies a keyboard for the
installer's text and password fields. To change modes, close and relaunch the
installer. This choice applies only to the installer.

Starch Lite's Xfce option does not include the Plasma keyboard.

## COSMIC (Standard and Lite)

Both COSMIC profiles use the upstream on-screen keyboard with **manual**
activation. Automatic activation is disabled: COSMIC OSK 1.11's
`ime_activation` option responds to text-field focus from both mouse and touch,
so it cannot provide KDE-style touch-only activation. Starch does not patch
COSMIC's compositor or keyboard. Open the keyboard manually when needed.

Starch seeds `false` in
`/etc/skel/.local/state/cosmic/com.system76.CosmicOSK/v1/ime_activation`
before account creation. This is COSMIC's **state** directory, not its config
directory. The installer verifies that the default reached the user's home;
later user changes survive login and reboot.

For an existing COSMIC account that received the earlier automatic default,
run these commands as that user (without sudo):

```sh
mkdir -p "${XDG_STATE_HOME:-$HOME/.local/state}/cosmic/com.system76.CosmicOSK/v1"
printf 'false\n' > "${XDG_STATE_HOME:-$HOME/.local/state}/cosmic/com.system76.CosmicOSK/v1/ime_activation"
```

Log out and back in if an already-open automatic keyboard remains visible.
The new installer default does not rewrite existing accounts. Verify that
mouse and touchscreen text-field focus leave the keyboard closed and that
its manual control still opens it on both COSMIC profiles.

Source: [COSMIC OSK 1.11 state schema](https://github.com/pop-os/cosmic-osk/blob/epoch-1.11.0/config/src/lib.rs).
