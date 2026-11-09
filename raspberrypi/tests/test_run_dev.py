"""Verify that a dashboard alone cannot hide a receiver startup failure."""

import os
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "run_dev.sh"


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="fire-tag-startup-")
        self.root = Path(self.tmp.name)
        shutil.copy2(SCRIPT, self.root / "run_dev.sh")
        (self.root / "config.json").write_text(json.dumps({
            "auto_calibrate": False, "calibration_mode": "anchor_ranges",
            "anchors": {"1": {"x": 7.0, "y": 0.0}}, "serial_port": "A0_USB3",
        }))
        # Real child processes isolate the shell launcher from USB hardware.
        for role in ("receiver", "web", "web_lite"):
            (self.root / f"fire_tag_{role}.py").write_text(
                "import os, sys, time\n"
                f"if os.environ.get('FAIL_ROLE') == '{role}':\n"
                f"    print('{role} startup failed', flush=True)\n"
                "    sys.exit(1)\n"
                "time.sleep(60)\n"
            )

    def tearDown(self):
        subprocess.run(["bash", str(self.root / "run_dev.sh"), "stop"],
                       capture_output=True, timeout=5)
        self.tmp.cleanup()

    def start(self, fail_role=""):
        return subprocess.run(
            ["bash", str(self.root / "run_dev.sh"), "start"],
            env={**os.environ, "FAIL_ROLE": fail_role},
            capture_output=True, text=True, timeout=10,
        )

    def test_receiver_failure_is_reported_even_when_web_runs(self):
        result = self.start("receiver")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receiver startup failed", result.stderr)
        self.assertNotIn("Dashboard:", result.stdout)

    def test_web_failure_is_reported_even_when_receiver_runs(self):
        result = self.start("web")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("web startup failed", result.stderr)
        self.assertNotIn("Dashboard:", result.stdout)

    def test_lite_failure_is_reported_even_when_full_web_runs(self):
        result = self.start("web_lite")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("web_lite startup failed", result.stderr)
        self.assertNotIn("Dashboard:", result.stdout)

    def test_success_requires_all_three_processes(self):
        result = self.start()
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_each_start_rechecks_anchor_positions_without_erasing_config(self):
        result = self.start()
        self.assertEqual(result.returncode, 0, result.stderr)
        config = json.loads((self.root / "config.json").read_text())
        self.assertTrue(config["auto_calibrate"])
        self.assertEqual(config["anchors"]["1"], {"x": 7.0, "y": 0.0})
        self.assertEqual(config["serial_port"], "A0_USB3")


if __name__ == "__main__":
    unittest.main()
