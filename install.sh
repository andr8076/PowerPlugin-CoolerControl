#!/usr/bin/env bash
# Install or upgrade PowerPlugin for CoolerControl.
set -euo pipefail

SOURCE="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
BASE="/var/lib/coolercontrol/plugins"
DEST="$BASE/cc_power_to_temp"

for tool in sudo python3; do
    command -v "$tool" >/dev/null || { echo "Missing required command: $tool" >&2; exit 1; }
done
[[ -f "$SOURCE/manifest.toml" && -d "$SOURCE/proto" ]] ||
    { echo "Run this script from a complete repository checkout." >&2; exit 1; }

echo "PowerPlugin-CoolerControl: install/upgrade"
echo "Plugin files: $DEST"
sudo -v
sudo install -d -m 0755 "$BASE"

# Stage the complete new version before replacing the installed one.
STAGE="$(sudo mktemp -d "$BASE/.cc_power_to_temp.stage.XXXXXXXX")"
BACKUP=""
on_exit() {
    local result=$?
    trap - EXIT
    if [[ $result -ne 0 && -n "$BACKUP" ]] && sudo test -d "$BACKUP/previous"; then
        if ! sudo test -e "$DEST"; then
            echo "Restoring previous PowerPlugin installation..." >&2
            sudo mv -- "$BACKUP/previous" "$DEST" || true
        fi
    fi
    if [[ -n "$STAGE" ]] && sudo test -d "$STAGE"; then
        sudo rm -r -- "$STAGE" || true
    fi
    if [[ -n "$BACKUP" ]] && sudo test -d "$BACKUP"; then
        sudo rmdir -- "$BACKUP" 2>/dev/null || true
    fi
}
trap on_exit EXIT

sudo install -d -m 0755 "$STAGE/ui" "$STAGE/scripts"
for file in service.py power_sensor.py manifest.toml start.sh requirements.txt; do
    sudo install -m 0644 "$SOURCE/$file" "$STAGE/$file"
done
sudo chmod 0755 "$STAGE/start.sh"
sudo install -m 0644 "$SOURCE/ui/index.html" "$STAGE/ui/index.html"
sudo install -m 0644 "$SOURCE/scripts/generate_proto.py" "$STAGE/scripts/generate_proto.py"
sudo cp -a "$SOURCE/proto" "$STAGE/proto"

echo "Installing Python dependencies and generating gRPC bindings..."
sudo python3 -m venv "$STAGE/.venv"
sudo "$STAGE/.venv/bin/python" -m pip install --disable-pip-version-check -r "$STAGE/requirements.txt"
sudo "$STAGE/.venv/bin/python" "$STAGE/scripts/generate_proto.py"
sudo "$STAGE/.venv/bin/python" -m compileall -q "$STAGE/service.py" "$STAGE/power_sensor.py" "$STAGE/generated"

if sudo test -f "$DEST/config.json"; then
    echo "Keeping saved maximum-wattage settings"
    sudo cp -p "$DEST/config.json" "$STAGE/config.json"
fi

# Move the previous installation out of the active plugin path.
# Keep it only until the new version has been activated successfully.
if sudo test -e "$DEST"; then
    BACKUP="$(sudo mktemp -d "$BASE/.cc_power_to_temp.backup.XXXXXXXX")"
    echo "Removing previous PowerPlugin version..."
    sudo mv -- "$DEST" "$BACKUP/previous"
fi

sudo mv -- "$STAGE" "$DEST"
STAGE=""

if [[ -n "$BACKUP" ]]; then
    sudo rm -r -- "$BACKUP"
    BACKUP=""
fi

# Clean up any backup folders left by older installers.
# A matching manifest is required before deleting a legacy backup.
while IFS= read -r -d '' old_backup; do
    if sudo test -f "$old_backup/manifest.toml" &&
       sudo grep -Eq '^id[[:space:]]*=[[:space:]]*"cc_power_to_temp"' "$old_backup/manifest.toml"; then
        echo "Removing old backup: ${old_backup##*/}"
        sudo rm -r -- "$old_backup"
    fi
done < <(sudo find "$BASE" -maxdepth 1 -mindepth 1 -type d -name '.cc_power_to_temp.backup.*' -print0)

echo
echo "PowerPlugin installed successfully."
echo "Restart CoolerControl: sudo systemctl restart coolercontrold"
echo "Configure wattage limits under CoolerControl → Plugins → Power to Temperature."
