# Archiso 90 baseline

Source: https://gitlab.archlinux.org/archlinux/archiso (upstream version 90).
Copied from the installed Arch `archiso 90-1` package, `/usr/share/archiso/configs/releng`.
Upstream README declares GPL-3.0-or-later; package metadata agrees. Authors are preserved in AUTHORS.rst. LICENSE.txt is the locally installed SPDX GPL-3.0-or-later text.

`baseline.json` records the original, unmodified upstream profile, including file content, modes and symbolic-link targets without dereferencing symbolic links.

## Starch modifications

The Starch profile includes live Plasma/SDDM, account, networking and Fastfetch changes. `baseline.json` describes the original upstream tree for comparison. See [Live desktop](../../live-desktop.md). The upstream scripts and notices remain identifiable; new Starch files are project-authored configuration.
