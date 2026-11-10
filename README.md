# PowerPlugin for CoolerControl

**Power-aware fan curves without modifying CoolerControl.**

PowerPlugin exposes CPU/GPU power consumption as **virtual temperature sensors** that you can use in existing [CoolerControl](https://coolercontrol.org/) Graph Profiles. Select a sensor and set the wattage that should correspond to **100°C (100% of the scale)**.

> **Independent community plugin:** Not developed, reviewed, or endorsed by the CoolerControl maintainers.
>
> **Release status:** v1.0.0-rc.1. Hardware tested with an AMD Ryzen 7 5700X3D and Radeon RX 7800 XT running Arch Linux. In-app integration testing is still required for the final stable v1.0.0 release.

## Example

| Device power | Virtual temperature (500 W maximum) |
|---:|---:|
| 0 W | 0°C |
| 100 W | 20°C |
| 250 W | 50°C |
| 375 W | 75°C |
| 500 W or more | 100°C |

**Formula:** virtual °C = min(100, 100 × current W ÷ maximum W).

These are *not actual temperatures*. CoolerControl chooses the actual fan speed using the curve you create. This plugin does **not** create a physical fan or write to a fan controller.

## Features

- Native **CoolerControl device-service plugin** using its documented gRPC interface and embedded configuration page.
- Automatically finds Linux hwmon power-average or power-input channels, and CPU-package RAPL counters.
- Individual **maximum wattage** setting for every sensor.
- Stable sensor IDs even if Linux renumbers hwmon devices after reboot.
- Live virtual readings on the plugin page.
- **Fail-safe 100°C** on unreadable sensors, invalid configuration, or missing maximum wattages.
- CPU energy rollover handling and stale-sampling detection.
- No modifications to CoolerControl, no runtime network access, and no writes to hardware.
- All existing CoolerControl Graph, Mix and response-function features remain available.

## Installation (Linux)

Requirements: **CoolerControl 5.1+**, Python 3.11+, a Python venv/ensurepip-capable installation, pip, sudo, systemd and internet access for downloading pinned Python dependencies during installation.

~~~bash
git clone https://github.com/andr8076/PowerPlugin-CoolerControl.git
cd PowerPlugin-CoolerControl
./install.sh
~~~

The installer installs only to /var/lib/coolercontrol/plugins/cc_power_to_temp, preserves your existing maximum-wattage settings on upgrades and makes a backup of the old installation. **It does not change fan profiles or restart CoolerControl.**

Restart CoolerControl to discover the newly installed plugin:

~~~bash
sudo systemctl restart coolercontrold
~~~

Then open **CoolerControl → Plugins → Power to Temperature**, set the maximum wattage of each sensor and click **Save settings**.

**Create a fan curve:** Select a sensor from the **Power to Temperature** virtual device as a normal Graph Profile input. Example: 500 W max, 250 W current → virtual 50°C. The actual fan duty depends on the fan curve.

**Important:** Create another Graph Profile based on *actual CPU/GPU temperatures* and combine it with the power profile using a **Maximum Mix Profile**. This is essential to avoid undercooling during low-power thermal soak or sensor faults.

## Safety and limitations

**This plugin does not replace thermal protection.** Power and actual temperature are different metrics. Components can remain hot even after power drops. A virtual reading of 100°C does **not** itself force 100% fan speed: the curve's top point must provide adequate cooling.

- Missing wattage, unreadable sensor, invalid or missing configuration → virtual **100°C**, never a misleading 0°C.
- CPU RAPL gives CPU *package power* based on energy differences; GPU PPT typically measures chip/package power, **not wall-plug consumption**.
- Only power metrics exposed by the Linux kernel are supported; the plugin does not estimate wattage from utilization.
- Sources are discovered at startup; restart CoolerControl after adding/removing hardware.
- The virtual sensor axis remains labeled °C in CoolerControl. Changing the native curve editor to watts is outside plugin scope.
- CPU RAPL is frequently accessible only to root; the manifest requests **privileged execution**. The running plugin only reads sysfs/powercap and its own configuration, then publishes gRPC sensors over a local Unix socket.
- SELinux systems may require the plugin executable to have an appropriate SELinux type; see the [CoolerControl plugin docs](https://docs.coolercontrol.org/plugins/plugins/).
- The initial release targets Linux. Windows, macOS, and proprietary external meters are not supported.

## Troubleshooting

View logs:

~~~bash
sudo journalctl -b -u cc-plugin-cc_power_to_temp --no-pager -n 80
sudo journalctl -b -u coolercontrold --no-pager -n 80
~~~

**Plugin missing:** confirm that the install finished, then restart coolercontrold. Confirm that /var/lib/coolercontrol/plugins/cc_power_to_temp/manifest.toml exists.

**Virtual temperature stays at 100°C:** this is a deliberate safety signal. Set a valid maximum wattage, then ensure the kernel sensor can be read. The first CPU RAPL sample after startup also reports 100°C briefly while the power rate is calculated.

**No CPU source:** check /sys/class/powercap/ and kernel RAPL support. CPU package measurements vary by processor/kernel.

**No sources:** run the Linux sensors command and look for PPT, power-average or power-input readings.

## Update / uninstall

~~~bash
git pull --ff-only
./install.sh
sudo systemctl restart coolercontrold
~~~

To remove it, run **./uninstall.sh** and restart CoolerControl. Back up the plugin's config.json first if you want to preserve your wattage settings. Before removal, change existing profiles referencing the virtual sensors to use valid sources, to avoid unexpected fan behavior.

## Development

~~~bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/generate_proto.py
.venv/bin/python -m unittest discover -s tests -v
~~~

The generated protocol bindings are built from bundled .proto files and intentionally not checked in. GitHub Actions tests supported Python versions and the gRPC service. The code is intentionally small: sensor discovery, protocol service, one configuration page and installation scripts.

## License and attribution

**GPL-3.0-or-later.** See [LICENSE](LICENSE). Protocol definitions are from [CoolerControl cc-plugins](https://gitlab.com/coolercontrol/cc-plugins), under GPLv3; see [THIRD_PARTY_NOTICES](THIRD_PARTY_NOTICES.md). Not affiliated with or endorsed by the CoolerControl project.
