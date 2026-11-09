#!/usr/bin/env bash
# Start the receiver and the dashboard for testing, without sudo or systemd.
#   ./run_dev.sh            start (ZIP lite on 8080, original on 8081)
#   ./run_dev.sh stop       stop receiver and both dashboards
#   ./run_dev.sh status     show all processes and last log lines
# For the always-on setup use setup_pi.sh (systemd, port 80) instead.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8080}"
mkdir -p "$DIR/data"

stop() {
  pkill -f "$DIR/fire_tag_receiver.py" 2>/dev/null || true
  pkill -f "$DIR/fire_tag_web(_lite)?.py" 2>/dev/null || true
}

case "${1:-start}" in
  stop)
    stop
    echo "stopped"
    ;;
  status)
    pgrep -fl "$DIR/fire_tag_(receiver|web|web_lite).py" || echo "not running"
    tail -n 5 "$DIR/data/receiver.log" "$DIR/data/web_lite.log" "$DIR/data/web.log" 2>/dev/null || true
    ;;
  start)
    stop
    python3 - "$DIR/config.json" <<'PY'
import json
from pathlib import Path
import sys
p = Path(sys.argv[1])
config = json.loads(p.read_text(encoding="utf-8"))
config.update(auto_calibrate=True, calibration_mode="anchor_ranges")
p.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PY
    nohup python3 -u "$DIR/fire_tag_receiver.py" --db "$DIR/data/fire_tag.db" --record "$DIR/data/raw.jsonl" \
      > "$DIR/data/receiver.log" 2>&1 &
    receiver_pid=$!
    nohup python3 -u "$DIR/fire_tag_web_lite.py" --db "$DIR/data/fire_tag.db" --port "$PORT" > "$DIR/data/web_lite.log" 2>&1 &
    lite_pid=$!
    nohup python3 -u "$DIR/fire_tag_web.py" --db "$DIR/data/fire_tag.db" --port "$((PORT + 1))" > "$DIR/data/web.log" 2>&1 &
    web_pid=$!
    sleep 2
    if ! kill -0 "$receiver_pid" 2>/dev/null || ! kill -0 "$lite_pid" 2>/dev/null || ! kill -0 "$web_pid" 2>/dev/null; then
      echo "receiver or dashboard failed to start:" >&2
      tail -n 15 "$DIR/data/receiver.log" "$DIR/data/web_lite.log" "$DIR/data/web.log" >&2
      stop
      exit 1
    fi
    pgrep -fl "$DIR/fire_tag_(receiver|web|web_lite).py"
    for ip in $(hostname -I 2>/dev/null || ipconfig getifaddr en0); do
      echo "Dashboard: http://$ip:$PORT"
      echo "Original:  http://$ip:$((PORT + 1))"
    done
    ;;
  *)
    sed -n '2,6p' "$0"
    exit 1
    ;;
esac
