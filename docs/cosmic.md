# COSMIC LTS

Select **COSMIC LTS** on the Installation Profiles page. It uses Arch packages,
Linux LTS, systemd, and COSMIC Wayland with COSMIC Greeter (greetd).

The profile includes COSMIC Files, Terminal, Text Editor, desktop portals,
GNOME Keyring, and Starch desktop defaults. The on-screen keyboard opens
manually; automatic screen rotation uses the Starch session helper.
See [keyboard](virtual-keyboard.md) and [rotation](rotation.md) controls.

`scripts/installer/profiles.py` selects explicit COSMIC packages and checks
the resolved transaction. The audited COSMIC components must be version 1.11.0;
a version change requires compatibility review before installation.
`scripts/installer/cosmic.py` applies the target configuration.

Release validation requires a fresh install and checks of login, locking,
reboot, audio, networking, portals, and hardware behavior.
