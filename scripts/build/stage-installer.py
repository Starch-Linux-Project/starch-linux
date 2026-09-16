#!/usr/bin/env python3
"""Stage maintained installer inputs into a fresh archiso profile snapshot."""
from pathlib import Path
import shutil
import sys

SOURCE = Path(__file__).resolve().parents[2]


def stage(profile):
    fs = profile / 'airootfs'
    config = fs / 'etc/calamares'
    shutil.copytree(SOURCE / 'calamares', config, dirs_exist_ok=True)
    data = fs / 'usr/share/starch-installer'
    data.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SOURCE / 'manifests/minimal-packages.txt', data / 'minimal-packages.txt')
    shutil.copyfile(SOURCE / 'calamares/pacman.conf', data / 'pacman.conf')
    runtime = fs / 'usr/lib/starch-installer'
    shutil.copytree(SOURCE / 'scripts/installer', runtime, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    for name in ('preflight', 'bootstrap', 'configure', 'validate'):
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
    for relative in ('etc/skel/.config/kdeglobals', 'etc/xdg/konsolerc',
                     'etc/fastfetch/config.jsonc', 'usr/share/starch/fastfetch-text',
                     'usr/share/konsole/Starch Live.profile',
                     'usr/share/plasma/look-and-feel/org.starch.desktop'):
        source = fs / relative
        dest = overlay / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, dest, dirs_exist_ok=True)
        else:
            shutil.copyfile(source, dest)
    fish = overlay / 'etc/fish/conf.d/10-starch.fish'
    fish.parent.mkdir(parents=True, exist_ok=True)
    fish.write_text('if status is-interactive; and test (id -u) -ne 0\n    fastfetch\nend\n')
    konsole = overlay / 'usr/share/konsole/Starch Live.profile'
    (konsole.parent / 'Starch.profile').write_text(konsole.read_text().replace('Name=Starch Live', 'Name=Starch'))
    konsole.unlink()
    (overlay / 'etc/xdg/konsolerc').write_text('[Desktop Entry]\nDefaultProfile=Starch.profile\n')


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: stage-installer.py SNAPSHOT_PROFILE')
    profile = Path(sys.argv[1]).resolve()
    if profile == (SOURCE / 'archiso/profile').resolve() or not (profile / 'profiledef.sh').is_file():
        sys.exit('Installer staging requires a generated profile snapshot.')
    stage(profile)
