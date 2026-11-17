#!/usr/bin/env bash
# Exercise the actual plugin with fake transactions inside the build chroot.
set -euo pipefail
repo_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd -P)
chroot_dir="$repo_root/build/calamares/chroot"
source_archive="$repo_root/build/calamares/repo/sources/calamares-3.3.14.tar.gz"
[[ -f $chroot_dir/usr/lib/starch-installer/additional.py && -f $source_archive ]]
# The private bind mount substitutes the helper only for this test namespace.
# It disappears even if the test crashes; no package manager or disk job runs.
unshare --map-auto --map-root-user --mount --fork bash -eu -o pipefail -c '
    root=$1
    repo=$2
    archive=$3
    test_dir="$root/starch/software-test"
    mkdir -p "$test_dir"
    tar -xf "$archive" -C "$test_dir" --strip-components=2 \
        calamares-3.3.14/src/libcalamares calamares-3.3.14/src/libcalamaresui
    cp "$repo/tests/calamares/software-selection.cpp" "$test_dir/"
    mount --bind "$repo/tests/calamares/software-helper.py" "$root/usr/lib/starch-installer/additional.py"
    chroot "$root" /bin/bash -eu -c '\''
        cd /starch/software-test
        g++ -fPIC software-selection.cpp -Ilibcalamares -Ilibcalamaresui \
            $(pkg-config --cflags --libs Qt6Widgets) -lcalamares -lcalamaresui \
            -o software-selection
        QT_QPA_PLATFORM=offscreen ./software-selection
    '\''
' bash "$chroot_dir" "$repo_root" "$source_archive"
