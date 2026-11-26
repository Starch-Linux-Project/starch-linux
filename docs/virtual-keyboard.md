# Virtual keyboard

Before Calamares starts, choose **standard keyboard** (the default) or
**on-screen keyboard**. The on-screen option supplies a keyboard for the
installer's text and password fields. To change modes, close and relaunch the
installer. This choice applies only to the installer.

## COSMIC LTS

COSMIC LTS uses the upstream on-screen keyboard with **manual**
activation. Automatic activation is disabled: COSMIC OSK 1.11's
`ime_activation` option responds to text-field focus from both mouse and touch,
so Starch seeds manual activation on both the live and installed desktops.

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
its manual control still opens it on COSMIC LTS.

Source: [COSMIC OSK 1.11 state schema](https://github.com/pop-os/cosmic-osk/blob/epoch-1.11.0/config/src/lib.rs).
