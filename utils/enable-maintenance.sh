#!/bin/bash

MAINTENANCE_FLAG="/var/www/html/maintenance/ENABLE_MAINTENANCE"

if [ "$1" == "on" ]; then
    sudo touch "$MAINTENANCE_FLAG"
    echo "✅ Maintenance mode ENABLED"
elif [ "$1" == "off" ]; then
    sudo rm -f "$MAINTENANCE_FLAG"
    echo "✅ Maintenance mode DISABLED"
else
    echo "Usage: $0 [on|off]"
    exit 1
fi

sudo nginx -s reload
