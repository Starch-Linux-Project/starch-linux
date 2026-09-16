#!/usr/bin/env bash
# Shared containment checks; callers set REPO_ROOT from their own location.
validate_build_root() {
    if [[ -L "$REPO_ROOT/build" || ( -e "$REPO_ROOT/build" && ! -d "$REPO_ROOT/build" ) ]]; then
        echo 'Refusing symlink or non-directory build root' >&2
        return 1
    fi
}
validate_generated_dir() {
    local name=$1
    case "$name" in work|cache|logs|inventory) ;; *) echo "Unsupported generated directory: $name" >&2; return 1 ;; esac
    validate_build_root || return 1
    if [[ -L "$REPO_ROOT/build/$name" || ( -e "$REPO_ROOT/build/$name" && ! -d "$REPO_ROOT/build/$name" ) ]]; then
        echo "Refusing symlink or non-directory: $name" >&2
        return 1
    fi
    if mountpoint -q "$REPO_ROOT/build/$name"; then
        echo "Refusing mounted directory: $name" >&2
        return 1
    fi
}
