#!/usr/bin/env python3
"""FIRE-TAG web dashboard server (standard library only).

Reads the SQLite file written by fire_tag_receiver.py and serves
  GET  /                         dashboard page (web/index.html, no external files)
  GET  /api/state                latest positions, trail, anchors, events, commands (JSON)
  GET  /api/positions.csv?minutes=60   stored positions as CSV download
  POST /api/command  {"cmd":"ping"|"reboot","target":0|1|2|"all"}  queue an anchor command
  POST /api/alert    {"tag":0,"on":true}                           set the rescue alert
Commands only go into the DB; fire_tag_receiver.py owns the serial port and sends them.

On the Pi hotspot open http://10.42.0.1 (port 80 needs the systemd unit's
CAP_NET_BIND_SERVICE; for a quick test use --port 8000).
"""

import argparse
import csv
import io
import json
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
TRAIL_S = 30          # seconds of path shown behind each tag
TRAIL_GAP_S = 1.0     # longer gaps split the path instead of drawing a jump
EVENT_LIMIT = 30
CSV_MAX_MINUTES = 24 * 60
COMMAND_LIMIT = 5
COMMANDS = ("ping", "reboot")
TARGET_ALL = 255
MAX_TAGS = 8


class ApiError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def trail_segments(points):
    """[(t, x, y), ...] -> [[[x, y], ...], ...] split at time gaps."""
    segments, last_t = [], None
    for p in points:
        if last_t is None or p["t"] - last_t > TRAIL_GAP_S:
            segments.append([])
        segments[-1].append([round(p["x"], 3), round(p["y"], 3)])
        last_t = p["t"]
    return segments


class Dashboard:
    def __init__(self, db_path, config_path):
        self.db_path = Path(db_path)
        self.config_path = Path(config_path)
        self.index_html = (HERE / "web" / "index.html").read_bytes()

    def config(self):
        # Re-read every request so anchor coordinates can be edited live.
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def connect(self):
        if not self.db_path.exists():
            return None
        db = sqlite3.connect(str(self.db_path), timeout=2)
        db.row_factory = sqlite3.Row
        return db

    def state(self):
        cfg = self.config()
        offline_after = cfg.get("anchor_offline_s", 3.0)
        lost_after = cfg.get("tag_lost_s", 2.0)
        # Ages are computed here with the Pi clock, so a wrong phone clock
        # (or a Pi without internet time) cannot mark live data as stale.
        now = time.time()
        anchors_cfg = {int(k): v for k, v in cfg["anchors"].items()}
        status, tags, events, commands, alert_desired = {}, [], [], [], {}
        calibration = None

        db = self.connect()
        if db is not None:
            with db:
                for r in db.execute("SELECT * FROM anchor_status"):
                    status[r["anchor"]] = r
                try:
                    r = db.execute("SELECT * FROM calibration WHERE id=1").fetchone()
                    if r:
                        calibration = {"status": r["status"], "samples": r["samples"], "needed": r["needed"],
                                       "message": r["message"], "age_s": round(now - r["t"], 1)}
                except sqlite3.OperationalError:
                    pass  # receiver from before self-calibration
                for r in db.execute("SELECT tag, alert_on FROM alert_desired"):
                    alert_desired[r["tag"]] = bool(r["alert_on"])
                for r in db.execute("SELECT * FROM commands ORDER BY id DESC LIMIT ?", (COMMAND_LIMIT,)):
                    commands.append({"id": r["id"], "cmd": r["cmd"],
                                     "target": "all" if r["target"] == TARGET_ALL else r["target"],
                                     "status": r["status"], "acks": json.loads(r["acks"]),
                                     "age_s": round(now - r["t"], 1)})
                for r in db.execute("SELECT * FROM tag_latest ORDER BY tag"):
                    points = db.execute(
                        "SELECT t, x, y FROM positions WHERE tag=? AND t>=? ORDER BY t",
                        (r["tag"], r["t"] - TRAIL_S),
                    ).fetchall()
                    age = now - r["t"]
                    tags.append({
                        "id": r["tag"], "x": r["x"], "y": r["y"], "rms": r["rms"], "seq": r["seq"],
                        "age_s": round(age, 1), "lost": age > lost_after,
                        "ranges": json.loads(r["ranges"]),
                        "trail": trail_segments(points),
                        "alert_desired": alert_desired.get(r["tag"], False),
                        "alert_confirmed": bool(r["alert"]),
                    })
                for r in db.execute("SELECT t, kind, message FROM events ORDER BY id DESC LIMIT ?",
                                    (EVENT_LIMIT,)):
                    events.append({"age_s": round(now - r["t"], 1), "kind": r["kind"], "message": r["message"]})
            db.close()

        anchors = []
        for aid, a in sorted(anchors_cfg.items()):
            s = status.get(aid)
            age = now - s["last_seen"] if s else None
            anchors.append({
                "id": aid, "x": a["x"], "y": a["y"],
                "online": age is not None and age <= offline_after,
                "age_s": round(age, 1) if age is not None else None,
                "ok": s["ok"] if s else None, "fail": s["fail"] if s else None,
                "link_rssi": s["link_rssi"] if s else None,
                "alert_mask": s["alert_mask"] if s else None,
            })
        return {"db": db is not None, "anchors": anchors, "tags": tags, "events": events,
                "commands": commands, "room": cfg.get("room"), "calibration": calibration,
                "auto_calibrate": bool(cfg.get("auto_calibrate"))}

    def writable(self):
        db = self.connect()
        if db is None:
            raise ApiError(503, "수신기(fire_tag_receiver.py)가 아직 DB를 만들지 않았습니다")
        return db

    def queue_command(self, body):
        cmd = body.get("cmd")
        target = body.get("target", "all")
        anchors = {int(k) for k in self.config()["anchors"]}
        if cmd not in COMMANDS:
            raise ApiError(400, f"cmd must be one of {COMMANDS}")
        if target == "all":
            target = TARGET_ALL
        elif isinstance(target, bool) or not isinstance(target, int) or target not in anchors:
            raise ApiError(400, f"target must be 'all' or one of {sorted(anchors)}")
        db = self.writable()
        with db:
            cur = db.execute("INSERT INTO commands (t, target, cmd) VALUES (?,?,?)", (time.time(), target, cmd))
        db.close()
        return {"id": cur.lastrowid}

    def set_alert(self, body):
        tag, on = body.get("tag"), body.get("on")
        if isinstance(tag, bool) or not isinstance(tag, int) or not 0 <= tag < MAX_TAGS \
                or not isinstance(on, bool):
            raise ApiError(400, "need {\"tag\": 0-7, \"on\": true|false}")
        db = self.writable()
        with db:
            db.execute("INSERT OR REPLACE INTO alert_desired (tag, alert_on, t) VALUES (?,?,?)",
                       (tag, int(on), time.time()))
            db.execute("INSERT INTO events (t, kind, message) VALUES (?,?,?)",
                       (time.time(), "alert_request", f"요구조자 Tag {tag} 경보 {'켜기' if on else '끄기'} 요청"))
        db.close()
        return {"tag": tag, "on": on}

    def positions_csv(self, minutes):
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(["time_unix", "time_local", "tag", "seq", "x_m", "y_m", "rms_m", "ranges_m"])
        db = self.connect()
        if db is not None:
            since = time.time() - minutes * 60
            for r in db.execute("SELECT * FROM positions WHERE t>=? ORDER BY t", (since,)):
                w.writerow([f"{r['t']:.3f}", time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(r["t"])),
                            r["tag"], r["seq"], f"{r['x']:.3f}", f"{r['y']:.3f}", f"{r['rms']:.3f}", r["ranges"]])
            db.close()
        return out.getvalue().encode("utf-8-sig")  # BOM so Excel opens Korean/UTF-8 correctly


