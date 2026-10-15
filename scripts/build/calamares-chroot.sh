#!/usr/bin/env bash
set -euo pipefail

if (( $# != 2 )); then
    echo 'Usage: calamares-chroot.sh PACKAGE_DIR OUTPUT_DIR' >&2
    exit 2
fi

package_dir=$1
output_dir=$2
expected_package_dir=/build/calamares

[[ $package_dir == "$expected_package_dir" ]] || {
    echo "Refusing unexpected package build path: $package_dir" >&2
    exit 1
}
[[ $output_dir == /starch/output ]] || {
    echo "Refusing unexpected output path: $output_dir" >&2
    exit 1
}

pacman -Syu --noconfirm --needed \
    base-devel cmake extra-cmake-modules git kpmcore libpwquality ninja \
    parted polkit-qt6 pybind11 python python-jsonschema python-yaml qt6-base \
    qt6-svg qt6-tools yaml-cpp

id -u builduser >/dev/null 2>&1 || useradd -m builduser
install -d -o builduser -g builduser "$package_dir"
find "$package_dir" -mindepth 1 -maxdepth 1 -exec rm -rf -- {} +
cp -a /starch/package/. "$package_dir/"
chown -R builduser:builduser "$package_dir"

jobs=$(nproc)
runuser -u builduser -- env MAKEFLAGS="-j$jobs" \
    makepkg --dir "$package_dir" --clean --cleanbuild --force --noconfirm

shopt -s nullglob
# A numeric version excludes the separately generated calamares-starch-debug.
packages=("$package_dir"/calamares-starch-[0-9]*.pkg.tar.zst)
(( ${#packages[@]} == 1 )) || {
    echo "Expected exactly one Calamares package, found ${#packages[@]}" >&2
    exit 1
}
cp -- "${packages[0]}" "$output_dir/"
install -D -m 0644 "$package_dir/calamares-3.3.14.tar.gz" \
    "$output_dir/sources/calamares-3.3.14.tar.gz"
pacman -Q > "$output_dir/build-environment-packages.txt"
