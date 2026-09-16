#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source "$REPO_ROOT/scripts/build/paths.sh"
if (( $# != 1 )) || [[ $1 != --check && $1 != --build && $1 != --compile ]]; then
    echo 'Usage: build.sh --check | --build | --compile' >&2
    exit 2
fi
failed=0
for tool in mkarchiso pacman realpath df mountpoint python3 sha256sum tee; do
    if ! command -v "$tool" >/dev/null; then echo "Missing tool: $tool" >&2; failed=1; fi
done
for name in work cache logs; do
    if ! validate_generated_dir "$name"; then failed=1; fi
done
if [[ -L "$REPO_ROOT/starch-out" || ( -e "$REPO_ROOT/starch-out" && ! -d "$REPO_ROOT/starch-out" ) ]]; then
    echo 'Refusing symlink or non-directory ISO output root' >&2
    failed=1
fi
if mountpoint -q "$REPO_ROOT/starch-out"; then
    echo 'Refusing mounted ISO output root' >&2
    failed=1
fi
for file in profiledef.sh packages.x86_64 pacman.conf; do
    if [[ ! -f "$REPO_ROOT/archiso/profile/$file" ]]; then echo "Missing profile file: $file" >&2; failed=1; fi
done
if [[ ! -d "$REPO_ROOT/archiso/profile/airootfs" ]]; then echo 'Missing profile airootfs directory' >&2; failed=1; fi
available=$(df -Pk -- "$REPO_ROOT" | awk 'NR==2 {print $4}')
if [[ ! $available =~ ^[0-9]+$ ]] || (( available < 20 * 1024 * 1024 )); then
    echo 'Need at least 20 GiB available (provisional development threshold)' >&2; failed=1
fi
(( failed == 0 )) || exit "$failed"
[[ $1 != --check ]] || exit 0
if (( EUID != 0 )); then
    # Archiso 90 supports rootless builds with subordinate UID/GID mappings.
    unshare --map-auto --map-root-user -- true
fi
# Build/reuse the pinned installer in an isolated official-Arch build root.
"$REPO_ROOT/scripts/build/calamares.sh" --ensure
mkdir -p -- "$REPO_ROOT/build/"{work,cache,logs} "$REPO_ROOT/starch-out"
# Fresh paths avoid mkarchiso's run-once markers reusing an older profile.
run_dir=$(mktemp -d "$REPO_ROOT/build/work/run-XXXXXXXX")
run_id=${run_dir##*/}
output="$REPO_ROOT/starch-out/$run_id"
if [[ $1 == --compile ]]; then
    output="$run_dir/artifacts"
fi
mkdir -- "$output"
log="$REPO_ROOT/build/logs/$run_id.log"
exec > >(tee "$log") 2>&1
printf 'Build output: %s\nBuild log: %s\n' "$output" "$log"
report_exit() {
    local build_status=$?
    if (( build_status != 0 )); then
        printf 'Build failed (exit %s). See %s\n' "$build_status" "$log"
    fi
}
trap report_exit EXIT
# Snapshot inputs so edits during a build cannot change what it consumes.
cp -a -- "$REPO_ROOT/archiso/profile" "$run_dir/profile"
python3 "$REPO_ROOT/scripts/build/stage-installer.py" "$run_dir/profile"
cp -a -- "$REPO_ROOT/build/calamares/repo" "$run_dir/installer-repo"
printf '\ncalamares-starch\n' >>"$run_dir/profile/packages.x86_64"
printf '\n[starch]\nSigLevel = Optional TrustAll\nServer = file://%s\n' "$run_dir/installer-repo" >>"$run_dir/profile/pacman.conf"
python3 - "$run_dir/profile/pacman.conf" "$REPO_ROOT/build/cache" <<'CONFIG'
import pathlib, sys
p = pathlib.Path(sys.argv[1])
p.write_text(p.read_text().replace('[options]\n', '[options]\nCacheDir = ' + sys.argv[2] + '\n', 1))
CONFIG
pacman -Q archiso >"$output/build-report.txt"
cat "$run_dir/installer-repo/package-version.txt" >>"$output/build-report.txt"
cp -- "$REPO_ROOT/manifests/minimal-packages.txt" "$output/target-requested-packages.txt"
cp -a -- "$run_dir/installer-repo/sources" "$output/calamares-sources"
cp -a -- "$run_dir/installer-repo/notices" "$output/calamares-notices"
tar -C "$REPO_ROOT" -czf "$output/starch-installer-source.tar.gz" build.sh scripts calamares manifests packages/calamares tests README.md docs/third-party-provenance.tsv
cp -- "$run_dir/profile/packages.x86_64" "$output/requested-packages.txt"
# Preserve the exact source profile, including symlinks and file permissions.
tar -C "$run_dir" -czf "$output/profile-source.tar.gz" profile
sha256sum "$output/profile-source.tar.gz" >>"$output/build-report.txt"
mkarchiso -v -w "$run_dir/work" -o "$output" "$run_dir/profile"
cp -- "$run_dir/work/iso/arch/pkglist.x86_64.txt" "$output/live-packages.txt"
if (( EUID == 0 )); then
    python3 "$REPO_ROOT/scripts/validate/built-live.py" "$run_dir/work/x86_64/airootfs"
else
    unshare --map-auto --map-root-user -- python3 "$REPO_ROOT/scripts/validate/built-live.py" "$run_dir/work/x86_64/airootfs"
fi
awk '$1 == "linux" || $1 == "plasma-workspace" || $1 == "sddm" || $1 == "fastfetch"' "$output/live-packages.txt" >>"$output/build-report.txt"
shopt -s nullglob
isos=("$output/"*.iso)
(( ${#isos[@]} == 1 )) || { echo 'Expected exactly one ISO' >&2; exit 1; }
(cd -- "$output" && sha256sum -- "${isos[0]##*/}" >SHA256SUMS)
printf 'Build and filesystem validation passed; VM boot remains untested.\n' >>"$output/build-report.txt"
if [[ $1 == --compile ]]; then
    # Include the run ID so same-day builds coexist. Link without overwriting.
    destination="$REPO_ROOT/starch-out/${isos[0]##*/}"
    destination="${destination%.iso}-$run_id.iso"
    ln -- "${isos[0]}" "$destination"
    rm -- "${isos[0]}"
    isos=("$destination")
fi
printf 'ISO ready: %s\n' "${isos[0]}"
