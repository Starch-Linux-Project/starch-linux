#!/usr/bin/env python3
"""Stage maintained installer inputs into a fresh archiso profile snapshot."""
from pathlib import Path
import hashlib
import json
import re
import shutil
import sys

SOURCE = Path(__file__).resolve().parents[2]

LUU_FILES = {
    'appimage': Path('usr/local/bin/linux-update-utility.AppImage'),
    'icon': Path('usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg'),
    'desktop': Path('usr/share/applications/linux-update-utility.desktop'),
}

WALLPAPER_SUFFIXES = {'.avif', '.bmp', '.gif', '.jpeg', '.jpg', '.jxl', '.png', '.svg', '.tif', '.tiff', '.webp'}
COSMIC_WALLPAPER_SUFFIXES = {'.avif', '.jpeg', '.jpg', '.jxl', '.png', '.webp'}
EVERGREEN_SOURCE = 'wyxina-tree-8559118.jpg'
COSMIC_BACKGROUNDS = Path('usr/share/backgrounds/starch')
COSMIC_DEFAULT = COSMIC_BACKGROUNDS / 'evergreen.jpg'


def stage_wallpapers(fs, input_dir=None):
    """Stage source images for the Plasma and COSMIC wallpaper choosers."""
    input_dir = Path(input_dir) if input_dir is not None else SOURCE / 'wallpapers'
    if not input_dir.exists():
        return
    if input_dir.is_symlink() or not input_dir.is_dir():
        raise RuntimeError('wallpapers must be a real directory')
    images = sorted(path for path in input_dir.rglob('*')
                    if path.suffix.lower() in WALLPAPER_SUFFIXES)
    if any(path.is_symlink() or not path.is_file() for path in images):
        raise RuntimeError('Wallpaper inputs must be regular, non-symlink files')

    overlay = fs / 'usr/share/starch-installer/target-overlay'
    for source in images:
        relative = source.relative_to(input_dir).as_posix()
        slug = re.sub(r'[^a-z0-9]+', '-', source.stem.lower()).strip('-') or 'wallpaper'
        digest = hashlib.sha256(relative.encode()).hexdigest()[:8]
        package_name = f'Starch-{slug}-{digest}'
        if relative == EVERGREEN_SOURCE:
            package_name = 'Starch-Evergreen'
        plugin_id = f'org.starch.wallpaper.{slug}.{digest}'
        display_name = re.sub(r'[_-]+', ' ', source.stem).strip().title() or 'Starch Wallpaper'
        metadata = {
            'KPlugin': {
                'Description': 'Wallpaper supplied with Starch Linux',
                'Id': plugin_id,
                'Name': display_name,
            },
            'KPackageStructure': 'Plasma/Wallpaper',
        }
        # Plasma wallpaper packages conventionally identify a single image by
        # a resolution-shaped filename. Qt still reads the image's real size.
        image_name = f'3840x2160{source.suffix.lower()}'
        for root in (fs, overlay):
            package = root / 'usr/share/wallpapers' / package_name
            destination = package / 'contents/images' / image_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
            (package / 'metadata.json').write_text(json.dumps(metadata, indent=4) + '\n')

        # COSMIC Settings discovers system wallpapers below
        # /usr/share/backgrounds and only descends three levels. Keep its
        # copies shallow and collision-safe instead of exposing Plasma's
        # package layout, which is one level too deep.
        if source.suffix.lower() in COSMIC_WALLPAPER_SUFFIXES:
            background_name = f'{slug}-{digest}{source.suffix.lower()}'
            if relative == EVERGREEN_SOURCE:
                background_name = COSMIC_DEFAULT.name
            for root in (fs, overlay):
                background = root / COSMIC_BACKGROUNDS / background_name
                background.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, background)

    # Evergreen is a preferred initial choice, not a required COSMIC asset.
    # Only seed the selection when the corresponding input was supplied.
    selections = [
        fs / 'usr/share/starch-installer/desktop-overlays' / desktop
        / 'etc/skel/.config/cosmic/com.system76.CosmicBackground/v1/all'
        for desktop in ('cosmic', 'cosmic-lite')
    ]
    for config in selections:
        config.unlink(missing_ok=True)
    default = fs / COSMIC_DEFAULT
    if default.is_file():
        selection = ('(output: "all", source: Path("/' + COSMIC_DEFAULT.as_posix()
                     + '"), filter_by_theme: false, rotation_frequency: 900, '
                     'filter_method: Lanczos, scaling_mode: Zoom, '
                     'sampling_method: Alphanumeric)\n')
        for config in selections:
            config.parent.mkdir(parents=True, exist_ok=True)
            config.write_text(selection)


def stage_luu(fs, input_dir=None):
    """Install local LUU inputs into the live image and installed-system overlay."""
    input_dir = Path(input_dir) if input_dir is not None else SOURCE / 'luu-input'
    appimages = list(input_dir.glob('*.AppImage'))
    icons = list(input_dir.glob('*.svg'))
    if not appimages and not icons:
        return
    if len(appimages) != 1 or len(icons) != 1:
        raise RuntimeError('luu-input must contain exactly one *.AppImage and one *.svg file')
    if any(path.is_symlink() or not path.is_file() for path in (*appimages, *icons)):
        raise RuntimeError('Linux Update Utility inputs must be regular, non-symlink files')

    desktop = SOURCE / 'packages/linux-update-utility/linux-update-utility.desktop'
    sources = {'appimage': appimages[0], 'icon': icons[0], 'desktop': desktop}
    overlay = fs / 'usr/share/starch-installer/target-overlay'
    for name, relative in LUU_FILES.items():
        mode = 0o755 if name == 'appimage' else 0o644
        for root in (fs, overlay):
            destination = root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(sources[name], destination)
            destination.chmod(mode)


