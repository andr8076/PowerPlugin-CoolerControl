# Security

If you find a security issue, use GitHub's private vulnerability reporting if enabled; do not publish exploit details before a fix is available.

## Privileges and trust

The plugin reads Linux sensor files. CPU RAPL package energy is commonly root-restricted, so the manifest requests privileged execution. The service only reads sysfs/powercap and its config.json. It never controls fans, changes CoolerControl profiles, writes to sysfs, or sends telemetry.

The gRPC service listens on the local /run/cc-power-to-temp.sock Unix socket and rejects all fan-control methods. It refuses to replace a live socket or a socket belonging to another user. The installer uses sudo and downloads pinned Python dependencies. Inspect the source before installation.

## Cooling safety

Invalid, unreadable or unconfigured sources emit virtual 100°C. Fan duty is still determined by the configured curve. Always provide a second profile using real hardware temperature and a Maximum Mix Profile. Never rely on a virtual wattage sensor as a hardware thermal safeguard.
