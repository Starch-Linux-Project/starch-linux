# Boot splash

Installed UEFI systems embed `/usr/share/starch/splash-starch.bmp` in the
Linux LTS unified kernel image. The systemd EFI stub centers the image on
screen. The Starch logo stays at its native 64×64 size on a black background.
This replaces the Arch splash previously selected by the installer preset.

The bitmap is converted from the existing installer logo without resizing.
To regenerate it from the repository root with ImageMagick:

```sh
magick calamares/branding/starch/starchlinux.png -background black -alpha remove -alpha off -type TrueColor BMP3:archiso/profile/airootfs/usr/share/starch/splash-starch.bmp
```

The installer stages this uncompressed 24-bit BMP into the target before
generating the UKI. Future kernel rebuilds use the same installed bitmap.

Installed BIOS systems use Plymouth with the `starch` script theme. The
installer adds the Plymouth package only for BIOS installs, selects the
theme before rebuilding the initramfs, and adds `quiet splash` to the Limine
kernel command line. The theme displays the same native 64×64 installer
logo, centered on black, with no animation. Press Escape to show boot text.
Graphical display requires a working KMS/framebuffer driver; machines
without one may fall back to text.

The live BIOS ISO boot menu uses `archiso/profile/syslinux/splash.png`, a
640×480 RGB PNG with the same native 64×64 Starch logo on black. The logo
sits above the menu at (288, 48), leaving the boot options unobstructed.
This replaces the upstream Arch Linux background. Regenerate it from the
existing black-background bitmap with:

```sh
ffmpeg -hide_banner -loglevel error -y -i archiso/profile/airootfs/usr/share/starch/splash-starch.bmp -vf 'pad=640:480:288:48:black,format=rgb24' -frames:v 1 -update 1 archiso/profile/syslinux/splash.png
```

This live boot menu background is separate from the installed-system splashes
above. Rebuild the ISO to include a changed background.
