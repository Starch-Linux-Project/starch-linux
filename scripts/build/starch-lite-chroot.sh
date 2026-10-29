#!/usr/bin/env bash
# Build only Starch's configuration package in the dedicated Arch build root.
set -euo pipefail
[[ -d /starch/package/integration && -d /starch/output ]] || exit 2
# Reused roots may have an unpopulated or stale active trust database.
pacman-key --init
pacman-key --populate archlinux
pacman -Sy --noconfirm --needed archlinux-keyring
pacman -Syu --noconfirm --needed base-devel
id builduser >/dev/null 2>&1 || useradd -m builduser
build_dir=$(mktemp -d /build-starch-lite-XXXXXXXX)
cp -a /starch/package/integration "$build_dir/"
python3 - "$build_dir/integration" <<'PY'
import hashlib, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
subprocess.run(['tar', '--sort=name', '--mtime=@0', '--owner=0', '--group=0',
                '--numeric-owner', '-czf', str(root / 'integration.tar.gz'),
                '-C', str(root), 'root'], check=True)
recipe = root / 'PKGBUILD'
recipe.write_text(recipe.read_text().replace('INTEGRATION_SHA256',
    hashlib.sha256((root / 'integration.tar.gz').read_bytes()).hexdigest()))
PY
chown -R builduser:builduser "$build_dir"
# The package contains scripts/configuration only. Artix runtime dependencies
# are resolved during installer preflight, not installed into this Arch root.
runuser -u builduser -- makepkg --dir "$build_dir/integration" --cleanbuild --noconfirm --nodeps
find /starch/output -mindepth 1 -maxdepth 1 -type f -delete
cp "$build_dir/integration/"starch-lite-*-x86_64.pkg.tar.zst /starch/output/
mkdir -p /starch/output/sources
cp "$build_dir/integration/integration.tar.gz" /starch/output/sources/
pacman -Q > /starch/output/build-environment-packages.txt
