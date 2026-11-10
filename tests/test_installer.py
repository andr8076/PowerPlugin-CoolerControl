"""Isolated installer tests; no root access or CoolerControl changes."""
from pathlib import Path
from tempfile import TemporaryDirectory
import os
import shutil
import subprocess
import unittest


REPO = Path(__file__).resolve().parents[1]


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        root = Path(self.tempdir.name)
        self.base = root / "plugins"
        self.base.mkdir()
        self.source = root / "source"
        self.source.mkdir()
        for relative in [
            "install.sh", "service.py", "power_sensor.py", "manifest.toml",
            "start.sh", "requirements.txt", "ui/index.html",
            "scripts/generate_proto.py",
        ]:
            target = self.source / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(REPO / relative, target)
        (self.source / "proto").mkdir()

        installer = self.source / "install.sh"
        body = installer.read_text().replace(
            'BASE="/var/lib/coolercontrol/plugins"',
            'BASE="$POWERPLUGIN_TEST_BASE"',
        )
        installer.write_text(body)

        fakebin = root / "bin"
        fakebin.mkdir()
        sudo = fakebin / "sudo"
        sudo.write_text("""#!/usr/bin/env bash
set -e
if [[ "$1" == "-v" ]]; then exit 0; fi
if [[ "$1" == "python3" && "$2" == "-m" && "$3" == "venv" ]]; then
    mkdir -p "$4/bin"
    printf '#!/bin/sh\\nexit 0\\n' > "$4/bin/python"
    chmod 755 "$4/bin/python"
    exit 0
fi
if [[ "$1" == */.venv/bin/python ]]; then exit 0; fi
if [[ "$1" == "mv" && "$2" == "--" &&
      "$3" == */.cc_power_to_temp.stage.* &&
      "$4" == "$POWERPLUGIN_TEST_BASE/cc_power_to_temp" &&
      "$FAKE_FAIL_ACTIVATION" == "1" ]]; then
    echo "Simulated activation failure" >&2
    exit 23
fi
exec "$@"
""")
        sudo.chmod(0o755)
        self.env = os.environ.copy()
        self.env["PATH"] = str(fakebin) + os.pathsep + self.env["PATH"]
        self.env["POWERPLUGIN_TEST_BASE"] = str(self.base)

    def install(self, fail=False):
        env = {**self.env, "FAKE_FAIL_ACTIVATION": "1" if fail else "0"}
        return subprocess.run(
            ["bash", str(self.source / "install.sh")],
            cwd=self.source, env=env, capture_output=True, text=True,
            timeout=15, check=False,
        )

    def previous(self):
        dest = self.base / "cc_power_to_temp"
        dest.mkdir()
        (dest / "manifest.toml").write_text('id = "cc_power_to_temp"\nversion = "old"\n')
        (dest / "config.json").write_text('{"max_watts":{"gpu":500}}')
        (dest / "old_file.txt").write_text("obsolete")
        return dest

    def assert_no_temporary_installations(self):
        self.assertFalse(list(self.base.glob(".cc_power_to_temp.stage.*")))
        self.assertFalse(list(self.base.glob(".cc_power_to_temp.backup.*")))

    def test_clean_first_install(self):
        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        dest = self.base / "cc_power_to_temp"
        self.assertTrue((dest / "service.py").exists())
        self.assertTrue((dest / "manifest.toml").exists())
        self.assert_no_temporary_installations()

    def test_upgrade_cleans_old_version_and_preserves_settings(self):
        dest = self.previous()
        legacy = self.base / ".cc_power_to_temp.backup.202611100001"
        legacy.mkdir()
        (legacy / "manifest.toml").write_text('id = "cc_power_to_temp"')
        unrelated = self.base / ".cc_power_to_temp.backup.other"
        unrelated.mkdir()
        (unrelated / "manifest.toml").write_text('id = "different_plugin"')

        result = self.install()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((dest / "old_file.txt").exists())
        self.assertEqual((dest / "config.json").read_text(),
                         '{"max_watts":{"gpu":500}}')
        self.assertTrue((dest / "service.py").exists())
        self.assertFalse(legacy.exists())
        self.assertTrue(unrelated.exists())
        self.assertFalse(list(self.base.glob(".cc_power_to_temp.stage.*")))
        self.assertEqual(
            list(self.base.glob(".cc_power_to_temp.backup.*")), [unrelated],
        )

    def test_failed_activation_restores_previous_installation(self):
        dest = self.previous()
        result = self.install(fail=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((dest / "old_file.txt").exists())
        self.assertEqual((dest / "config.json").read_text(),
                         '{"max_watts":{"gpu":500}}')
        self.assert_no_temporary_installations()


if __name__ == "__main__":
    unittest.main()
