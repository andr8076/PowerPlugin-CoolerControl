# Changelog

## 1.0.0-rc.4 — 2026-11-12

- Detect power sources that expose Linux hwmon `energy*_input` counters, including Intel Arc GPUs using the i915 driver.
- Derive power consumption from energy changes over time; prioritize direct wattage channels when available.
- Add hardware discovery, counter reset, and stale-reading regression tests.

## 1.0.0-rc.3 — 2026-11-10

- Replace existing installations cleanly during upgrades.
- Preserve configured wattage limits and restore the previous version if installation fails.
- Remove obsolete plugin backups created by older installers.
- Add first-install, upgrade and rollback tests.

## 1.0.0-rc.2 — 2026-11-10

- Save maximum wattages when a field is committed or the Save button is used.
- Display the saved maximum next to each power source.
- Show unsaved values and failed saves explicitly.
- Include more specific service logs for unavailable power readings or missing settings.
- Add browser-level configuration tests and a live configuration-reload test.

## 1.0.0-rc.1 — 2026-11-10

- Added Linux hwmon and CPU RAPL power monitoring.
- Added configurable wattage limits and virtual temperature sensors.
- Added the CoolerControl plugin settings page.
- Added sensor fail-safe handling and RAPL counter rollover support.
- Added installer, upgrade and uninstall scripts.
- Added automated tests and GitHub Actions.
