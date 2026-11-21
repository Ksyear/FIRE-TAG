import json
import sqlite3
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fire_tag_receiver import Receiver, Store
from fire_tag_web import Dashboard


class DashboardStateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.config = {"auto_calibrate": False, "tag_z": 1,
                       "anchors": {str(i): {"x": i, "y": i % 2, "z": 1} for i in range(3)}}
        self.cfg = self.root / "config.json"
        self.cfg.write_text(json.dumps(self.config))
        self.store = Store(self.root / "data.db")
        self.rx = Receiver(self.config, store=self.store)
        self.dash = Dashboard(self.root / "data.db", self.cfg)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def range(self, anchor, seq=12, mm=2500):
        self.rx.handle_line(json.dumps({"type": "range", "anchor": anchor,
                                      "tag": 0, "seq": seq, "range_mm": mm}), time.monotonic())
        self.store.commit(time.monotonic(), force=True)

    def test_two_current_ranges_are_visible_before_a_position_can_be_solved(self):
        self.range(0)
        self.range(1, mm=3200)
        tags = self.dash.state()["tags"]
        self.assertEqual(len(tags), 1)
        tag = tags[0]
        self.assertIsNone(tag["x"])
        self.assertTrue(tag["lost"])
        self.assertEqual(tag["uwb_ranges"]["1"]["range_m"], 3.2)
        self.assertTrue(tag["uwb_ranges"]["0"]["fresh"])
        self.assertNotIn("2", tag["uwb_ranges"])

    def test_heartbeat_does_not_make_an_old_uwb_range_fresh(self):
        for a in range(3):
            self.range(a)
        self.assertTrue(self.dash.state()["tags"][0].get("uwb_ranges"))
        self.store.db.execute("UPDATE range_latest SET t=? WHERE anchor=2", (time.time() - 20,))
        self.store.anchor_seen(2, {"type": "status", "ok": 100, "fail": 0})
        self.store.commit(time.monotonic(), force=True)
        state = self.dash.state()
        self.assertTrue(state["anchors"][2]["online"])
        self.assertFalse(state["tags"][0]["uwb_ranges"]["2"]["fresh"])
        self.assertTrue(state["tags"][0]["uwb_ranges"]["0"]["fresh"])

    def test_recalibration_hides_coordinates_from_the_previous_triangle(self):
        for a in range(3):
            self.range(a)
        self.config["auto_calibrate"] = True
        self.cfg.write_text(json.dumps(self.config))
        tag = self.dash.state()["tags"][0]
        self.assertIsNone(tag["x"])
        self.assertIsNone(tag["y"])
        self.assertEqual(tag["trail"], [])
        self.assertTrue(tag["lost"])
        self.assertEqual(len(tag["uwb_ranges"]), 3)

    def test_calibration_progress_requires_samples_from_each_pair(self):
        self.store.calibration("collecting", 80, 60, "measuring",
                               {"counts": {"01": 40, "02": 0, "12": 40}})
        self.store.commit(time.monotonic(), force=True)
        cal = self.dash.state()["calibration"]
        self.assertEqual(cal.get("progress_pct"), 67)
        self.assertEqual(cal["pair_counts"], {"01": 40, "02": 0, "12": 40})

    def test_database_from_before_range_cache_is_still_readable(self):
        self.store.position(0, 1, 1, 2, .1, {0: 2, 1: 3, 2: 4}, False)
        self.store.db.execute("DROP TABLE IF EXISTS range_latest")
        self.store.commit(time.monotonic(), force=True)
        tag = self.dash.state()["tags"][0]
        self.assertEqual(tag["x"], 1)
        self.assertEqual(tag.get("uwb_ranges"), {})

    def test_invalid_serial_ranges_cannot_crash_or_create_live_devices(self):
        for changes in ({"range_mm": None}, {"range_mm": "2500"}, {"range_mm": -1},
                        {"tag": True}, {"tag": 8}, {"seq": 65536}, {"anchor": "0"}):
            msg = {"type": "range", "anchor": 0, "tag": 0, "seq": 1, "range_mm": 2500, **changes}
            try:
                self.rx.handle_line(json.dumps(msg), time.monotonic())
            except (KeyError, TypeError, ValueError, sqlite3.Error) as e:
                self.fail(f"Malformed serial input escaped the receiver: {e}")
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM range_latest").fetchone()[0], 0)
        self.assertEqual(self.store.db.execute("SELECT count(*) FROM anchor_status").fetchone()[0], 0)

    def test_a_new_triangle_excludes_all_previous_coordinate_samples(self):
        with patch("time.time", return_value=195):
            self.store.position(0, 1, 8, 9, .1, {0: 2, 1: 3, 2: 4}, False)
        with patch("time.time", return_value=200):
            self.store.calibration("done", 60, 60, "new triangle")
        self.store.commit(time.monotonic(), force=True)
        with patch("time.time", return_value=200.1):
            self.assertIsNone(self.dash.state()["tags"][0]["x"])
        with patch("time.time", return_value=201):
            self.store.position(0, 2, 1, 2, .1, {0: 2, 1: 3, 2: 4}, False)
        self.store.commit(time.monotonic(), force=True)
        with patch("time.time", return_value=201.1):
            self.assertEqual(self.dash.state()["tags"][0]["trail"], [[[1, 2]]])


if __name__ == "__main__":
    unittest.main()
