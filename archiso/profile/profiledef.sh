#!/usr/bin/env bash
# shellcheck disable=SC2034

iso_name="starch-linux"
iso_label="STARCH_$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y%m)"
iso_publisher="Starch Linux"
iso_application="Starch Linux Development Installer"
iso_version="$(date --date="@${SOURCE_DATE_EPOCH:-$(date +%s)}" +%Y.%m.%d)"
install_dir="arch"
buildmodes=('iso')
bootmodes=('bios.syslinux'
           'uefi.systemd-boot')
pacman_conf="pacman.conf"
airootfs_image_type="squashfs"
airootfs_image_tool_options=('-comp' 'xz' '-Xbcj' 'x86,arm64' '-b' '1M' '-Xdict-size' '1M')
bootstrap_tarball_compression=('zstd' '-c' '-T0' '--auto-threads=logical' '--long' '-19')
file_permissions=(
  ["/usr/local/bin/starch-install"]="0:0:755"
  ["/usr/local/bin/linux-update-utility.AppImage"]="0:0:755"
  ["/usr/share/starch-installer/target-overlay/usr/local/bin/linux-update-utility.AppImage"]="0:0:755"
  ["/usr/share/icons/hicolor/scalable/apps/linux-update-utility.svg"]="0:0:644"
  ["/usr/share/applications/linux-update-utility.desktop"]="0:0:644"
  ["/etc/sudoers.d/10-starch-live"]="0:0:440"
  ["/usr/local/lib/starch/setup-live-user"]="0:0:755"
  ["/etc/shadow"]="0:0:400"
  ["/root"]="0:0:750"
  ["/root/.automated_script.sh"]="0:0:755"
  ["/root/.gnupg"]="0:0:700"
  ["/usr/local/bin/choose-mirror"]="0:0:755"
  ["/usr/local/bin/Installation_guide"]="0:0:755"
  ["/usr/local/bin/livecd-sound"]="0:0:755"
)
