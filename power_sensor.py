"""Read Linux power sensors and map wattage to safe virtual temperatures.

The module never controls fans, writes to sysfs, or connects to a network.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from pathlib import Path
import re
import time

MIN_SAMPLE_SECONDS = 0.15
MAX_SAMPLE_SECONDS = 10.0
MAX_PLAUSIBLE_WATTS = 10_000.0
MAX_CONFIGURED_WATTS = 10_000.0


@dataclass
class Source:
    key: str
    label: str
    path: Path
    kind: str
    range_path: Path | None = None
    previous_energy: int | None = field(default=None, repr=False)
    previous_time: float | None = field(default=None, repr=False)

    @property
    def channel_id(self) -> str:
        """Stable across enumeration order and hwmonN renumbering."""
        return "temp" + hashlib.sha256(self.key.encode("utf-8")).hexdigest()[:12]

    def watts(self, now: float | None = None) -> float | None:
        """Return watts; None indicates missing, invalid, or stale data."""
        try:
            timestamp = time.monotonic() if now is None else now
            raw = int(self.path.read_text(encoding="utf-8").strip())
            if raw < 0:
                return None

            if self.kind == "power_uw":
                power = raw / 1_000_000.0
            elif self.kind == "energy_uj":
                previous_energy = self.previous_energy
                previous_time = self.previous_time
                # Always reset the baseline, including after a long sampling gap.
                self.previous_energy = raw
                self.previous_time = timestamp
                if previous_energy is None or previous_time is None:
                    return None
                elapsed = timestamp - previous_time
                if not MIN_SAMPLE_SECONDS <= elapsed <= MAX_SAMPLE_SECONDS:
                    return None
                energy_delta = raw - previous_energy
                if energy_delta < 0:
                    if self.range_path is None:
                        return None
                    energy_range = int(self.range_path.read_text(encoding="utf-8").strip())
                    if not 0 < energy_range or raw >= energy_range or previous_energy >= energy_range:
                        return None
                    energy_delta += energy_range
                power = energy_delta / elapsed / 1_000_000.0
            else:
                return None

            if not math.isfinite(power) or power > MAX_PLAUSIBLE_WATTS:
                return None
            return max(0.0, power)
        except (OSError, ValueError, OverflowError, ZeroDivisionError):
            return None


def _hwmon_identity(hwmon: Path, chip: str) -> str:
    """Prefer hardware topology path; exclude unstable hwmonN directory."""
    real = hwmon.resolve()
    device = real.parent.parent if real.parent.name == "hwmon" else real
    return f"{device}:{chip}"


def discover(sys_root: Path = Path("/sys")) -> list[Source]:
    """Discover hwmon power (average or input) and CPU-package RAPL energy."""
    sources: list[Source] = []
    for hwmon in sorted((sys_root / "class/hwmon").glob("hwmon*")):
        try:
            chip = (hwmon / "name").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        # Prefer powerN_average over powerN_input when both exist.
        power_files: dict[str, Path] = {}
        for pattern in ("power*_input", "power*_average"):
            for path in sorted(hwmon.glob(pattern)):
                match = re.fullmatch(r"power(\d+)_(?:input|average)", path.name)
                if match:
                    power_files[match.group(1)] = path
        for index, path in sorted(power_files.items(), key=lambda pair: int(pair[0])):
            label_path = hwmon / f"power{index}_label"
            try:
                label = label_path.read_text(encoding="utf-8").strip()
            except OSError:
                label = "Power"
            key = f"hwmon:{_hwmon_identity(hwmon, chip)}:power{index}"
            sources.append(Source(key, f"{chip} {label}", path, "power_uw"))

    powercap = sys_root / "class/powercap"
    for directory in sorted(powercap.glob("*-rapl:*")):
        if not re.fullmatch(r"(?:intel|amd)-rapl:\d+", directory.name):
            continue  # Ignore subordinate domains (DRAM/core) to avoid confusion.
        energy = directory / "energy_uj"
        if not energy.exists():
            continue
        try:
            label = (directory / "name").read_text(encoding="utf-8").strip()
        except OSError:
            continue
        sources.append(Source(
            f"rapl:{directory.name}:{label}",
            f"CPU {label} power", energy, "energy_uj",
            directory / "max_energy_range_uj",
        ))
    return sorted(sources, key=lambda source: source.key)


def read_limits(config_path: Path) -> dict[str, float]:
    """Read configured maximum watts, ignoring invalid settings."""
    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
        raw = config.get("max_watts", {})
        if not isinstance(raw, dict):
            return {}
        limits: dict[str, float] = {}
        for identifier, maximum in raw.items():
            try:
                value = float(maximum)
                if math.isfinite(value) and 1.0 <= value <= MAX_CONFIGURED_WATTS:
                    limits[str(identifier)] = value
            except (ValueError, TypeError):
                pass
        return limits
    except (OSError, ValueError, TypeError, AttributeError):
        return {}


def virtual_temp(watts: float | None, maximum: float | None) -> float:
    """Convert W to 0–100 synthetic °C; never fail down to 0°C."""
    if watts is None or maximum is None:
        return 100.0
    if not all(map(math.isfinite, (watts, maximum))):
        return 100.0
    if watts < 0 or not 1 <= maximum <= MAX_CONFIGURED_WATTS:
        return 100.0
    return min(100.0, max(0.0, (watts / maximum) * 100.0))
