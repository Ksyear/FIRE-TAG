import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fire_tag_receiver import Receiver, Store
from fire_tag_web import Dashboard


class Link:
    def __init__(self):
        self.lines = []

    def write(self, line):
        self.lines.append(line)


class PairReceiverTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(str(Path(self.tmp.name) / "data.db"))
        self.link = Link()
        self.config = {"auto_calibrate": True, "calibration_mode": "anchor_ranges", "tag_z": 1,
                       "anchors": {str(i): {"x": 0, "y": 0, "z": 1} for i in range(3)}}
        self.rx = Receiver(self.config, store=self.store, link=self.link,
                           config_path=str(Path(self.tmp.name) / "config.json"))
        self.silence = contextlib.redirect_stdout(io.StringIO())
        self.silence.__enter__()

    def tearDown(self):
        self.silence.__exit__(None, None, None)
        self.store.close()
        self.tmp.cleanup()

    def test_direct_reports_set_coordinates_then_real_tag_ranges_set_position(self):
        sides = {(0, 1): 3000, (0, 2): 4000, (1, 2): 5000}
        for tick in range(61):
            now = 100 + tick * 0.2
            self.rx.tick(now)
            if not self.rx.auto_cal:
                break
            a, b, seq, _ = self.rx.pair_pending
            self.rx.handle_line(json.dumps({"type": "anchor_range", "anchor": b, "peer": a,
                                           "seq": seq, "range_mm": sides[a, b]}), now + 0.01)
        self.assertFalse(self.rx.auto_cal)
        saved = json.loads((Path(self.tmp.name) / "config.json").read_text())
        self.assertEqual(saved["anchors"]["2"]["y"], 4.0)
        self.assertEqual(saved["calibration"]["source"], "anchor_ranges")
        self.assertEqual(len(self.link.lines), 60)
        for a, r in enumerate((2236, 2828, 2236)):
            self.rx.handle_line(json.dumps({"type": "range", "anchor": a, "tag": 0,
                                           "seq": 7, "range_mm": r}), now + 0.1)
        row = self.store.db.execute("SELECT x,y FROM tag_latest").fetchone()
        self.assertAlmostEqual(row["x"], 1.0, places=3)
        self.assertAlmostEqual(row["y"], 2.0, places=3)

    def test_ack_and_unrequested_range_do_not_count_as_measurements(self):
        self.rx.tick(100)
        a, b, seq, _ = self.rx.pair_pending
        for message in (
            {"type": "ack", "anchor": a, "id": seq, "cmd": "range", "ok": True},
            {"type": "anchor_range", "anchor": b, "peer": a, "seq": seq - 1, "range_mm": 3000},
        ):
            self.rx.handle_line(json.dumps(message), 100.1)
        self.assertEqual(self.rx.pair_cal.counts(), {"01": 0, "02": 0, "12": 0})
        self.rx.tick(100.9)
        self.assertEqual(self.link.lines[-1].split()[3:], ["range", "2"])
        self.assertTrue(self.rx.auto_cal)

    def test_successful_measurement_clears_transient_rejection(self):
        self.rx.tick(100)
        a, b, seq, _ = self.rx.pair_pending
        self.rx.handle_line(json.dumps({"type": "ack", "anchor": a, "id": seq,
                                       "cmd": "range", "ok": False}), 100.01)
        self.assertIn(a, self.rx.pair_rejected)
        self.rx.tick(100.2)
        a, b, seq, _ = self.rx.pair_pending
        self.rx.handle_line(json.dumps({"type": "anchor_range", "anchor": b, "peer": a,
                                       "seq": seq, "range_mm": 4000}), 100.21)
        self.assertNotIn(a, self.rx.pair_rejected)

    def test_dashboard_can_queue_commands_between_serial_messages(self):
        self.rx.auto_cal = False
        for seq, now in ((10, 100), (11, 100.1)):
            self.rx.handle_line(json.dumps({"type": "range", "anchor": 0, "tag": 0,
                                           "seq": seq, "range_mm": 3000}), now)
            self.rx.tick(now)
        cfg = Path(self.tmp.name) / "config.json"
        cfg.write_text(json.dumps(self.config))
        dash = Dashboard(Path(self.tmp.name) / "data.db", cfg)
        self.assertGreater(dash.queue_command({"cmd": "ping", "target": "all"})["id"], 0)


if __name__ == "__main__":
    unittest.main()
