#!/usr/bin/env bash
# FIRE-TAG firmware build/upload helper (macOS, Arduino IDE 2 bundled arduino-cli).
#
#   ./build.sh tag                       # compile Tag (LOLIN D32)
#   ./build.sh anchor 1                  # compile Anchor 1 (ESP32 DevKitC)
#   ./build.sh tag /dev/cu.usbserial-XXX # compile + upload Tag
#   ./build.sh anchor 0 /dev/cu.usbserial-XXX
#   SAFE_UPLOAD=1 ./build.sh anchor 2 /dev/cu.usbserial-XXX
#       slow but reliable: esptool at 38400 baud with --no-stub, the settings
#       that worked on 2026-10-05 when normal uploads failed (SPI test report)
#
# Uses libraries/FireTagUwb and the DW3000 driver pinned as a git submodule
# (run `git submodule update --init` once); nothing is installed into
# ~/Documents/Arduino.
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CLI="${ARDUINO_CLI:-/Applications/Arduino IDE.app/Contents/Resources/app/lib/backend/resources/arduino-cli}"
ESPTOOL="${ESPTOOL:-$(ls -d "$HOME"/Library/Arduino15/packages/esp32/tools/esptool_py/*/esptool 2>/dev/null | tail -1)}"
# The ctags bundled with arduino-cli is x86_64; on Apple Silicon without
# Rosetta point CTAGS_DIR at an arm64 build (the one built on 2026-10-05).
CTAGS_DIR="${CTAGS_DIR:-$HOME/Documents/Codex/2026-10-05/fire-tag-uwb-qorvo-dwm3000evb-4/work/ctags-master}"
BUILD_ROOT="${BUILD_ROOT:-${TMPDIR:-/tmp}/fire-tag-build}"
DW3000_LIB="$HERE/third_party/Makerfabs-ESP32-UWB-DW3000/Dw3000"

if [[ ! -f "$DW3000_LIB/library.properties" ]]; then
  echo "DW3000 driver missing. Run: git submodule update --init" >&2
  exit 1
fi

role="${1:-}"
case "$role" in
  tag)
    sketch="$HERE/fire_tag_tag"
    fqbn="esp32:esp32:d32"
    port="${2:-}"
    build="$BUILD_ROOT/tag"
    extra=()
    ;;
  anchor)
    id="${2:?anchor id (0, 1 or 2) required}"
    [[ "$id" =~ ^[0-2]$ ]] || { echo "anchor id must be 0, 1 or 2" >&2; exit 1; }
    sketch="$HERE/fire_tag_anchor"
    fqbn="esp32:esp32:esp32"
    port="${3:-}"
    build="$BUILD_ROOT/anchor$id"
    extra=(--build-property "compiler.cpp.extra_flags=-DANCHOR_ID=$id")
    ;;
  *)
    sed -n '2,12p' "$0"
    exit 1
    ;;
esac

ctags_prop=()
if [[ -x "$CTAGS_DIR/ctags" ]]; then
  ctags_prop=(--build-property "runtime.tools.ctags.path=$CTAGS_DIR")
fi

"$CLI" compile --fqbn "$fqbn" --libraries "$HERE/libraries" --library "$DW3000_LIB" \
  ${ctags_prop[@]+"${ctags_prop[@]}"} ${extra[@]+"${extra[@]}"} --build-path "$build" "$sketch"

[[ -n "$port" ]] || exit 0

if [[ "${SAFE_UPLOAD:-0}" == 1 ]]; then
  [[ -x "$ESPTOOL" ]] || { echo "esptool not found; set ESPTOOL=/path/to/esptool" >&2; exit 1; }
  name="$(basename "$sketch").ino"
  "$ESPTOOL" --chip esp32 --port "$port" --baud "${UPLOAD_BAUD:-38400}" \
    --before default-reset --after hard-reset --no-stub write-flash -z \
    --flash-mode keep --flash-freq keep --flash-size keep \
    0x1000 "$build/$name.bootloader.bin" \
    0x8000 "$build/$name.partitions.bin" \
    0xe000 "$build/boot_app0.bin" \
    0x10000 "$build/$name.bin"
else
  "$CLI" upload --fqbn "$fqbn" --port "$port" --input-dir "$build" "$sketch"
fi
