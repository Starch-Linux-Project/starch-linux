# Starch wallpapers

Add wallpaper images anywhere in this directory. During an ISO build, each
supported image is packaged separately for Plasma and installed in both the
live environment and the system produced by Calamares. Formats supported by
COSMIC are also copied to `/usr/share/backgrounds/starch`, where COSMIC
Settings discovers system wallpapers.

When present, `wyxina-tree-8559118.jpg` is the initial Evergreen selection. It
is packaged as `Starch-Evergreen` for Plasma and as `evergreen.jpg` for COSMIC.
COSMIC does not require this particular image: omitting it leaves the upstream
default behavior intact while all other supplied backgrounds remain available
in the wallpaper menu.

Supported filename extensions are AVIF, BMP, GIF, JPEG, JXL, PNG, SVG, TIFF,
and WebP. Source filenames become the display names shown by KDE.
