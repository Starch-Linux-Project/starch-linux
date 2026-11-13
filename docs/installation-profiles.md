# Installation profiles

Choose one profile on Calamares' **Installation Profiles** page:

| Profile | Internal identity | Desktop / login | Kernel / init |
| --- | --- | --- | --- |
| KDE Plasma LTS — Recommended (default) | `standard` | Plasma Wayland / SDDM | Linux LTS / systemd |
| COSMIC LTS | `standard-cosmic` | COSMIC Wayland / COSMIC Greeter (greetd) | Linux LTS / systemd |
| Starch Lite — For experienced users | `lite-xfce` | Xfce X11 / LightDM | Linux Zen / OpenRC |

Selection persists when navigating back and appears in the summary. Lite is
included in normal builds; it is disabled if its bundle is missing.

The `starchadvanced` module writes the selection; `scripts/installer/profiles.py`
validates it and selects packages and repositories before disk operations.
See [COSMIC](cosmic.md) and [Starch Lite](starch-lite.md) for profile details.
