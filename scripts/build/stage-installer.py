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


def stage_wallpapers(fs, input_dir=None):
    """Turn source images into system Plasma wallpaper packages."""
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


def stage(profile, luu_input=None, wallpaper_input=None):
    fs = profile / 'airootfs'
    config = fs / 'etc/calamares'
    shutil.copytree(SOURCE / 'calamares', config, dirs_exist_ok=True)
    data = fs / 'usr/share/starch-installer'
    data.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'manifests/minimal-packages.txt', data / 'minimal-packages.txt')
    shutil.copyfile(SOURCE / 'calamares/pacman.conf', data / 'pacman.conf')
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
    # Explicit allowlist: none of the live user, sudo or network state is copied.
    for relative in ('etc/skel/.config/kdeglobals', 'etc/skel/.config/baloofilerc',
                     'etc/xdg/konsolerc',
                     'etc/nftables.conf',
                     'etc/fastfetch/config.jsonc', 'usr/share/starch/fastfetch-text',
                     'usr/share/starch/splash-starch.bmp',
                     'usr/share/plymouth/themes/starch',
                     'usr/share/konsole/Starch Live.profile',
                     'usr/share/plasma/look-and-feel/org.starch.desktop'):
        source = fs / relative
        dest = overlay / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            shutil.copyfile(source, dest)
    shutil.copyfile(SOURCE / 'calamares/branding/starch/starchlinux.png',
                    overlay / 'usr/share/plymouth/themes/starch/logo.png')
    fish = overlay / 'etc/fish/conf.d/10-starch.fish'
    fish.parent.mkdir(parents=True, exist_ok=True)
    fish.write_text('if status is-interactive; and test (id -u) -ne 0\n    fastfetch\nend\n')
    konsole = overlay / 'usr/share/konsole/Starch Live.profile'
    (konsole.parent / 'Starch.profile').write_text(konsole.read_text().replace('Name=Starch Live', 'Name=Starch'))
    konsole.unlink()
    (overlay / 'etc/xdg/konsolerc').write_text('[Desktop Entry]\nDefaultProfile=Starch.profile\n')
    stage_luu(fs, luu_input)
    stage_wallpapers(fs, wallpaper_input)


if __name__ == '__main__':
    if len(sys.argv) not in (2, 3, 4):
        sys.exit('Usage: stage-installer.py SNAPSHOT_PROFILE [LUU_INPUT [WALLPAPER_INPUT]]')
    profile = Path(sys.argv[1]).resolve()
    if profile == (SOURCE / 'archiso/profile').resolve() or not (profile / 'profiledef.sh').is_file():
        sys.exit('Installer staging requires a generated profile snapshot.')
    stage(profile, sys.argv[2] if len(sys.argv) >= 3 else None,
          sys.argv[3] if len(sys.argv) == 4 else None)
