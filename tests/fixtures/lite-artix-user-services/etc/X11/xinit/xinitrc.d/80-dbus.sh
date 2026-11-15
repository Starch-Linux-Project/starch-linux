#!/bin/bash

dbus_socket="$XDG_RUNTIME_DIR/bus"
dbuslaunch="$(which dbus-launch 2>/dev/null)"

if [ -n "$DBUS_SESSION_BUS_ADDRESS" ]; then
    # dbus ok
    :
elif [ -S "$dbus_socket" ]; then
    # use dbus instance provided by user service
    export DBUS_SESSION_BUS_ADDRESS="unix:path=${dbus_socket}"
elif [ -n "$dbuslaunch" ] && [ -x "$dbuslaunch" ]; then
    # launch a session dbus instance
    if [ -n "$command" ]; then
        command="$dbuslaunch --exit-with-session $command"
    else
        eval $($dbuslaunch --sh-syntax --exit-with-session)
    fi
fi
