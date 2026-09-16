# Calamares 3.3.14 notices

Calamares 3.3.14 was downloaded from the upstream GitHub release published by
the Calamares project. The release archive SHA-256 is
`5547f80db067dea923ae693ba6bb88eb2b2eeac1da3ebec42fce453e31c290c0`.

Calamares is primarily GPL-3.0-or-later. Individual files use the licenses
listed in `LICENSES/` and `.reuse/dep5`; those upstream files are preserved in
this directory. The Starch package applies its patches during `prepare()` and
keeps the upstream archive unchanged.

- Source: https://github.com/calamares/calamares/releases/tag/v3.3.14
- Release archive: https://github.com/calamares/calamares/releases/download/v3.3.14/calamares-3.3.14.tar.gz
- Upstream commit: `21ea803`
- Package modifications: use system pybind11; compile only the modules listed
  in `packages/calamares/README.md`; apply the Starch installer safety patch;
  skip existing-OS probing because only whole-disk erase is offered.

The BIOS Boot partition adaptation comes from upstream commit
`4e09e1ff0065c268a286da95c0425f6df26ee668` (Aaron Rainbolt and Calamares
contributors, GPL-3.0-or-later). The patch records that origin and preserves
the affected files' notices. Starch's remaining partition-policy changes are
identified in the patch files shipped alongside the source archive.
