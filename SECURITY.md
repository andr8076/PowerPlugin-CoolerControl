# Security

Report vulnerabilities through GitHub's private vulnerability reporting, if enabled.

## Permissions

The plugin runs as root because CPU RAPL energy counters may require privileged access. It reads Linux power sensors and its local configuration and serves data over the Unix socket at `/run/cc-power-to-temp.sock`.

The installer uses sudo and installs pinned Python dependencies from PyPI.

## Thermal protection

Unconfigured or unavailable power sensors report 100°C. For safe fan control, combine a power curve with a real-temperature curve using a Maximum Mix Profile. Set the top point of each curve to provide adequate cooling.
