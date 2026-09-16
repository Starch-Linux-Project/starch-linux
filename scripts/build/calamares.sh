#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
PACKAGE_DIR="$REPO_ROOT/packages/calamares"
BUILD_ROOT="$REPO_ROOT/build/calamares"
CHROOT_DIR="$BUILD_ROOT/chroot"
OUTPUT_DIR="$BUILD_ROOT/repo"
PACMAN_CONFIG="$REPO_ROOT/calamares/pacman.conf"
CHROOT_HELPER="$REPO_ROOT/scripts/build/calamares-chroot.sh"

usage() {
    echo 'Usage: scripts/build/calamares.sh --check | --build | --ensure' >&2
}

if (( $# != 1 )) || [[ $1 != --check && $1 != --build && $1 != --ensure ]]; then
    usage
    exit 2
fi

for tool in arch-chroot makepkg pacstrap repo-add sha256sum unshare; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done

[[ -f $PACMAN_CONFIG ]] || { echo "Missing pacman config: $PACMAN_CONFIG" >&2; exit 1; }
[[ -f $PACKAGE_DIR/PKGBUILD ]] || { echo "Missing package recipe: $PACKAGE_DIR/PKGBUILD" >&2; exit 1; }
[[ -x $CHROOT_HELPER ]] || { echo "Missing chroot helper: $CHROOT_HELPER" >&2; exit 1; }
for path in "$REPO_ROOT/build" "$BUILD_ROOT" "$CHROOT_DIR" "$OUTPUT_DIR"; do
    [[ ! -L $path && ( ! -e $path || -d $path ) ]] || { echo "Unsafe build directory: $path" >&2; exit 1; }
done

input_hash=$(
    find "$PACKAGE_DIR" "$CHROOT_HELPER" -maxdepth 1 -type f -print0 |
        sort -z |
        xargs -0 sha256sum |
        sha256sum |
        cut -d ' ' -f 1
)

if (( EUID != 0 )); then
    unshare --map-auto --map-root-user -- true
fi

[[ $1 != --check ]] || exit 0

mkdir -p -- "$BUILD_ROOT" "$OUTPUT_DIR"

if [[ $1 == --ensure && -f $OUTPUT_DIR/INPUT_SHA256 && -f $OUTPUT_DIR/SHA256SUMS ]] &&
    [[ $(<"$OUTPUT_DIR/INPUT_SHA256") == "$input_hash" ]] &&
    (cd "$OUTPUT_DIR" && sha256sum -c SHA256SUMS >/dev/null); then
    package_file=$(find "$OUTPUT_DIR" -maxdepth 1 -type f \
        -name 'calamares-starch-[0-9]*.pkg.tar.zst' -printf '%f\n' | sort -V | tail -n1)
    [[ -n $package_file && -f $OUTPUT_DIR/starch.db.tar.gz ]] || exit 1
    printf 'Reusing verified Calamares package: %s\nLocal repository: %s\n' \
        "$OUTPUT_DIR/$package_file" "$OUTPUT_DIR/starch.db.tar.gz"
    exit 0
fi

if [[ ! -x $CHROOT_DIR/usr/bin/pacman ]]; then
    mkdir -p -- "$CHROOT_DIR"
    pacstrap -N -C "$PACMAN_CONFIG" -K "$CHROOT_DIR" \
        base-devel cmake extra-cmake-modules git kpmcore libpwquality ninja \
        parted polkit-qt6 pybind11 python python-jsonschema qt6-base qt6-svg \
        qt6-tools python-yaml yaml-cpp
fi

# The quoted script expands its positional arguments inside the namespace.
# shellcheck disable=SC2016
unshare --map-auto --map-root-user --mount --pid --fork --mount-proc \
    bash -eu -o pipefail -c '
        chroot_dir=$1
        package_dir=$2
        pacman_config=$3
        chroot_helper=$4

        install -d "$chroot_dir/starch/package" "$chroot_dir/starch/output"
        find "$chroot_dir/starch/package" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
        find "$chroot_dir/starch/output" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
        cp -a "$package_dir"/. "$chroot_dir/starch/package/"
        cp "$pacman_config" "$chroot_dir/etc/pacman.conf"
        cp -L /etc/resolv.conf "$chroot_dir/etc/resolv.conf"
        cp "$chroot_helper" "$chroot_dir/starch/calamares-chroot.sh"
        chmod 0755 "$chroot_dir/starch/calamares-chroot.sh"
    ' bash "$CHROOT_DIR" "$PACKAGE_DIR" "$PACMAN_CONFIG" "$CHROOT_HELPER"

arch-chroot -N -r "$CHROOT_DIR" /starch/calamares-chroot.sh \
    /build/calamares /starch/output

unshare --map-auto --map-root-user --mount --pid --fork --mount-proc \
    cp -a "$CHROOT_DIR/starch/output/." "$OUTPUT_DIR/"

package_file=$(find "$OUTPUT_DIR" -maxdepth 1 -type f -name 'calamares-starch-[0-9]*.pkg.tar.zst' -printf '%f\n' | sort -V | tail -n1)
[[ -n $package_file ]] || { echo 'Calamares package was not produced' >&2; exit 1; }

repo-add -R "$OUTPUT_DIR/starch.db.tar.gz" "$OUTPUT_DIR/$package_file"

source_url="https://github.com/calamares/calamares/releases/download/v3.3.14/calamares-3.3.14.tar.gz"
source_archive="$OUTPUT_DIR/sources/calamares-3.3.14.tar.gz"
[[ -f $source_archive ]] || { echo 'Could not locate the verified source archive' >&2; exit 1; }
mkdir -p "$OUTPUT_DIR/notices"
cp -a "$REPO_ROOT/docs/third-party/calamares-3.3.14/." "$OUTPUT_DIR/notices/"

printf '%s\n' "$source_url" > "$OUTPUT_DIR/sources/SOURCE_URL"
printf '%s\n' "$input_hash" > "$OUTPUT_DIR/INPUT_SHA256"
pacman -Qp "$OUTPUT_DIR/$package_file" > "$OUTPUT_DIR/package-version.txt"
pacman -Qip "$OUTPUT_DIR/$package_file" > "$OUTPUT_DIR/package-info.txt"
(
    cd "$OUTPUT_DIR"
    # SHA256SUMS is explicitly excluded from the input set.
    # shellcheck disable=SC2094
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

printf 'Calamares package ready: %s\nLocal repository: %s\n' \
    "$OUTPUT_DIR/$package_file" "$OUTPUT_DIR/starch.db.tar.gz"
