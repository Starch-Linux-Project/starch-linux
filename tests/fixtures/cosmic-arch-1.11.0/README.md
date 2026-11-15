# Arch COSMIC integration fixture

Unmodified text files extracted from the official Arch `cosmic-greeter
1:1.11.0-1` archive on 2026-11-15. These are test inputs only, never an installer
overlay. `packages.json` records archive URLs/SHA-256, reviewed greeter/OSD
versions and per-file SHA-256. Network is not needed to run tests.

Source: https://github.com/pop-os/cosmic-greeter/tree/epoch-1.11.0
Packaging: https://gitlab.archlinux.org/archlinux/packaging/packages/cosmic-greeter/-/blob/main/PKGBUILD
Copyright: System76 and cosmic-greeter contributors; Arch packaging contributors.
License: GPL-3.0-only according to the package; upstream LICENSE is included.

The Arch recipe SHA-256 at review was
`13233ac41c008afb2ae45183fdce26a2374684e14b4a0fc69373f8306fbf90d0`.
It explicitly reverts `ef1253aa2393666bb2a0b0132b722f51ec7ebbf3`; that commit
changes both the locker PAM context and TOML from login to cosmic-greeter.
The reviewed archive TOML therefore selects login. The source/recipe establishes
the compiled locker selection; offline fixture tests do not exercise real PAM.

COSMIC OSD epoch-1.11.0 `src/components/app.rs` subscribes to the agent and
`src/subscriptions/polkit_agent.rs` registers it with PolicyKit. The inspected
Arch OSD recipe builds this normally, without a disabling patch. Its recipe
SHA-256 was `ddd23678aed40cbb45925fe22ed79f66876e00b4becf0ccdad264ec4e2f756c1`.
Runtime authorization dialogs still need VM acceptance.

When updating this fixture, review the package recipe and PAM patch, vendor
units, launcher and native OSD activation together; update provenance and the
installer release gate. Do not merely change expected versions to pass tests.