def stage_lite(fs, input_dir):
    config = fs / 'etc/calamares/modules/starchadvanced.conf'
    config.write_text('liteEnabled: false\n')
    if input_dir is None:
        return
    sys.path.insert(0, str(SOURCE / 'scripts/installer'))
    from profiles import verified_bundle
    archives = verified_bundle(input_dir)
    destination = fs / 'usr/share/starch-installer/lite'
    destination.mkdir(parents=True, exist_ok=True)
    for archive in archives:
        shutil.copyfile(archive, destination / archive.name)
    shutil.copyfile(Path(input_dir) / 'bundle.json', destination / 'bundle.json')
    config.write_text('liteEnabled: true\n')


def stage(profile, luu_input=None, wallpaper_input=None, lite_input=None):
    fs = profile / 'airootfs'
    # Keep live and installed banners sourced from the maintained root artwork.
    artwork = fs / 'usr/share/starch/fastfetch-text'
    artwork.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'fastfetch-text', artwork)
    config = fs / 'etc/calamares'
    shutil.copytree(SOURCE / 'calamares', config, dirs_exist_ok=True)
    stage_lite(fs, lite_input)
    data = fs / 'usr/share/starch-installer'
    data.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'manifests/minimal-packages.txt', data / 'minimal-packages.txt')
    shutil.copyfile(SOURCE / 'calamares/pacman.conf', data / 'pacman.conf')
    shutil.copyfile(SOURCE / 'calamares/pacman-lite.conf', data / 'pacman-lite.conf')
    runtime = fs / 'usr/lib/starch-installer'
    shutil.copytree(SOURCE / 'scripts/installer', runtime, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    for name in ('preflight', 'bootstrap', 'configure', 'limine', 'validate'):
        (config / 'modules' / f'starch-{name}.conf').write_text('{}\n')
        module = fs / 'usr/lib/calamares/modules' / f'starch-{name}'
        module.mkdir(parents=True, exist_ok=True)
        (module / 'module.desc').write_text(f'type: job\nname: starch-{name}\ninterface: python\nscript: main.py\nweight: {20 if name == "bootstrap" else 1}\n')
        (module / 'main.py').write_text(
            'import sys\nimport libcalamares\n'
            'sys.path.insert(0, "/usr/lib/starch-installer")\n'
            f'import {name}\nfrom runtime import run_stage\n\n'
            f'def pretty_name():\n    return "Starch: {name}"\n\n'
            f'def run():\n    return run_stage("{name}", libcalamares.globalstorage, {name}.run)\n')
    overlay = data / 'target-overlay'
    # Remove the former shared rotation overlay when re-staging an existing tree.
    for name in ('usr/lib/starch/rotation.py',
                 'etc/xdg/autostart/starch-rotation.desktop',
                 'usr/share/applications/starch-rotation-lock.desktop'):
        (overlay / name).unlink(missing_ok=True)
    shutil.copytree(SOURCE / 'packages/starch-rotation/root', data / 'rotation-overlay', dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    # Explicit allowlist: none of the live user, sudo or network state is copied.
    for relative in ('etc/skel/.config/kdeglobals', 'etc/skel/.config/baloofilerc',
                     'etc/skel/.config/kwinrc',
                     'etc/xdg/kscreenlockerrc',
                     'usr/share/sddm/themes/breeze/theme.conf.user',
                     'etc/nftables.conf',
                     'etc/fastfetch/config.jsonc', 'usr/share/starch/fastfetch-text',
                     'usr/share/starch/splash-starch.bmp',
                     'usr/share/plymouth/themes/starch',
                     'usr/share/plasma/look-and-feel/org.starch.desktop'):
        source = fs / relative
        desktop_only = relative.startswith(('etc/skel/.config/', 'etc/xdg/kscreenlocker',
                                            'usr/share/sddm/', 'usr/share/plasma/'))
        dest = (data / 'desktop-overlays/plasma' if desktop_only else overlay) / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            shutil.copyfile(source, dest)
    shutil.copyfile(SOURCE / 'calamares/branding/starch/starchlinux.png',
                    overlay / 'usr/share/plymouth/themes/starch/logo.png')
    for desktop in ('cosmic', 'cosmic-lite'):
        source = SOURCE / 'packages/starch-cosmic' / ('root' if desktop == 'cosmic' else 'lite-root')
        shutil.copytree(source, data / 'desktop-overlays' / desktop, dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'))
    fish = overlay / 'etc/fish/conf.d/10-starch.fish'
    fish.parent.mkdir(parents=True, exist_ok=True)
    fish.write_text('if status is-interactive; and test (id -u) -ne 0\n    fastfetch\nend\n')
    stage_luu(fs, luu_input)
    stage_wallpapers(fs, wallpaper_input)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3, 4):
        sys.exit('Usage: stage-installer.py SNAPSHOT_PROFILE [LUU_INPUT [WALLPAPER_INPUT]]')
    profile = Path(sys.argv[1]).resolve()
    if profile == (SOURCE / 'archiso/profile').resolve() or not (profile / 'profiledef.sh').is_file():
        sys.exit('Installer staging requires a generated profile snapshot.')
    stage(profile, sys.argv[2] if len(sys.argv) >= 3 else None,
          sys.argv[3] if len(sys.argv) == 4 else None,
          SOURCE / 'build/starch-lite/artix-repo')
