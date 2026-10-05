#!/usr/bin/env bash
# One command on the Raspberry Pi (no sudo, no git, no pip):
#   curl -fsSL https://raw.githubusercontent.com/Ksyear/FIRE-TAG/feat/pi-live-demo/raspberrypi/bootstrap.sh | bash
# Downloads the raspberrypi/ folder into ~/fire-tag, checks the Pi, and starts
# the receiver and the dashboard (port 8080). Run it again to update; the
# measured anchor positions in config.json and the data/ folder are kept.
set -euo pipefail

BRANCH="${FIRE_TAG_BRANCH:-feat/pi-live-demo}"
DEST="${FIRE_TAG_DIR:-$HOME/fire-tag}"
URL="https://codeload.github.com/Ksyear/FIRE-TAG/tar.gz/refs/heads/$BRANCH"

echo "== FIRE-TAG setup into $DEST (branch $BRANCH)"
command -v python3 >/dev/null || { echo "python3 is missing (Ubuntu Server normally has it)" >&2; exit 1; }
python3 --version

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
curl -fsSL "$URL" | tar -xz -C "$tmp"
src="$(find "$tmp" -mindepth 2 -maxdepth 2 -type d -name raspberrypi | head -1)"
[ -n "$src" ] || { echo "download did not contain raspberrypi/" >&2; exit 1; }

mkdir -p "$DEST"
if [ -f "$DEST/config.json" ]; then
  cp "$src/config.json" "$DEST/config.json.new"     # keep measured anchor positions
  rm "$src/config.json"
fi
cp -R "$src"/. "$DEST"/
chmod +x "$DEST"/*.sh "$DEST"/*.py

echo "== Checks"
if id -nG | tr ' ' '\n' | grep -qx dialout; then
  echo "serial permission: ok ($USER is in dialout)"
else
  echo "serial permission: MISSING. Run: sudo usermod -aG dialout $USER  then log out and in" >&2
fi
ports="$(ls /dev/serial/by-id/* 2>/dev/null || true)"
if [ -n "$ports" ]; then
  echo "USB serial devices:"; echo "$ports" | sed 's/^/  /'
else
  echo "no USB serial device found: plug Anchor 0 into the Pi" >&2
fi

echo "== Start"
"$DEST/run_dev.sh" start
echo
echo "Open the address above from a phone or laptop on the same Wi-Fi."
echo "If it does not open: sudo ufw status  (if active: sudo ufw allow 8080/tcp)"
echo "Logs: $DEST/run_dev.sh status"
