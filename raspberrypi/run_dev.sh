#!/usr/bin/env bash
# Start the receiver and the dashboard for testing, without sudo or systemd.
#   ./run_dev.sh            start (dashboard on port 8080), print the address
#   ./run_dev.sh stop       stop both
#   ./run_dev.sh status     show whether they run, last log lines
# For the always-on setup use setup_pi.sh (systemd, port 80) instead.
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
PORT="${PORT:-8080}"
mkdir -p "$DIR/data"

stop() {
  pkill -f "$DIR/fire_tag_receiver.py" 2>/dev/null || true
  pkill -f "$DIR/fire_tag_web.py" 2>/dev/null || true
}

case "${1:-start}" in
  stop)
    stop
    echo "stopped"
    ;;
  status)
    pgrep -fl "$DIR/fire_tag_(receiver|web).py" || echo "not running"
    tail -n 5 "$DIR/data/receiver.log" "$DIR/data/web.log" 2>/dev/null || true
    ;;
  start)
    stop
    nohup python3 -u "$DIR/fire_tag_receiver.py" --db "$DIR/data/fire_tag.db" --record "$DIR/data/raw.jsonl" \
      > "$DIR/data/receiver.log" 2>&1 &
    receiver_pid=$!
    nohup python3 -u "$DIR/fire_tag_web.py" --db "$DIR/data/fire_tag.db" --port "$PORT" > "$DIR/data/web.log" 2>&1 &
    web_pid=$!
    sleep 2
    if ! kill -0 "$receiver_pid" 2>/dev/null || ! kill -0 "$web_pid" 2>/dev/null; then
      echo "receiver or dashboard failed to start:" >&2
      tail -n 15 "$DIR/data/receiver.log" "$DIR/data/web.log" >&2
      stop
      exit 1
    fi
    pgrep -fl "$DIR/fire_tag_(receiver|web).py"
    for ip in $(hostname -I 2>/dev/null || ipconfig getifaddr en0); do
      echo "Dashboard: http://$ip:$PORT"
    done
    ;;
  *)
    sed -n '2,6p' "$0"
    exit 1
    ;;
esac
