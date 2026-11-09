# Installed Limine maintenance

The installer installs `/usr/local/lib/starch/update-limine`, enrolls the boot
identity in `/etc/starch/limine.json`, and installs pre/post pacman hooks for all
three desktop profiles. Python is required on the installed system.

The current [upstream BIOS/GPT procedure](https://github.com/Limine-Bootloader/Limine/blob/v12.x/USAGE.md#biosgpt)
requires both `limine bios-install DEVICE PARTITION_NUMBER` and the
`limine-bios.sys` file. Copying the file alone does not refresh the embedded
stages. Maintenance refreshes both; it never rewrites the boot menu, kernels,
initramfs, UKIs, or kernel options.

Validation requires a unique UUID-based vfat fstab entry and an actual writable
mount of that filesystem. BIOS additionally requires a plain GPT disk, exactly
one valid BIOS boot partition on that disk, and the enrolled disk PTUUID and
partition PARTUUID. Device names may change. Duplicate identities, mapped
storage, ambiguous layouts, changed identities, and missing sources fail closed.
The intended scope is the installer's standard layout, not arbitrary migrated
or RAID installations.

## Existing installations

Installer changes do not retrofit installed machines. Ship the updater and the
two hooks in a maintenance package, or apply the following manually from a
trusted checkout of this revision. First mount the correct boot filesystem and
review `/etc/fstab` and `lsblk -f`. On BIOS, independently verify that the disk
containing `/boot` is the firmware boot disk and its BIOS boot partition is the
one used by this installation. Enrollment cannot infer firmware boot order.
Do not enroll an ambiguous or migrated layout without resolving it first.

Install Python before installing the hooks (`sudo pacman -S --needed python`).
From the checkout:

```sh
sudo install -Dm755 scripts/installer/limine_update.py /usr/local/lib/starch/update-limine
# Choose the installed firmware mode; use bios instead for BIOS installations.
sudo /usr/local/lib/starch/update-limine --setup efi
```

Setup only validates and records identity; it does not deploy a bootloader.
Existing enrollment is never overwritten automatically. Do not delete it to
bypass an identity mismatch: inspect and resolve the storage change first.

Create `/etc/pacman.d/hooks/05-starch-limine-check.hook`:

```ini
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = limine

[Action]
Description = Checking the Starch Limine loader target...
When = PreTransaction
Exec = /usr/local/lib/starch/update-limine --check
AbortOnFail
```

Create or replace `/etc/pacman.d/hooks/99-starch-limine.hook`:

```ini
[Trigger]
Operation = Install
Operation = Upgrade
Type = Package
Target = limine

[Action]
Description = Deploying the Starch Limine loader...
When = PostTransaction
Exec = /usr/local/lib/starch/update-limine
```

Then run `sudo /usr/local/lib/starch/update-limine --check` and
`sudo /usr/local/lib/starch/update-limine` to deploy the currently installed
package. Keep recovery media available for bootloader maintenance.

The pre-hook aborts an unsafe transaction. The post-hook checks again because
mounts or devices can change during a transaction. A post-hook failure **does
not roll back the package upgrade**: correct the reported condition and rerun
the updater before rebooting. Loader files are staged and flushed on the target
filesystem, then renamed individually. Multiple EFI replacements and BIOS
sector writes are not a single atomic operation; interruption or I/O failure
can still require recovery media and redeployment.

## Validation

Run `python -m unittest discover -s tests/unit -q`. Regression tests exercise
mount identity, filesystem/device mismatches, read-only and missing sources,
ambiguous BIOS partitions, duplicate UUIDs, changed enrolled identities, no
writes on failed validation, and staged deployment with unchanged menus.
VM upgrade/reboot tests remain necessary for both firmware modes and desktop
profiles before release.
