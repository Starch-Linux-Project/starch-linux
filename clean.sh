#!/usr/bin/env bash
set -euo pipefail
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
source "$REPO_ROOT/scripts/build/paths.sh"
dry_run=false
if [[ ${1:-} == --dry-run ]]; then dry_run=true; shift; fi
if (( $# == 0 )); then
    echo 'Usage: clean.sh [--dry-run] {work|cache|logs|inventory} ...' >&2
    exit 2
fi
command -v mountpoint >/dev/null
# Validate the complete request before deleting anything.
for name in "$@"; do validate_generated_dir "$name"; done
for name in "$@"; do
    target="$REPO_ROOT/build/$name"
    if $dry_run; then
        printf 'Would remove %s\n' "$target"
    elif [[ -d "$target" ]]; then
        # Never cross into nested filesystems or follow directory symlinks.
        rm -rf --one-file-system -- "$target"
    fi
done
