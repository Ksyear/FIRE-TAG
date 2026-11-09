#!/usr/bin/env python3
"""FIRE-TAG 대시보드 (초기 베타 / 경량판, 표준 라이브러리만 사용).

fire_tag_receiver.py 가 쓰는 SQLite 파일을 읽기만 해서
  GET /            web/index_lite.html
  GET /api/state   앵커 상태, Tag 최신 위치, 최근 이벤트 (JSON)
을 제공합니다. 명령 전송, 경보, CSV, 이동 경로, 캘리브레이션 표시는 없습니다.

Pi 핫스팟에서는 http://10.42.0.1 (포트 80은 systemd 유닛의 CAP_NET_BIND_SERVICE 필요),
간단히 시험할 때는 --port 8000.
"""

import argparse
import json
import sqlite3
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
EVENT_LIMIT = 10


class Dashboard:
    def __init__(self, db_path, config_path):
        self.db_path = Path(db_path)
        self.config_path = Path(config_path)
        self.index_html = (HERE / "web" / "index_lite.html").read_bytes()

    def config(self):
        # 매 요청마다 읽어서 앵커 좌표를 실행 중에도 수정할 수 있게 함
        return json.loads(self.config_path.read_text(encoding="utf-8"))

    def state(self):
        cfg = self.config()
        offline_after = cfg.get("anchor_offline_s", 3.0)
        lost_after = cfg.get("tag_lost_s", 2.0)
        now = time.time()  # 나이(age)는 Pi 시계로 계산 (폰 시계가 틀려도 안전)

        last_seen, tags, events = {}, [], []
        have_db = self.db_path.exists()
        if have_db:
            db = sqlite3.connect(str(self.db_path), timeout=2)
            db.row_factory = sqlite3.Row
            with db:
                for r in db.execute("SELECT anchor, last_seen FROM anchor_status"):
                    last_seen[r["anchor"]] = r["last_seen"]
                for r in db.execute("SELECT tag, x, y, t FROM tag_latest ORDER BY tag"):
                    age = now - r["t"]
                    tags.append({"id": r["tag"], "x": r["x"], "y": r["y"], "lost": age > lost_after})
                for r in db.execute("SELECT t, message FROM events ORDER BY id DESC LIMIT ?", (EVENT_LIMIT,)):
                    events.append({"age_s": round(now - r["t"], 1), "message": r["message"]})
            db.close()

        anchors = []
        for aid, a in sorted((int(k), v) for k, v in cfg["anchors"].items()):
            seen = last_seen.get(aid)
            anchors.append({
                "id": aid, "x": a["x"], "y": a["y"],
                "online": seen is not None and now - seen <= offline_after,
                "never": seen is None,
            })
        return {"db": have_db, "room": cfg.get("room"), "anchors": anchors, "tags": tags, "events": events}


def make_handler(dash):
    class Handler(BaseHTTPRequestHandler):
        def send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            path = self.path.split("?", 1)[0]
            try:
                if path in ("/", "/index.html"):
                    self.send(200, dash.index_html, "text/html; charset=utf-8")
                elif path == "/api/state":
                    body = json.dumps(dash.state(), ensure_ascii=False).encode("utf-8")
                    self.send(200, body, "application/json; charset=utf-8")
                else:
                    self.send(404, b"not found", "text/plain")
            except (sqlite3.Error, OSError, ValueError, KeyError) as e:
                self.send(500, f"error: {e}".encode("utf-8"), "text/plain; charset=utf-8")

        def log_message(self, fmt, *args):
            pass  # 폰이 0.5초마다 요청하므로 로그 생략

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
    print(f"# FIRE-TAG lite dashboard on http://{args.host}:{args.port}  (db: {args.db})", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
