#!/usr/bin/env bash
# Build target-only Lite packages; never install them on the build host.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
build_root="$repo_root/build/starch-lite"
chroot_dir="$build_root/config-chroot"
output_dir="$build_root/artix-repo"
package_dir="$repo_root/packages/starch-lite"
helper="$repo_root/scripts/build/starch-lite-chroot.sh"
[[ $# == 1 && ( $1 == --check || $1 == --build || $1 == --ensure ) ]] || {
    echo 'Usage: scripts/build/starch-lite.sh --check | --build | --ensure' >&2
    exit 2
}
for tool in arch-chroot pacstrap unshare sha256sum python3 curl bsdtar; do
    command -v "$tool" >/dev/null || { echo "Missing tool: $tool" >&2; exit 1; }
done
for path in "$repo_root/build" "$build_root" "$chroot_dir" "$output_dir"; do
    [[ ! -L $path && ( ! -e $path || -d $path ) ]] || { echo "Unsafe build path: $path" >&2; exit 1; }
done
input_hash=$(
    find "$package_dir" "$helper" "$repo_root/scripts/build/starch-lite.sh" -type f -print0 |
        sort -z | xargs -0 sha256sum | sha256sum | cut -d ' ' -f 1
)
[[ $1 != --check ]] || exit 0
if [[ $1 == --ensure && -f $output_dir/INPUT_SHA256 && -f $output_dir/SHA256SUMS ]] &&
    [[ $(<"$output_dir/INPUT_SHA256") == "$input_hash" ]] &&
    (cd "$output_dir" && sha256sum -c SHA256SUMS >/dev/null); then
    echo 'Reusing verified Starch Lite package bundle.'
    exit 0
fi
mkdir -p "$build_root" "$output_dir"
if [[ ! -x $chroot_dir/usr/bin/pacman ]]; then
    mkdir -p "$chroot_dir/etc/pacman.d/hooks"
    awk -v hooks="$chroot_dir/etc/pacman.d/hooks" '
        { print }
        /^\[options\]$/ { print "HookDir = " hooks }
    ' "$repo_root/calamares/pacman.conf" > "$build_root/bootstrap-pacman.conf"
    pacstrap -N -C "$build_root/bootstrap-pacman.conf" -K "$chroot_dir" base base-devel
fi
[[ -x $chroot_dir/usr/bin/pacman && -x $chroot_dir/usr/bin/bash ]] || {
    echo 'Starch Lite build root bootstrap failed.' >&2; exit 1;
}
unshare --map-auto --map-root-user -- bash -eu -c '
    root=$1
    install -d "$root/starch/package" "$root/starch/output"
    cp -a "$2/." "$root/starch/package/"
    cp "$3" "$root/starch/build.sh"
    cp "$4" "$root/etc/pacman.conf"
    cp -L /etc/resolv.conf "$root/etc/resolv.conf"
' bash "$chroot_dir" "$package_dir" "$helper" "$repo_root/calamares/pacman.conf"
arch-chroot -N -r "$chroot_dir" bash /starch/build.sh
# Only current generated archives belong in a bundle after a version update.
find "$output_dir" -maxdepth 1 -type f -name 'starch-lite*.pkg.tar.zst' -delete
unshare --map-auto --map-root-user -- cp -a "$chroot_dir/starch/output/." "$output_dir/"
printf '%s\n' "$input_hash" > "$output_dir/INPUT_SHA256"
python3 - "$output_dir" "$package_dir" <<'PY'
import hashlib, json, pathlib, subprocess, sys
root = pathlib.Path(sys.argv[1])
packages = []
pin = json.loads((pathlib.Path(sys.argv[2]) / 'artix-keyring.json').read_text())
archive = root / pin['filename']
if not archive.is_file() or hashlib.sha256(archive.read_bytes()).hexdigest() != pin['sha256']:
    subprocess.run(['curl', '--fail', '--location', '--retry', '2', '--max-time', '120',
                    '--output', str(archive), pin['url']], check=True)
if hashlib.sha256(archive.read_bytes()).hexdigest() != pin['sha256']:
    raise SystemExit('Artix bootstrap keyring checksum mismatch')
(root / 'sources/artix-keyring.json').write_text(json.dumps(pin, indent=2) + '\n')
for name in ('starch-lite', 'artix-keyring'):
    candidates = ([root / pin['filename']] if name == 'artix-keyring'
                  else sorted(root.glob(name + '-[0-9]*-*.pkg.tar.zst')))
    if len(candidates) != 1:
        raise SystemExit(f'Expected one {name} archive; found {len(candidates)}')
    archive = candidates[0]
    info = subprocess.check_output(['bsdtar', '-xOf', str(archive), '.PKGINFO'], text=True)
    if f'pkgname = {name}\n' not in info:
        raise SystemExit(f'Unexpected package identity: {archive.name}')
    packages.append(dict(name=name, filename=archive.name,
                         sha256=hashlib.sha256(archive.read_bytes()).hexdigest()))
(root / 'bundle.json').write_text(json.dumps(dict(format=2, repositories='artix-arch-extra', packages=packages), indent=2) + '\n')
PY
(cd "$output_dir" && find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)
echo "Starch Lite development bundle ready: $output_dir"
