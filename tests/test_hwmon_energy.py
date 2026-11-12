"""Tests for power measurements derived from Linux hwmon energy counters."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from power_sensor import Source, discover, virtual_temp


class HwmonEnergyTests(unittest.TestCase):
    def make_chip(self, directory: Path, chip: str = "i915") -> Path:
        root = directory / "class" / "hwmon" / "hwmon5"
        root.mkdir(parents=True)
        (root / "name").write_text(chip)
        return root

    def test_intel_gpu_energy_is_discovered_and_measured(self):
        with TemporaryDirectory() as temp:
            hwmon = self.make_chip(Path(temp))
            energy = hwmon / "energy1_input"
            energy.write_text("18000000000")
            # power1_max is a limit, not a measurement.
            (hwmon / "power1_max").write_text("190000000")
            sources = discover(Path(temp))
            self.assertEqual(len(sources), 1)
            arc = sources[0]
            self.assertIn("Intel GPU", arc.label)
            self.assertEqual(arc.kind, "energy_uj")
            self.assertEqual(arc.path, energy)
            self.assertIsNone(arc.watts(now=10.0))  # initial baseline
            energy.write_text("18036000000")
            self.assertAlmostEqual(arc.watts(now=11.0), 36.0)
            self.assertAlmostEqual(virtual_temp(36, 180), 20.0)

    def test_direct_power_preferred_to_energy_same_channel(self):
        with TemporaryDirectory() as temp:
            hwmon = self.make_chip(Path(temp))
            (hwmon / "energy1_input").write_text("1000000")
            (hwmon / "power1_input").write_text("49000000")
            (hwmon / "power1_average").write_text("44000000")
            found = discover(Path(temp))
            self.assertEqual(len(found), 1)
            self.assertEqual(found[0].kind, "power_uw")
            self.assertEqual(found[0].watts(), 44.0)

    def test_independent_energy_and_direct_power_channels(self):
        with TemporaryDirectory() as temp:
            hwmon = self.make_chip(Path(temp), "example")
            (hwmon / "power1_average").write_text("10000000")
            (hwmon / "energy2_input").write_text("1000000")
            (hwmon / "energy2_label").write_text("secondary")
            found = discover(Path(temp))
            self.assertEqual(len(found), 2)
            self.assertEqual({s.kind for s in found}, {"power_uw", "energy_uj"})
            energy = next(s for s in found if s.kind == "energy_uj")
            self.assertEqual(energy.label, "example secondary")

    def test_energy_counter_reset_returns_fail_safe_then_recovers(self):
        with TemporaryDirectory() as temp:
            hwmon = self.make_chip(Path(temp))
            path = hwmon / "energy1_input"
            path.write_text("100000000")
            source = discover(Path(temp))[0]
            self.assertIsNone(source.watts(now=1.0))
            path.write_text("120000000")
            self.assertEqual(source.watts(now=2.0), 20)
            path.write_text("5000000")  # counter reset, not negative power
            self.assertIsNone(source.watts(now=3.0))
            path.write_text("35000000")
            self.assertEqual(source.watts(now=4.0), 30)

    def test_energy_counter_staleness_returns_fail_safe(self):
        with TemporaryDirectory() as temp:
            hwmon = self.make_chip(Path(temp))
            path = hwmon / "energy1_input"
            path.write_text("100000000")
            source = discover(Path(temp))[0]
            self.assertIsNone(source.watts(now=1))
            path.write_text("120000000")
            self.assertIsNone(source.watts(now=15))  # too much time since last poll
            path.write_text("140000000")
            self.assertEqual(source.watts(now=16), 20)


if __name__ == "__main__":
    unittest.main()
