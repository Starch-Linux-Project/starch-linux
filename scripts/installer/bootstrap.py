import json
import hashlib
import shutil
from runtime import DATA, LOG, STATE, chroot, command, target
from profiles import LITE_PACKAGES, is_lite, has_xfce, pacman_config, verified_bundle
from repositories import prepare_lite_keyring


def pacstrap(root, config_path, keyring_args, packages, attempts=3):
    """Resume the package transaction after transient mirror failures."""
    argv = ['pacstrap', '-K', '-M', '-C', config_path, root, *keyring_args, *packages]
    for attempt in range(1, attempts + 1):
        try:
            command(argv)
            return
        except RuntimeError:
            if attempt == attempts:
                raise
            with LOG.open('a') as log:
                log.write(f'pacstrap attempt {attempt} failed; retrying with cached downloads.\n')


def run(gs):
    root = target(gs)
    selection = json.loads((STATE / 'selection.json').read_text())
    packages = selection['packages']
    archives = []
    config_path = pacman_config(DATA, gs)
    keyring_args = []
    if is_lite(gs):
        archives = verified_bundle(DATA / 'lite')
        if hashlib.sha256((DATA / 'lite/bundle.json').read_bytes()).hexdigest() != selection['lite_bundle_sha256']:
            raise RuntimeError('The Starch Lite bundle changed after preflight.')
        if hashlib.sha256(config_path.read_bytes()).hexdigest() != selection['repositories_sha256']:
            raise RuntimeError('The Lite repository configuration changed after preflight.')
        keyring_args = ['--gpgdir', prepare_lite_keyring(archives, STATE)]
        # artix-keyring itself comes from the signed Artix repository transaction.
        archives = [p for p in archives if p.name.startswith('starch-lite-')]
    # Fresh root and keyring; never copy the live filesystem or its users.
    pacstrap(root, config_path, keyring_args, packages)
    shutil.copyfile(config_path, root / 'etc/pacman.conf')
    if is_lite(gs):
        chroot(root, 'pacman-key', '--populate', 'artix', 'archlinux')
    if archives:
        cache = root / 'var/cache/starch-lite'
        cache.mkdir(parents=True, exist_ok=True)
        for archive in archives:
            shutil.copyfile(archive, cache / archive.name)
        # Scoped only to these verified local archives; installed pacman.conf
        # retains Required signatures and the selected repositories.
        config = cache / 'pacman.conf'
        config.write_text(config_path.read_text().replace(
            'LocalFileSigLevel = Required', 'LocalFileSigLevel = Optional'))
        chroot(root, 'pacman', '--config', '/var/cache/starch-lite/pacman.conf',
               '-U', '--noconfirm', '--',
               *['/var/cache/starch-lite/' + archive.name for archive in archives])
        config.unlink()
    # Seed /etc/skel before Calamares creates the account and home directory.
    ignore = (shutil.ignore_patterns('kdeglobals', 'kwinrc', 'baloofilerc', 'plasma')
              if has_xfce(gs) else None)
    shutil.copytree(DATA / 'target-overlay', root, dirs_exist_ok=True, ignore=ignore)
    if has_xfce(gs):
        panel = root / 'etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml'
        panel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / 'usr/share/starch-lite/xfce-panel.xml', panel)
    # Archiso defaults nested overlay files to 0644 unless profiledef preserves
    # their mode. Enforce executability here as well before target validation.
    (root / 'usr/local/bin/linux-update-utility.AppImage').chmod(0o755)
    manifests = root / 'var/log/starch-installer'
    manifests.mkdir(parents=True, exist_ok=True, mode=0o700)
    requested = packages + list(LITE_PACKAGES) if archives else packages
    (manifests / 'requested-packages.txt').write_text('\n'.join(requested) + '\n')
    (manifests / 'profile.txt').write_text(selection.get('profile', 'standard') + '\n')
