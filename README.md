Starch Linux, a personal Linux made to  serve you the endless horizons of Arch/Artix,
without roleplaying as a systems engineer. 

If you'd like to contribute to this project, understand your contribution matters
more than you likely think. I'm currently one dude spending many hours out of my 
day to make this thing happen. I really wish I could understand everything in an entire 
Linux distro, but just as Linus Torvalds stated no single person can understand the whole 
Linux Kernel, the same applies to a whole operating system. I'm not a professional developer
and I'm barely a programmer. This is exactly why this project needs experts. Maybe not a 
Linux Systems Engineer, but rather someone who loves one specific part. If you love
diving into a couple niche parts of Linux, these are the kind of contributors that change
things. A jack of a trades is a master of none, a master of one will get their job done. 
I have done the best I can covering all bases, and I've learned so much from this project. 
However, I do not plan on staying the master of none this project is making me, and so 
I will always appreciate a credible expert.



# Starch Linux

Starch Linux is an x86_64 Linux distribution with a graphical online installer.
One ISO offers three installation profiles:

| Profile | Desktop / login | Kernel / init | Repositories |
| --- | --- | --- | --- |
| KDE Plasma LTS (default) | Plasma Wayland / SDDM | Linux LTS / systemd | Arch |
| COSMIC LTS | COSMIC Wayland / COSMIC Greeter | Linux LTS / systemd | Arch |
| Starch Lite | Xfce X11 / LightDM | Linux Zen / OpenRC | Artix + Arch extra |

Calamares installs fresh packages with pacstrap and erases the selected disk.
All profiles use ext4, Limine (UEFI or BIOS), zram, NetworkManager, PipeWire,
Flatpak, and Linux Update Utility. The Archiso live desktop uses Plasma,
systemd, and the regular Arch kernel.

An optional Additional Software page accepts pacman packages and Flathub app IDs
for installation after the essential OS succeeds, with safe skipping and warnings
for optional failures. Nothing is deferred to first boot.

See [installation profiles](docs/installation-profiles.md),
[supported scope](docs/decisions.md), and [licensing](docs/licensing.md).

Source: `archiso/profile/` holds the live image; `calamares/` the installer;
`manifests/` the base package list; `scripts/installer/` profile configuration;
`packages/` integrations; and `tests/` automated checks.
