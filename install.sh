#!/usr/bin/env bash
# Install or upgrade without touching CoolerControl's own profiles/configuration.
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
echo "This will not modify fan profiles or restart the daemon."
sudo -v
sudo install -d -m 0755 "$BASE"
STAGE="$(sudo mktemp -d "$BASE/.cc_power_to_temp.stage.XXXXXXXX")"
on_exit() { [[ -z "${STAGE:-}" ]] || sudo rm -rf -- "$STAGE"; }
trap on_exit EXIT

sudo install -d -m 0755 "$STAGE/ui" "$STAGE/scripts"
for file in service.py power_sensor.py manifest.toml start.sh requirements.txt; do
    sudo install -m 0644 "$SOURCE/$file" "$STAGE/$file"
done
sudo chmod 0755 "$STAGE/start.sh"
sudo install -m 0644 "$SOURCE/ui/index.html" "$STAGE/ui/index.html"
sudo install -m 0644 "$SOURCE/scripts/generate_proto.py" "$STAGE/scripts/generate_proto.py"
sudo cp -a "$SOURCE/proto" "$STAGE/proto"

echo "Installing pinned Python dependencies and generating gRPC bindings…"
sudo python3 -m venv "$STAGE/.venv"
sudo "$STAGE/.venv/bin/python" -m pip install --disable-pip-version-check -r "$STAGE/requirements.txt"
sudo "$STAGE/.venv/bin/python" "$STAGE/scripts/generate_proto.py"
sudo "$STAGE/.venv/bin/python" -m compileall -q "$STAGE/service.py" "$STAGE/power_sensor.py" "$STAGE/generated"

if sudo test -f "$DEST/config.json"; then
    echo "Preserving your existing maximum-wattage settings"
    sudo cp -p "$DEST/config.json" "$STAGE/config.json"
fi

BACKUP=""
if sudo test -e "$DEST"; then
    BACKUP="$BASE/.cc_power_to_temp.backup.$(date -u +%Y%m%d%H%M%S)"
    echo "Keeping previous installation at $BACKUP"
    sudo mv -- "$DEST" "$BACKUP"
fi

if ! sudo mv -- "$STAGE" "$DEST"; then
    echo "Install failed; restoring previous installation…" >&2
    if [[ -n "$BACKUP" ]]; then sudo mv -- "$BACKUP" "$DEST"; fi
    exit 1
fi
STAGE=""
echo
echo "Installed successfully."
echo "Restart CoolerControl when convenient: sudo systemctl restart coolercontrold"
echo "Then configure maximum wattages in CoolerControl → Plugins → Power to Temperature."
echo "Your existing fan profiles are unchanged."
