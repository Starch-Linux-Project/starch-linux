#!/usr/bin/env bash
set -euo pipefail
umask 077
REPO_ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
source "$REPO_ROOT/scripts/build/paths.sh"
if (( $# != 0 )); then echo 'Usage: collect-inventory.sh (no elevation needed)' >&2; exit 2; fi
validate_generated_dir inventory
mkdir -p -- "$REPO_ROOT/build/inventory"
output=$(mktemp -d "$REPO_ROOT/build/inventory/run-XXXXXXXX")
# Capture failures explicitly; unavailable services must not look like empty successful queries.
capture() {
    local name=$1 status=0
    shift
    "$@" >"$output/$name.txt" 2>"$output/$name.stderr" || status=$?
    printf '%s\t%s\n' "$name" "$status" >>"$output/status.tsv"
}
capture os-release cat /etc/os-release
capture packages pacman -Q
capture explicit-packages pacman -Qe
capture foreign-packages pacman -Qm
capture system-units systemctl list-unit-files --no-pager --no-legend
capture system-services systemctl list-units --type=service --all --no-pager --no-legend
capture user-units systemctl --user list-unit-files --no-pager --no-legend
capture user-services systemctl --user list-units --type=service --all --no-pager --no-legend
capture zram zramctl --output NAME,ALGORITHM,DISKSIZE
capture firewall systemctl is-active firewalld.service nftables.service ufw.service
for file in /etc/systemd/zram-generator.conf /usr/lib/systemd/zram-generator.conf; do
    if [[ -f "$file" ]]; then
        name=${file//\//_}
        capture "$name" cat "$file"
    fi
done
for file in /etc/systemd/zram-generator.conf.d/*.conf /usr/lib/systemd/zram-generator.conf.d/*.conf; do
    [[ -f "$file" ]] || continue
    name=${file//\//_}
    capture "$name" cat "$file"
done
cat >"$output/README.txt" <<'NOTE'
Read-only inventory; no elevation, network connections, journal or credentials collected.
Package and custom unit names can reveal personal software; review before sharing.
status.tsv records command exit codes. Firewall service activity is not proof of effective firewall rules.
Compare PipeWire/WirePlumber, NetworkManager, BlueZ/Bluedevil, CUPS, SANE/airscan,
IPP-over-USB/discovery, SDDM, microcode, fwupd, power profiles, firewall and zram.
Classify as standard Arch/Plasma, useful Starch default, CachyOS-specific, or personal-only.
This host has not yet been confirmed as the owner's representative daily-use desktop.
No package manifest is approved by this capture.
NOTE
printf 'Inventory saved to %s\n' "$output"
