#!/usr/bin/env bash
# Turns the Pi's wlan0 into the FIRE-TAG Wi-Fi access point.
# Raspberry Pi 4 + Ubuntu Server (netplan). Dashboard: http://10.42.0.1
#
#   ./setup_hotspot.sh <password-8..63-chars> [ssid]
#
# How: writes /etc/netplan/90-fire-tag-ap.yaml with "mode: ap" under the
# NetworkManager renderer (netplan supports AP only there; it turns into
# NetworkManager "shared" mode = DHCP for phones, Pi at 10.42.0.1).
#
# WARNING: wlan0 stops being a Wi-Fi client, so the Pi loses Wi-Fi internet
# and SSH over Wi-Fi drops. Run setup_pi.sh first, and run this over
# Ethernet or with a keyboard/monitor.
# Undo: sudo rm /etc/netplan/90-fire-tag-ap.yaml && sudo netplan apply
set -euo pipefail

PASS="${1:?usage: $0 <password-8..63-chars> [ssid]}"
SSID="${2:-FIRE-TAG}"
# 2.4 GHz channel 11: every phone supports it, it is allowed without a
# country setting, and it stays clear of the anchors' ESP-NOW on channel 1.
CHANNEL="${CHANNEL:-11}"
FILE=/etc/netplan/90-fire-tag-ap.yaml

if (( ${#PASS} < 8 || ${#PASS} > 63 )); then
  echo "WPA2 password must be 8-63 characters" >&2
  exit 1
fi
for v in "$PASS" "$SSID"; do
  if [[ "$v" == *'"'* || "$v" == *'\'* ]]; then
    echo 'SSID/password must not contain " or \' >&2
    exit 1
  fi
done
if ! command -v nmcli >/dev/null; then
  echo "NetworkManager is missing. Run ./setup_pi.sh while the Pi has internet." >&2
  exit 1
fi

# If Wi-Fi was set up in Raspberry Pi Imager, cloud-init already declared
# wlan0 as a Wi-Fi client in another netplan file. Two configs for one
# interface would conflict, so stop and let the user decide.
others=$(sudo grep -l -E '^[[:space:]]*(wifis|wlan0):' /etc/netplan/*.yaml 2>/dev/null | grep -v "^$FILE\$" || true)
if [[ -n "$others" ]]; then
  echo "wlan0 is already configured as a Wi-Fi client in:" >&2
  echo "$others" >&2
  echo "Back that file up, remove its 'wifis:' section (keep ethernets), then re-run." >&2
  exit 1
fi

sudo install -m 600 /dev/null "$FILE"
sudo tee "$FILE" >/dev/null <<EOF
# FIRE-TAG hotspot (written by setup_hotspot.sh)
network:
  version: 2
  wifis:
    wlan0:
      renderer: NetworkManager
      dhcp4: false
      addresses: [10.42.0.1/24]
      access-points:
        "$SSID":
          password: "$PASS"
          mode: ap
          band: 2.4GHz
          channel: $CHANNEL
EOF

sudo netplan generate   # validates the YAML before touching the network
sudo netplan apply
sleep 5
nmcli device status || true
ip -4 addr show wlan0 || true

echo
echo "Hotspot '$SSID' should be up. Connect a phone and open http://10.42.0.1"
echo "If wlan0 has no 10.42.0.1 address: journalctl -u NetworkManager -n 50"
