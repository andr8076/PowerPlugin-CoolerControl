# PowerPlugin for CoolerControl

A CoolerControl plugin for fan curves based on CPU and GPU power usage.

PowerPlugin adds a virtual temperature sensor for each detected power source. Set a maximum wattage, and the sensor reports power usage on a 0–100°C scale. Use it in CoolerControl's Graph Profiles and Mix Profiles.

## Example

Set a GPU's maximum power to **500 W**:

| GPU power | Virtual sensor |
|---:|---:|
| 0 W | 0°C |
| 100 W | 20°C |
| 250 W | 50°C |
| 375 W | 75°C |
| 500 W+ | 100°C |

The conversion is `min(100, current watts / maximum watts × 100)`. Fan speed follows the curve you configure in CoolerControl.

## Installation

**Requirements:** Linux, CoolerControl 5.1+, Python 3.11+, Python venv/pip, sudo, and systemd. The installer downloads Python dependencies from PyPI.

```bash
git clone https://github.com/andr8076/PowerPlugin-CoolerControl.git
cd PowerPlugin-CoolerControl
./install.sh
sudo systemctl restart coolercontrold
```

## Configuration

1. Open **CoolerControl → Plugins → Power to Temperature**.
2. Enter the **maximum wattage** for each power source and save.
3. Create a **Graph Profile** and select a sensor from **Power to Temperature**.
4. Assign the profile to the desired fans.

For temperature protection, use a **Maximum Mix Profile** combining the power-based curve with a curve based on real CPU or GPU temperature.

## Supported sensors

PowerPlugin reads the power measurements provided by the Linux kernel:

- **GPU and other hwmon devices:** `power*_average` and `power*_input`.
- **CPU:** package power calculated from RAPL `energy_uj` counters.

Sources are detected when the plugin starts. Restart CoolerControl after adding or removing hardware.

Sensor names and IDs remain stable across ordinary hwmon renumbering. Each power source has its own maximum-wattage setting.

## Sensor behavior

| Condition | Result |
|---|---|
| Normal power reading | Scaled to 0–100°C |
| Power above configured maximum | 100°C |
| Missing or invalid reading | 100°C |
| Maximum wattage not configured | 100°C |
| Initial RAPL sample | 100°C until the next sample |

**Note:** Virtual temperatures represent power usage, not component temperature. Configure the 100°C curve point for adequate cooling and keep a real-temperature profile active.

CPU RAPL access may require root privileges, so the plugin service runs with elevated permissions. Power readings are collected locally.

## Updating

```bash
git pull --ff-only
./install.sh
sudo systemctl restart coolercontrold
```

Existing maximum-wattage settings are preserved during installation.

## Uninstalling

Change any fan profiles using PowerPlugin sensors to another source, then run:

```bash
./uninstall.sh
sudo systemctl restart coolercontrold
```

Back up `/var/lib/coolercontrol/plugins/cc_power_to_temp/config.json` first if you want to keep your settings.

## Troubleshooting

View the service logs:

```bash
sudo journalctl -b -u cc-plugin-cc_power_to_temp -n 80 --no-pager
sudo journalctl -b -u coolercontrold -n 80 --no-pager
```

- **Plugin doesn't appear:** Check that installation succeeded, then restart CoolerControl.
- **Sensor always shows 100°C:** Check its maximum-wattage setting and Linux power reading. An unavailable sensor reports 100°C.
- **CPU power is missing:** Check `/sys/class/powercap/` for available RAPL energy counters.
- **No power sources detected:** Check `sensors` and your kernel's power monitoring support.

## Development

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/generate_proto.py
.venv/bin/python -m unittest discover -s tests -v
```

The plugin uses CoolerControl's device-service gRPC API. Protocol definitions are in `proto/`; Python bindings are generated during installation.

## License

GPL-3.0-or-later. See [LICENSE](LICENSE) and [third-party notices](THIRD_PARTY_NOTICES.md).

Version: **1.0.0-rc.1**.
