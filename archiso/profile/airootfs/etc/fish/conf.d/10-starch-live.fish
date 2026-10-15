# Show the banner in interactive live-user terminals, never in scripts or root shells.
if status is-interactive; and test (id -un) = liveuser
    set -g fish_greeting
    if command -q fastfetch
        fastfetch
    end
end
