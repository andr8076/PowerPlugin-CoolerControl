# Changelog

## [1.0.0-rc.1] — 2026-11-10

### Added
- Native CoolerControl device-service plugin for Linux power readings.
- Individual maximum-wattage configuration for each source.
- Virtual-temperature IDs stable across Linux hwmon numbering changes.
- CPU RAPL energy-counter and rollover handling.
- Fail-safe 100°C readings for missing sensors/settings, plus warning logs.
- Embedded configuration page, local Unix socket, automated tests and CI.
- Install, upgrade, uninstall and troubleshooting guidance.

### Fixed since the prototype
- gRPC/Protocol Buffers version mismatch.
- Socket security: root-controlled /run instead of a public /tmp path.
- Detection of input and average power files without duplicating channels.
- Installer preserves user maximum-wattage settings on upgrades.
