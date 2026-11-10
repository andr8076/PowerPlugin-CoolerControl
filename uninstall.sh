#!/usr/bin/env bash
# Uninstall PowerPlugin for CoolerControl.
set -euo pipefail
DEST="/var/lib/coolercontrol/plugins/cc_power_to_temp"
if ! sudo test -d "$DEST"; then
    echo "PowerPlugin-CoolerControl is not installed."
    exit 0
fi
echo "Removing PowerPlugin-CoolerControl from $DEST"
echo "If you want to retain maximum wattages, copy $DEST/config.json first."
sudo rm -rf -- "$DEST"
echo "Uninstalled. Restart CoolerControl to unregister it:"
echo "sudo systemctl restart coolercontrold"
