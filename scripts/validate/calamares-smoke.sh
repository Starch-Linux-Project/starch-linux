#!/usr/bin/env bash
# Read-only installer launch: no automated interaction or installation jobs.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
build_root="$repo_root/build/calamares"
chroot_dir="$build_root/chroot"
profile="$build_root/smoke-profile"
package=$(find "$build_root/repo" -maxdepth 1 -type f \
    -name 'calamares-starch-[0-9]*.pkg.tar.zst' -printf '%p\n' | sort -V | tail -n1)
[[ -n $package ]] || { echo 'No built Calamares package found for smoke test.' >&2; exit 1; }
mkdir -p "$profile"
cp -a "$repo_root/archiso/profile/." "$profile/"
python3 "$repo_root/scripts/build/stage-installer.py" "$profile"
# Expand positional arguments inside the namespace, not in this shell.
# shellcheck disable=SC2016
unshare --map-auto --map-root-user -- bash -eu -c '
    source_fs=$1
    build_chroot=$2
    package=$3
    cp "$package" "$build_chroot/starch/calamares-test.pkg.tar.zst"
    printf "[options]\nArchitecture = auto\nSigLevel = Required DatabaseOptional\nLocalFileSigLevel = Optional\n" > "$build_chroot/starch/smoke-pacman.conf"
    for relative in etc/calamares usr/share/starch-installer usr/lib/starch-installer; do
        mkdir -p "$build_chroot/$relative"
        cp -a "$source_fs/$relative/." "$build_chroot/$relative/"
    done
    mkdir -p "$build_chroot/usr/lib/calamares/modules"
    cp -a "$source_fs/usr/lib/calamares/modules/"starch-* "$build_chroot/usr/lib/calamares/modules/"
' bash "$profile/airootfs" "$chroot_dir" "$package"
arch-chroot -N -r "$chroot_dir" pacman --config /starch/smoke-pacman.conf -U --noconfirm /starch/calamares-test.pkg.tar.zst
set +e
arch-chroot -N -r "$chroot_dir" env QT_QPA_PLATFORM=offscreen XDG_CACHE_HOME=/root/.cache XDG_CONFIG_HOME=/root/.config timeout 20s calamares -d -D6 >"$build_root/smoke.log" 2>&1
status=$?
set -e
# timeout means the GUI stayed open; crashes and immediate exits are failures.
[[ $status == 124 ]] || { cat "$build_root/smoke.log"; exit 1; }
echo "Installer remained open for the launch smoke check. Review $build_root/smoke.log for module errors."
