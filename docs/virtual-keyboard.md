# Virtual keyboard

Starch uses upstream keyboard implementations rather than a Starch keyboard
application. `plasma-keyboard` and `qt6-virtualkeyboard` are installed in both
the live image and the installed system.

KWin owns the input-method lifecycle. New Plasma users receive:

```ini
[Wayland]
InputMethod[$e]=/usr/share/applications/org.kde.plasma.keyboard.desktop
```

KWin requires the desktop-entry path here; pointing `InputMethod` at the
`plasma-keyboard` executable does not select the input method. This makes the
keyboard available to the Plasma session, including the lock screen, without
forcing the keyboard panel onto screen. Plasma/KWin's normal
touch and tablet input handling decides when to show it. In particular, Starch
does not set `KWIN_IM_SHOW_ALWAYS`; conventional non-touch systems therefore
retain normal physical-keyboard behavior, while touch-only hardware can invoke
the same input method whenever a text field has focus. This policy is evaluated
by the running KWin session, so it is not a one-time installation hardware
probe and remains appropriate when keyboards are attached or removed.

SDDM has a separate KWin process. Both live and installed SDDM configuration
start it with `--inputmethod plasma-keyboard`, allowing the greeter to expose
the same keyboard when its input UI requests it. This is intentionally separate
from SDDM's `InputMethod=qtvirtualkeyboard` setting: current SDDM ignores that
Qt input-method mode under Wayland and the Breeze greeter delegates its virtual
keyboard button to KWin. The normal Plasma lock screen uses the already
configured session KWin and needs no separate Starch keyboard.

Calamares is deliberately launched through XWayland because it runs as root.
XWayland clients cannot request KWin's Wayland text-input protocol themselves,
so its launcher first offers standard-keyboard and on-screen-keyboard modes.
Standard keyboard is the default and starts Calamares without a virtual-keyboard
input module. Selecting on-screen keyboard sets
`QT_IM_MODULE=qtvirtualkeyboard`; Qt Virtual Keyboard's desktop integration then
supplies Calamares with its own top-level keyboard. The choice is made before
Calamares starts because Qt selects its input-method plugin at application
startup. This configuration is restricted to the installer process and does
not change normal Plasma applications.

## Release test matrix

Run these checks on a built ISO before release. Automated validation confirms
both keyboard runtimes, the user default, the SDDM command line, and both
Calamares launcher modes; the following checks require interactive hardware.

| Hardware | SDDM and lock screen | Plasma and Calamares |
| --- | --- | --- |
| Desktop/laptop, physical keyboard, no touch | Physical password entry; no unsolicited panel | Choose standard keyboard; physical typing works and no OSK appears |
| Touchscreen laptop with keyboard | Use the greeter's virtual-keyboard button; physical typing remains usable | Test standard mode, then relaunch in on-screen-keyboard mode and exercise every Calamares text/password field |
| Tablet/handheld, no physical keyboard | Complete sign-in and unlock with the OSK | Select on-screen keyboard by touch and complete Calamares text/password/numeric entry |
| Touchscreen plus external keyboard | Repeat before and after attaching/removing keyboard | Test both installer modes; neither keyboard blocks the other |

Check US English plus one non-US layout, Shift/Caps Lock, symbols and password
fields. If a particular application does not accept input, record whether it
is native Wayland, XWayland, or Calamares and diagnose its KWin or Qt input
path before adding an application-specific workaround.
