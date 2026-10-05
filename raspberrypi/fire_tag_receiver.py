#!/usr/bin/env python3
"""FIRE-TAG Raspberry Pi receiver.

Anchor 0 is plugged into the Pi by USB and prints one JSON object per line:
  {"type":"range","anchor":1,"tag":0,"seq":812,"range_mm":2345,"tag_alert":false,...}
  {"type":"status","anchor":2,"ok":120,"fail":3,"alert_mask":0,...}
  {"type":"ack","anchor":1,"id":17,"cmd":"ping","ok":true,...}
This script groups the ranges of one tag cycle (same tag + seq), converts them
to horizontal distances, solves the tag's 2D position, and stores everything
in SQLite (data/fire_tag.db) for fire_tag_web.py.

It also owns the way back: dashboard commands queued in the DB are written to
Anchor 0 as "CMD <id> <target> <name> <arg>" lines, and the rescue-alert state
requested on the dashboard is kept in sync on every anchor.

  python3 fire_tag_receiver.py                        # auto-detect Anchor 0
  python3 fire_tag_receiver.py --port /dev/ttyUSB0
  python3 fire_tag_receiver.py --record raw.jsonl --csv positions.csv
  python3 fire_tag_receiver.py --replay raw.jsonl     # re-run a recorded session

Live mode uses pyserial if installed, otherwise the standard library (termios).
"""

import argparse
import collections
import csv
import glob
import json
import math
import os
import select
import sqlite3
import sys
import threading
import time
from pathlib import Path

SEQ_MOD = 1 << 16       # cycle sequence is uint16 on the tag
TARGET_ALL = 255        # command target meaning every anchor
CMD_ID_MOD = 0xF000     # dashboard commands use DB id % CMD_ID_MOD; above it = alert sync
CMD_RETRY_S = 1.0       # resend if not every expected anchor answered
CMD_MAX_ATTEMPTS = {"ping": 3, "reboot": 1}  # never repeat a reboot automatically
ALERT_RESYNC_S = 1.5    # min gap between alert re-sends to one anchor
MAX_TAGS = 8            # alert mask has one bit per tag id (firmware MAX_TAGS)

SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
  id INTEGER PRIMARY KEY,
  t REAL NOT NULL,              -- Pi wall clock (unix s)
  tag INTEGER NOT NULL,
  seq INTEGER NOT NULL,
  x REAL NOT NULL,
  y REAL NOT NULL,
  rms REAL NOT NULL,            -- multilateration residual (m)
  ranges TEXT NOT NULL          -- {"anchor": horizontal range m}
);
CREATE INDEX IF NOT EXISTS positions_tag_t ON positions(tag, t);
CREATE TABLE IF NOT EXISTS tag_latest (
  tag INTEGER PRIMARY KEY,
  t REAL, seq INTEGER, x REAL, y REAL, rms REAL, ranges TEXT,
  alert INTEGER                 -- alert state the tag itself reports (FINAL echo)
);
CREATE TABLE IF NOT EXISTS anchor_status (
  anchor INTEGER PRIMARY KEY,
  last_seen REAL,
  ok INTEGER, fail INTEGER, link_rssi INTEGER,
  alert_mask INTEGER            -- alert mask the anchor reports in its heartbeat
);
CREATE TABLE IF NOT EXISTS events (
  id INTEGER PRIMARY KEY,
  t REAL NOT NULL,
  kind TEXT NOT NULL,
  message TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS commands (  -- queued by fire_tag_web.py
  id INTEGER PRIMARY KEY,
  t REAL NOT NULL,
  target INTEGER NOT NULL,                  -- anchor id, 255 = all
  cmd TEXT NOT NULL,                        -- ping | reboot
  status TEXT NOT NULL DEFAULT 'pending',   -- pending | sent | done | failed
  attempts INTEGER NOT NULL DEFAULT 0,
  t_sent REAL,
  acks TEXT NOT NULL DEFAULT '{}'           -- {"anchor": true/false}
);
CREATE INDEX IF NOT EXISTS commands_status ON commands(status);
CREATE TABLE IF NOT EXISTS calibration (  -- anchor self-calibration status (one row)
  id INTEGER PRIMARY KEY CHECK (id = 1),
  t REAL, status TEXT, samples INTEGER, needed INTEGER, message TEXT, result TEXT
);
CREATE TABLE IF NOT EXISTS alert_desired (  -- set by fire_tag_web.py
  tag INTEGER PRIMARY KEY,
  alert_on INTEGER NOT NULL,
  t REAL NOT NULL
);
"""


class Store:
    """SQLite access. WAL mode lets fire_tag_web.py read while we write."""

    COMMIT_INTERVAL_S = 0.5  # batch writes; also limits SD card wear

    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=NORMAL")
        self.db.executescript(SCHEMA)
        self.db.commit()
        self.dirty = False
        self.last_commit = 0.0

    def position(self, tag, seq, x, y, rms, ranges, alert):
        row = (time.time(), tag, seq, x, y, rms, json.dumps({str(a): round(r, 3) for a, r in ranges.items()}))
        self.db.execute("INSERT INTO positions (t, tag, seq, x, y, rms, ranges) VALUES (?,?,?,?,?,?,?)", row)
        self.db.execute("INSERT OR REPLACE INTO tag_latest (t, tag, seq, x, y, rms, ranges, alert) "
                        "VALUES (?,?,?,?,?,?,?,?)", row + (int(alert),))
        self.dirty = True

    def anchor_seen(self, anchor, msg):
        status = msg.get("type") == "status"
        self.db.execute(
            "INSERT INTO anchor_status (anchor, last_seen, ok, fail, link_rssi, alert_mask) VALUES (?,?,?,?,?,?) "
            "ON CONFLICT(anchor) DO UPDATE SET last_seen=excluded.last_seen, "
            "ok=COALESCE(excluded.ok, ok), fail=COALESCE(excluded.fail, fail), "
            "link_rssi=COALESCE(excluded.link_rssi, link_rssi), "
            "alert_mask=COALESCE(excluded.alert_mask, alert_mask)",
            (anchor, time.time(), msg.get("ok") if status else None, msg.get("fail") if status else None,
             msg.get("link_rssi"), msg.get("alert_mask") if status else None),
        )
        self.dirty = True

    def event(self, kind, message):
        self.db.execute("INSERT INTO events (t, kind, message) VALUES (?,?,?)", (time.time(), kind, message))
        self.dirty = True

    # -- commands (rows inserted by the web server) ---------------------------
    def open_commands(self):
        return self.db.execute(
            "SELECT * FROM commands WHERE status IN ('pending','sent') ORDER BY id").fetchall()

    def sent_command(self, wire_id):
        return self.db.execute(
            "SELECT * FROM commands WHERE status='sent' AND id % ? = ? ORDER BY id DESC LIMIT 1",
            (CMD_ID_MOD, wire_id)).fetchone()

    def update_command(self, cmd_id, **fields):
        cols = ", ".join(f"{k}=?" for k in fields)
        self.db.execute(f"UPDATE commands SET {cols} WHERE id=?", (*fields.values(), cmd_id))
        self.dirty = True

    def alert_mask(self):
        mask = 0
        for row in self.db.execute("SELECT tag FROM alert_desired WHERE alert_on=1"):
            if 0 <= row["tag"] < MAX_TAGS:
                mask |= 1 << row["tag"]
        return mask

    def calibration(self, status, samples, needed, message, result=None):
        self.db.execute(
            "INSERT OR REPLACE INTO calibration (id, t, status, samples, needed, message, result) "
            "VALUES (1,?,?,?,?,?,?)",
            (time.time(), status, samples, needed, message, json.dumps(result) if result else None))
        self.dirty = True

    def commit(self, now, force=False):
        if self.dirty and (force or now - self.last_commit >= self.COMMIT_INTERVAL_S):
            self.db.commit()
            self.dirty = False
            self.last_commit = now

    def close(self):
        self.db.commit()
        self.db.close()


# ---------------------------------------------------------------------------
# Geometry
# ---------------------------------------------------------------------------
def horizontal_range(slant_m, anchor, tag_z):
    """Project a 3D range onto the floor plane using known heights."""
    dz = anchor["z"] - tag_z
    return math.sqrt(max(slant_m * slant_m - dz * dz, 0.0))


def solve_position(anchors, ranges):
    """Least-squares 2D multilateration.

    anchors: {id: {"x","y"}}, ranges: {id: horizontal range in m}, >= 3 entries.
    Returns (x, y, rms_residual_m) or None if the anchors are collinear.
    """
    ids = sorted(ranges)
    pts = [(anchors[i]["x"], anchors[i]["y"]) for i in ids]
    rs = [ranges[i] for i in ids]

    # Linearised initial guess: subtract the first circle equation.
    x0, y0 = pts[0]
    r0 = rs[0]
    ata = [[0.0, 0.0], [0.0, 0.0]]
    atb = [0.0, 0.0]
    for (xi, yi), ri in zip(pts[1:], rs[1:]):
        a = (2 * (xi - x0), 2 * (yi - y0))
        b = r0 * r0 - ri * ri + xi * xi - x0 * x0 + yi * yi - y0 * y0
        for m in range(2):
            atb[m] += a[m] * b
            for n in range(2):
                ata[m][n] += a[m] * a[n]
    det = ata[0][0] * ata[1][1] - ata[0][1] * ata[1][0]
    if abs(det) < 1e-9:
        return None
    x = (ata[1][1] * atb[0] - ata[0][1] * atb[1]) / det
    y = (ata[0][0] * atb[1] - ata[1][0] * atb[0]) / det

    # Gauss-Newton refinement on the true (non-linear) range residuals.
    for _ in range(10):
        jtj = [[0.0, 0.0], [0.0, 0.0]]
        jtr = [0.0, 0.0]
        for (xi, yi), ri in zip(pts, rs):
            d = math.hypot(x - xi, y - yi) or 1e-9
            j = ((x - xi) / d, (y - yi) / d)
            res = d - ri
            for m in range(2):
                jtr[m] += j[m] * res
                for n in range(2):
                    jtj[m][n] += j[m] * j[n]
        det = jtj[0][0] * jtj[1][1] - jtj[0][1] * jtj[1][0]
        if abs(det) < 1e-12:
            break
        dx = (jtj[1][1] * jtr[0] - jtj[0][1] * jtr[1]) / det
        dy = (jtj[0][0] * jtr[1] - jtj[1][0] * jtr[0]) / det
        x -= dx
        y -= dy
        if abs(dx) < 1e-4 and abs(dy) < 1e-4:
            break

    rms = math.sqrt(
        sum((math.hypot(x - xi, y - yi) - ri) ** 2 for (xi, yi), ri in zip(pts, rs)) / len(rs)
    )
    return x, y, rms


# ---------------------------------------------------------------------------
# Input sources
# ---------------------------------------------------------------------------
def find_anchor_port():
    """Anchor 0 is an ESP32 DevKitC with a CP2102 USB-UART."""
    candidates = sorted(glob.glob("/dev/serial/by-id/*CP210*"))
    candidates += sorted(glob.glob("/dev/ttyUSB*")) + sorted(glob.glob("/dev/cu.usbserial-*"))
    if not candidates:
        sys.exit("Anchor 0 not found. Plug it in or pass --port.")
    return candidates[0]


class SerialLink:
    """Anchor 0's USB serial: JSON lines in, CMD lines out.

    Uses pyserial when installed; otherwise opens the port with termios from
    the standard library, so the Pi can run without installing packages.
    """

    def __init__(self, port, baud):
        try:
            import serial  # imported here so --replay works without pyserial
        except ImportError:
            serial = None
        if serial:
            self.ser = serial.Serial()
            self.ser.port = port
            self.ser.baudrate = baud
            self.ser.timeout = 0.1
            # Keep DTR/RTS low so opening the port does not reset the ESP32.
            self.ser.dtr = False
            self.ser.rts = False
            self.ser.open()
            self._read = lambda: self.ser.read(512)
            self._write = self.ser.write
            backend = "pyserial"
        else:
            self.fd = self._open_termios(port, baud)
            self._read = self._read_termios
            self._write = lambda data: os.write(self.fd, data)
            backend = "termios"
        print(f"# listening on {port} @ {baud} ({backend})", file=sys.stderr)

    @staticmethod
    def _open_termios(port, baud):
        import fcntl
        import struct
        import termios
        import tty

        fd = os.open(port, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        tty.setraw(fd)
        attrs = termios.tcgetattr(fd)
        attrs[4] = attrs[5] = getattr(termios, f"B{baud}")
        attrs[2] |= termios.CLOCAL | termios.CREAD
        attrs[2] &= ~(termios.HUPCL | getattr(termios, "CRTSCTS", 0))
        termios.tcsetattr(fd, termios.TCSANOW, attrs)
        # Same as pyserial path: DTR/RTS low so the ESP32 keeps running.
        fcntl.ioctl(fd, termios.TIOCMBIC, struct.pack("I", termios.TIOCM_DTR | termios.TIOCM_RTS))
        return fd

    def _read_termios(self):
        if not select.select([self.fd], [], [], 0.1)[0]:
            return b""
        data = os.read(self.fd, 512)
        if not data:  # readable but empty: the device was unplugged
            raise OSError("serial port closed")
        return data

    def lines(self):
        buf = b""
        while True:
            chunk = self._read()
            if not chunk:
                yield None  # idle tick so timeouts and commands still run
                continue
            buf += chunk
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                yield line.decode("utf-8", errors="replace").strip()

    def write(self, line):
        self._write((line + "\n").encode("ascii"))


def file_lines(path):
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield line.strip()


# ---------------------------------------------------------------------------
# Receiver
# ---------------------------------------------------------------------------
class Receiver:
    def __init__(self, config, csv_writer=None, store=None, link=None, live=True, config_path=None):
        self.anchors = {int(k): v for k, v in config["anchors"].items()}
        self.tag_z = config.get("tag_z", 0.0)
        self.group_timeout = config.get("group_timeout_s", 0.3)
        self.offline_after = config.get("anchor_offline_s", 3.0)
        self.tag_lost_after = config.get("tag_lost_s", 2.0)
        self.csv = csv_writer
        self.store = store
        self.link = link
        self.live = live
        self.groups = {}          # (tag, seq) -> {"t", "ranges": {anchor: m}, "slant": {anchor: m}, "alert"}
        # Anchor self-calibration (config "auto_calibrate": true): positions are
        # only shown after the anchor triangle has been measured from Tag ranges.
        self.config = config
        self.config_path = config_path
        self.auto_cal = bool(config.get("auto_calibrate")) and len(self.anchors) == 3
        self.cal_samples = collections.deque(maxlen=2000)
        self.cal_thread = None
        self.cal_result = None
        self.cal_last = 0.0
        self.cal_status = None
        self.anchor_seen = {}     # anchor -> last time any message arrived
        self.anchor_online = {}
        self.tag_seen = {}        # tag -> last time a position was solved
        self.tag_lost = {}
        self.tag_alert = {}       # tag -> alert state the tag reports
        self.alert_reported = {}  # anchor -> alert mask from its last heartbeat
        self.alert_sent_at = {}   # anchor -> time of last alert re-sync
        self.sync_id = 0
        self.last_cmd_check = 0.0

    def event(self, kind, message):
        print(f"[{kind}] {message}")
        if self.store:
            self.store.event(kind, message)

    # -- message handling --------------------------------------------------
    def handle_line(self, line, now):
        if not line or not line.startswith("{"):
            return  # '#' log lines and ESP32 boot noise
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            return
        anchor = msg.get("anchor")
        if anchor is not None:
            self.mark_anchor(int(anchor), msg, now)
        kind = msg.get("type")
        if kind == "range":
            self.add_range(msg, now)
        elif kind == "ack":
            self.handle_ack(msg)

    def mark_anchor(self, anchor, msg, now):
        self.anchor_seen[anchor] = now
        if msg.get("type") == "status" and "alert_mask" in msg:
            self.alert_reported[anchor] = int(msg["alert_mask"])
        if self.store:
            self.store.anchor_seen(anchor, msg)
        if not self.anchor_online.get(anchor):
            self.anchor_online[anchor] = True
            self.event("anchor_online", f"Anchor {anchor} 연결됨")

    def add_range(self, msg, now):
        anchor = int(msg["anchor"])
        if anchor not in self.anchors:
            print(f"[anchor {anchor}] not in config.json, range ignored")
            return
        tag, seq = int(msg["tag"]), int(msg["seq"])
        slant = msg["range_mm"] / 1000.0 - self.anchors[anchor].get("bias_m", 0.0)
        group = self.groups.setdefault((tag, seq), {"t": now, "ranges": {}, "slant": {}, "alert": False})
        group["ranges"][anchor] = horizontal_range(slant, self.anchors[anchor], self.tag_z)
        group["slant"][anchor] = slant
        group["alert"] = group["alert"] or bool(msg.get("tag_alert"))

        # A newer cycle means older ones for this tag will not get more ranges.
        # Allow one cycle of reordering before flushing.
        for key in list(self.groups):
            behind = (seq - key[1]) % SEQ_MOD
            if key[0] == tag and 1 < behind < SEQ_MOD // 2:
                self.flush(key, now)
        if len(group["ranges"]) == len(self.anchors):
            self.flush((tag, seq), now)

    def flush(self, key, now):
        group = self.groups.pop(key, None)
        if group is None:
            return
        tag, seq = key
        ranges = group["ranges"]
        self.note_tag_alert(tag, group["alert"])
        detail = "  ".join(f"A{a} {r:5.2f}" for a, r in sorted(ranges.items()))
        if len(ranges) < 3:
            print(f"tag {tag} seq {seq:5d}  only {len(ranges)} range(s)       [{detail}]")
            return
        if self.auto_cal:
            if len(group["slant"]) == 3:
                self.cal_samples.append(tuple(group["slant"][a] for a in sorted(group["slant"])))
            return  # anchor positions not measured yet; a position would be wrong
        result = solve_position(self.anchors, ranges)
        if result is None:
            print(f"tag {tag} seq {seq:5d}  anchors are collinear, fix config.json")
            return
        x, y, rms = result
        self.tag_seen[tag] = now
        if tag not in self.tag_lost:
            self.tag_lost[tag] = False
            self.event("tag_found", f"요구조자 Tag {tag} 위치 수신 시작")
        elif self.tag_lost[tag]:
            self.tag_lost[tag] = False
            self.event("tag_found", f"요구조자 Tag {tag} 위치 갱신 재개")
        print(f"tag {tag} seq {seq:5d}  x={x:6.2f} y={y:6.2f} m  rms={rms:4.2f}  [{detail}]")
        if self.store:
            self.store.position(tag, seq, x, y, rms, ranges, group["alert"])
        if self.csv:
            row = [f"{time.time():.3f}", tag, seq, f"{x:.3f}", f"{y:.3f}", f"{rms:.3f}"]
            row += [f"{ranges[a]:.3f}" if a in ranges else "" for a in sorted(self.anchors)]
            self.csv.writerow(row)

    def note_tag_alert(self, tag, alert):
        previous = self.tag_alert.get(tag)
        self.tag_alert[tag] = alert
        if alert and not previous:
            self.event("tag_alert_on", f"요구조자 Tag {tag} 경보 수신 확인 (LED 점멸 중)")
        elif previous and not alert:
            self.event("tag_alert_off", f"요구조자 Tag {tag} 경보 해제 확인")

    # -- commands ------------------------------------------------------------
    def expected_acks(self, target):
        return set(self.anchors) if target == TARGET_ALL else {int(target)}

    @staticmethod
    def command_label(row):
        target = "전체 앵커" if row["target"] == TARGET_ALL else f"Anchor {row['target']}"
        name = {"ping": "점검", "reboot": "재시작"}.get(row["cmd"], row["cmd"])
        return f"{target} {name} #{row['id']}"

    def send_command(self, wire_id, target, name, arg=0):
        line = f"CMD {wire_id} {target} {name} {arg}"
        print(f"# -> {line}")
        self.link.write(line)

    def handle_ack(self, msg):
        wire_id = int(msg.get("id", -1))
        if not self.store or not 0 <= wire_id < CMD_ID_MOD:
            return  # alert re-sync ACKs need no bookkeeping; heartbeats confirm them
        row = self.store.sent_command(wire_id)
        if row is None:
            return
        acks = json.loads(row["acks"])
        acks[str(msg["anchor"])] = bool(msg.get("ok"))
        expected = self.expected_acks(row["target"])
        if expected <= {int(a) for a in acks}:
            ok = all(acks[str(a)] for a in expected)
            self.store.update_command(row["id"], status="done" if ok else "failed", acks=json.dumps(acks))
            result = ", ".join(f"A{a} {'성공' if acks[str(a)] else '실패'}" for a in sorted(expected))
            self.event("command_done" if ok else "command_failed", f"{self.command_label(row)}: {result}")
        else:
            self.store.update_command(row["id"], acks=json.dumps(acks))

    def process_commands(self, now):
        wall = time.time()
        for row in self.store.open_commands():
            if row["status"] == "sent" and wall - row["t_sent"] < CMD_RETRY_S:
                continue
            if row["attempts"] >= CMD_MAX_ATTEMPTS.get(row["cmd"], 1):
                acked = {int(a) for a in json.loads(row["acks"])}
                missing = sorted(self.expected_acks(row["target"]) - acked)
                self.store.update_command(row["id"], status="failed")
                self.event("command_failed", f"{self.command_label(row)}: "
                           + ", ".join(f"A{a}" for a in missing) + " 응답 없음")
                continue
            self.send_command(row["id"] % CMD_ID_MOD, row["target"], row["cmd"])
            self.store.update_command(row["id"], status="sent", attempts=row["attempts"] + 1, t_sent=wall)

        # Rescue alert: the dashboard stores the wanted state; make every
        # online anchor match it (also repairs anchors that rebooted).
        desired = self.store.alert_mask()
        for anchor in self.anchors:
            reported = self.alert_reported.get(anchor)
            if reported is None or reported == desired or not self.anchor_online.get(anchor):
                continue
            if now - self.alert_sent_at.get(anchor, -ALERT_RESYNC_S) < ALERT_RESYNC_S:
                continue
            self.sync_id = (self.sync_id + 1) % (SEQ_MOD - CMD_ID_MOD)
            self.send_command(CMD_ID_MOD + self.sync_id, anchor, "alert", desired)
            self.alert_sent_at[anchor] = now

    # -- periodic checks ---------------------------------------------------
    # -- anchor self-calibration ---------------------------------------------
    def calibration_step(self, now):
        import anchor_calibration as ac

        needed = ac.MIN_SAMPLES
        if self.cal_thread and not self.cal_thread.is_alive():
            self.cal_thread = None
            res = self.cal_result
            if res and res["ok"]:
                self.apply_calibration(res)
                return
            reason = ("Tag를 한 줄로만 움직였거나 거의 움직이지 않아 위치가 하나로 정해지지 않습니다. "
                      "앵커 세 개 사이를 넓게 돌아다녀 주세요." if res and not res["unique"]
                      else "측정값이 아직 고르지 않습니다. 계속 움직여 주세요.")
            self.set_cal_status("collecting", reason, res)
        if self.cal_thread is None:
            n = len(self.cal_samples)
            if n < needed:
                self.set_cal_status("collecting", f"샘플 {n}/{needed}: Tag를 앵커 세 개 사이에서 넓게 움직여 주세요.")
            elif now - self.cal_last >= 5:
                self.cal_last = now
                samples = list(self.cal_samples)
                self.cal_thread = threading.Thread(target=lambda: setattr(self, "cal_result", ac.calibrate(samples)),
                                                   daemon=True)
                self.cal_thread.start()

    def set_cal_status(self, status, message, result=None):
        import anchor_calibration as ac

        key = (status, message)
        changed = key != self.cal_status
        # Console: every 25 samples while collecting, otherwise on each new message.
        print_key = (status, len(self.cal_samples) // 25 if status == "collecting" and "샘플" in message else message)
        if print_key != getattr(self, "cal_printed", None):
            self.cal_printed = print_key
            print(f"[calibration] {message}")
        if changed:
            self.cal_status = key
        mono = time.monotonic()
        if self.store and (changed or mono - getattr(self, "cal_written", 0.0) >= 1.0):
            self.cal_written = mono
            self.store.calibration(status, len(self.cal_samples), ac.MIN_SAMPLES, message, result)

    def apply_calibration(self, res):
        for k, p in res["anchors"].items():
            self.anchors[int(k)].update(p)
        self.auto_cal = False
        d = res["distances"]
        msg = (f"앵커 위치 자동 측정 완료: A0–A1 {d['01']:.2f} m, A0–A2 {d['02']:.2f} m, "
               f"A1–A2 {d['12']:.2f} m (잔차 {res['rms_m'] * 100:.0f} cm, 샘플 {res['samples']}개)")
        self.event("calibrated", msg)
        self.set_cal_status("done", msg, res)
        if self.config_path:  # keep the result; the web server redraws the map from config.json
            for k, p in res["anchors"].items():
                self.config["anchors"][str(k)].update(p)
            self.config["auto_calibrate"] = False
            self.config["calibration"] = {**res, "t": time.strftime("%Y-%m-%d %H:%M:%S")}
            Path(self.config_path).write_text(json.dumps(self.config, ensure_ascii=False, indent=2) + "\n",
                                              encoding="utf-8")

    def tick(self, now):
        for key, group in list(self.groups.items()):
            if now - group["t"] > self.group_timeout:
                self.flush(key, now)
        if self.live:
            for anchor, seen in self.anchor_seen.items():
                if self.anchor_online.get(anchor) and now - seen > self.offline_after:
                    self.anchor_online[anchor] = False
                    self.event("anchor_offline", f"Anchor {anchor} 응답 없음 ({now - seen:.1f}초)")
            for tag, seen in self.tag_seen.items():
                if not self.tag_lost.get(tag) and now - seen > self.tag_lost_after:
                    self.tag_lost[tag] = True
                    self.event("tag_lost", f"요구조자 Tag {tag} 위치 갱신 끊김 ({now - seen:.1f}초)")
        if self.link and self.store and now - self.last_cmd_check >= 0.2:
            self.last_cmd_check = now
            self.process_commands(now)
        if self.auto_cal:
            self.calibration_step(now)
        if self.store:
            self.store.commit(now)

    def finish(self, now):
        for key in list(self.groups):
            self.flush(key, now)
        if self.store:
            self.store.commit(now, force=True)


def main():
    here = Path(__file__).resolve().parent
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--port", help="serial port of Anchor 0 (default: auto-detect)")
    ap.add_argument("--baud", type=int, help="override config.json serial_baud (default 115200)")
    ap.add_argument("--config", default=str(here / "config.json"))
    ap.add_argument("--db", help="SQLite file (default: data/fire_tag.db in live mode, none in replay)")
    ap.add_argument("--replay", help="read JSON lines from a file instead of serial")
    ap.add_argument("--record", help="append every raw line received to this file")
    ap.add_argument("--csv", help="append solved positions to this CSV file")
    args = ap.parse_args()

    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    if len(config["anchors"]) < 3:
        sys.exit("config.json needs at least 3 anchors for 2D positioning")

    live = not args.replay
    db_path = args.db or (str(here / "data" / "fire_tag.db") if live else None)
    store = Store(db_path) if db_path else None
    if store:
        print(f"# storing to {db_path}", file=sys.stderr)

    csv_file = csv_writer = None
    if args.csv:
        new = not Path(args.csv).exists()
        csv_file = open(args.csv, "a", newline="", encoding="utf-8")
        csv_writer = csv.writer(csv_file)
        if new:
            anchor_cols = [f"range_a{a}_m" for a in sorted(int(k) for k in config["anchors"])]
            csv_writer.writerow(["time", "tag", "seq", "x_m", "y_m", "rms_m"] + anchor_cols)
    record = open(args.record, "a", encoding="utf-8") if args.record else None

    baud = args.baud or config.get("serial_baud", 115200)  # must match firmware SERIAL_BAUD
    link = SerialLink(args.port or find_anchor_port(), baud) if live else None
    lines = link.lines() if link else file_lines(args.replay)
    rx = Receiver(config, csv_writer, store, link, live=live, config_path=args.config)
    try:
        for line in lines:
            now = time.monotonic()
            if line is not None:
                if record and line:
                    record.write(line + "\n")
                    record.flush()
                rx.handle_line(line, now)
            rx.tick(now)
    except KeyboardInterrupt:
        pass
    finally:
        rx.finish(time.monotonic())
        if store:
            store.close()
        if csv_file:
            csv_file.close()
        if record:
            record.close()


if __name__ == "__main__":
    main()
