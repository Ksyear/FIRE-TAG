#!/usr/bin/env bash
# FIRE-TAG Pi setup — Raspberry Pi 4, Ubuntu Server 22.04 / 24.04.
# Run ONCE while the Pi still has internet (Ethernet recommended); the
# hotspot step afterwards takes wlan0 away from internet access.
#
# Installs
#   python3-serial                Anchor 0 USB serial
#   network-manager, dnsmasq-base needed by setup_hotspot.sh: netplan's Wi-Fi
#                                 access-point mode only works with the
#                                 NetworkManager renderer, which uses dnsmasq
#                                 for the hotspot's DHCP
# and two systemd services that start on boot:
#   fire-tag-receiver : Anchor 0 USB serial <-> data/fire_tag.db
#   fire-tag-web      : data/fire_tag.db -> http://<pi>:80
#
# Undo: sudo systemctl disable --now fire-tag-receiver fire-tag-web
#       sudo rm /etc/systemd/system/fire-tag-{receiver,web}.service
set -euo pipefail

DIR="$(cd "$(dirname "$0")" && pwd)"
RUN_USER="${SUDO_USER:-$USER}"

if [[ "$DIR" == *" "* ]]; then
  echo "Copy this folder to a path without spaces (e.g. ~/fire-tag) first." >&2
  exit 1
fi
if ! grep -qi '^ID=ubuntu' /etc/os-release; then
  echo "Note: written for Ubuntu Server; continuing anyway." >&2
fi

sudo apt-get update
sudo apt-get install -y python3-serial network-manager dnsmasq-base
mkdir -p "$DIR/data"
# Serial port access (Ubuntu's default user already has it; harmless otherwise).
sudo usermod -aG dialout "$RUN_USER"

# brltty claims some USB-serial chips (incl. CP210x) on Ubuntu and makes
# /dev/ttyUSB0 vanish. Server images normally do not ship it.
if dpkg -s brltty >/dev/null 2>&1; then
  echo "WARNING: brltty is installed and can steal Anchor 0's /dev/ttyUSB0."
  echo "         If the receiver cannot find the port: sudo apt remove brltty"
fi

sudo tee /etc/systemd/system/fire-tag-receiver.service >/dev/null <<EOF
[Unit]
Description=FIRE-TAG receiver (Anchor 0 serial <-> SQLite)
After=multi-user.target

[Service]
User=$RUN_USER
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 -u $DIR/fire_tag_receiver.py --db $DIR/data/fire_tag.db
# Anchor 0 unplugged or not found -> exit -> retry.
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo tee /etc/systemd/system/fire-tag-web.service >/dev/null <<EOF
[Unit]
Description=FIRE-TAG web dashboard (port 80)
After=multi-user.target

[Service]
User=$RUN_USER
WorkingDirectory=$DIR
ExecStart=/usr/bin/python3 -u $DIR/fire_tag_web.py --db $DIR/data/fire_tag.db --port 80
# Lets a normal user bind port 80 without running as root.
AmbientCapabilities=CAP_NET_BIND_SERVICE
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now fire-tag-receiver fire-tag-web
systemctl --no-pager --lines=5 status fire-tag-receiver fire-tag-web || true

if command -v ufw >/dev/null && sudo ufw status | grep -q "Status: active"; then
  echo
  echo "ufw firewall is active. Allow the dashboard and hotspot DHCP/DNS:"
  echo "  sudo ufw allow 80/tcp && sudo ufw allow in on wlan0 to any port 67 proto udp && sudo ufw allow in on wlan0 to any port 53"
fi
echo
echo "Logs: journalctl -u fire-tag-receiver -f"
echo "Next: ./setup_hotspot.sh <password>   (turns wlan0 into the FIRE-TAG access point)"
