# Archiso 90 baseline

Source: https://gitlab.archlinux.org/archlinux/archiso (upstream version 90).
Copied from the installed Arch `archiso 90-1` package, `/usr/share/archiso/configs/releng`.
Upstream README declares GPL-3.0-or-later; package metadata agrees. Authors are preserved in AUTHORS.rst. LICENSE.txt is the locally installed SPDX GPL-3.0-or-later text.

The profile is unmodified, including upstream branding. This is a development baseline, not a reviewed Starch release. File content, modes and symbolic-link targets were compared with the installed profile; ownership belongs to the local checkout. baseline.json records that tree without dereferencing symbolic links.

## Local changes after baseline capture

The profile now has Starch live Plasma/SDDM, account, networking and Fastfetch changes. baseline.json continues to describe the original upstream tree for comparison. See ../../live-desktop.md. The upstream scripts and notices remain identifiable; new Starch files are project-authored configuration.