def make_handler(dash):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, ctype, extra=None):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            try:
                if url.path in ("/", "/index.html"):
                    self.send(200, dash.index_html, "text/html; charset=utf-8")
                elif url.path == "/api/state":
                    body = json.dumps(dash.state(), ensure_ascii=False).encode("utf-8")
                    self.send(200, body, "application/json; charset=utf-8")
                elif url.path == "/api/positions.csv":
                    q = parse_qs(url.query)
                    minutes = min(max(int(q.get("minutes", ["60"])[0]), 1), CSV_MAX_MINUTES)
                    name = time.strftime(f"fire_tag_positions_%Y%m%d_%H%M_{minutes}min.csv")
                    self.send(200, dash.positions_csv(minutes), "text/csv; charset=utf-8",
                              {"Content-Disposition": f'attachment; filename="{name}"'})
                else:
                    self.send(404, b"not found", "text/plain")
            except ValueError:
                self.send(400, b"bad query", "text/plain")
            except (sqlite3.Error, OSError) as e:
                self.send(500, f"error: {e}".encode("utf-8"), "text/plain; charset=utf-8")

        def do_POST(self):
            routes = {"/api/command": dash.queue_command, "/api/alert": dash.set_alert}
            handler = routes.get(urlparse(self.path).path)
            try:
                if handler is None:
                    raise ApiError(404, "not found")
                length = int(self.headers.get("Content-Length") or 0)
                if length > 4096:
                    raise ApiError(413, "body too large")
                try:
                    body = json.loads(self.rfile.read(length) or b"{}")
                except ValueError:
                    raise ApiError(400, "body must be JSON")
                if not isinstance(body, dict):
                    raise ApiError(400, "body must be a JSON object")
                result = handler(body)
                self.send(200, json.dumps(result).encode("utf-8"), "application/json; charset=utf-8")
            except ApiError as e:
                msg = json.dumps({"error": str(e)}, ensure_ascii=False).encode("utf-8")
                self.send(e.code, msg, "application/json; charset=utf-8")
            except sqlite3.Error as e:
                msg = json.dumps({"error": f"db: {e}"}, ensure_ascii=False).encode("utf-8")
                self.send(500, msg, "application/json; charset=utf-8")

        def log_message(self, fmt, *args):
            pass  # phones poll twice a second; keep the journal readable

    return Handler


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(HERE / "data" / "fire_tag.db"))
    ap.add_argument("--config", default=str(HERE / "config.json"))
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=80)
    args = ap.parse_args()

    dash = Dashboard(args.db, args.config)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(dash))
    print(f"# FIRE-TAG dashboard on http://{args.host}:{args.port}  (db: {args.db})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
