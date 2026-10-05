// FIRE-TAG shared UWB definitions.
// Tag (LOLIN D32) and Anchors (ESP32 DevKitC) include this file so that
// channel, preamble, timing and frame layout can never differ between them.
#pragma once

#include <Arduino.h>
#include "dw3000.h"

namespace firetag {

// ---------------------------------------------------------------------------
// Wiring: same on DevKitC and LOLIN D32. Verified by fire_tag_spi_test
// (DEV_ID 0xDECA0302) on 2026-10-05.
// ---------------------------------------------------------------------------
constexpr int PIN_SCK = 18;
constexpr int PIN_MISO = 19;
constexpr int PIN_MOSI = 23;
constexpr int PIN_CS = 27;
constexpr int PIN_RST = 26;  // open-drain LOW only, never driven HIGH
constexpr int PIN_IRQ = 34;  // polled, not used as interrupt

// DW3000 accepts at most 7 MHz SPI before its PLL locks. Jumper wires are
// long, so stay below that. Lower to 2 MHz if init fails intermittently.
constexpr uint32_t UWB_SPI_HZ = 4000000;

// USB serial speed. Must equal "serial_baud" in raspberrypi/config.json.
// Anchor 0 sends ~5 KB/s at 10 Hz, so 9600 is far too slow: the TX buffer
// would fill and block the UWB loop. If 115200 garbles on a board (seen in
// the SPI test), try 57600 together with the tag's CYCLE_MS = 200.
constexpr uint32_t SERIAL_BAUD = 115200;

// ---------------------------------------------------------------------------
// Network
// ---------------------------------------------------------------------------
constexpr uint8_t NUM_ANCHORS = 3;
constexpr uint16_t PAN_ID = 0xDECA;
constexpr uint16_t ANCHOR_ADDR_BASE = 0x4100;  // 'A' 0x00 -> anchor 0
constexpr uint16_t TAG_ADDR_BASE = 0x5400;     // 'T' 0x00 -> tag 0

inline uint16_t anchorAddr(uint8_t id) { return ANCHOR_ADDR_BASE + id; }
inline uint16_t tagAddr(uint8_t id) { return TAG_ADDR_BASE + id; }

// Default antenna delay (Qorvo examples). Calibrate per board later; until
// then the Raspberry Pi side can subtract a per-anchor bias.
constexpr uint16_t ANT_DLY = 16385;

// ---------------------------------------------------------------------------
// DS-TWR timing, in UWB microseconds (1 uus = 1.0256 us).
// Qorvo's STM32 examples use ~700-900 uus; ESP32 + Arduino SPI needs more CPU
// headroom, so both sides reply 2000 uus after the received frame.
// RX window opens 1500 uus after our TX ends and stays open 1200 uus,
// which brackets the reply (~1870-2050 us after TX end) with margin.
// ---------------------------------------------------------------------------
constexpr uint32_t REPLY_DLY_UUS = 2000;
constexpr uint32_t RX_AFTER_TX_DLY_UUS = 1500;
constexpr uint32_t RX_TIMEOUT_UUS = 1200;
// Software guard in case the radio never raises a status bit.
constexpr uint32_t SW_GUARD_MS = 20;

// ---------------------------------------------------------------------------
// Frame layout: IEEE 802.15.4 data frame, PAN ID compression, 16-bit addrs.
//   [0..1] frame control 0x41 0x88
//   [2]    MAC sequence number
//   [3..4] PAN ID (LE)
//   [5..6] destination address (LE)
//   [7..8] source address (LE)
//   [9]    function code
//   [10..11] cycle sequence (LE) - same for all anchors in one tag cycle
//   RESP only:  [12] flags, anchor -> tag (downlink from the Pi)
//   FINAL only: [12..15] poll_tx_ts, [16..19] resp_rx_ts, [20..23] final_tx_ts,
//               [24] flags, tag -> anchor (tag echoes the state it applied)
// Lengths below exclude the 2-byte FCS the radio appends.
// ---------------------------------------------------------------------------
constexpr uint8_t FN_POLL = 0x21;
constexpr uint8_t FN_RESP = 0x10;
constexpr uint8_t FN_FINAL = 0x23;
// Anchor calibration uses the same payload layout with distinct function codes.
constexpr uint8_t FN_ANCHOR_POLL = 0x31;
constexpr uint8_t FN_ANCHOR_RESP = 0x32;
constexpr uint8_t FN_ANCHOR_FINAL = 0x33;

constexpr size_t IDX_SEQ = 2;
constexpr size_t IDX_DST = 5;
constexpr size_t IDX_SRC = 7;
constexpr size_t IDX_FN = 9;
constexpr size_t IDX_CYCLE = 10;
constexpr size_t IDX_RESP_FLAGS = 12;
constexpr size_t IDX_POLL_TX_TS = 12;
constexpr size_t IDX_RESP_RX_TS = 16;
constexpr size_t IDX_FINAL_TX_TS = 20;
constexpr size_t IDX_FINAL_FLAGS = 24;

constexpr size_t POLL_LEN = 12;
constexpr size_t RESP_LEN = 13;
constexpr size_t FINAL_LEN = 25;
constexpr size_t RX_BUF_LEN = 32;

constexpr uint8_t FLAG_ALERT = 0x01;  // rescue alert: tag blinks its LED
constexpr uint8_t MAX_TAGS = 8;       // alert mask has one bit per tag id

void writeHeader(uint8_t *frame, uint8_t macSeq, uint16_t dst, uint16_t src,
                 uint8_t fn, uint16_t cycleSeq);

// True if frame is ours: correct frame control, PAN, destination and function.
bool isFrameFor(const uint8_t *frame, size_t len, uint16_t myAddr,
                uint8_t fn, size_t minLen);

inline uint16_t get16(const uint8_t *p) { return uint16_t(p[0]) | (uint16_t(p[1]) << 8); }
inline void put16(uint8_t *p, uint16_t v) { p[0] = uint8_t(v); p[1] = uint8_t(v >> 8); }

// Resets and configures the DW3000. Prints the failing step and returns false
// on error; the caller decides whether to retry or halt.
bool initRadio();

// Writes the frame and its length into the TX buffer (FCS added by radio).
void loadTxFrame(uint8_t *frame, size_t len);

// Busy-waits until any bit in mask is set or the software guard expires.
// Returns the status register (0 on guard expiry, after forcing TRX off).
uint32_t waitStatus(uint32_t mask);

// Reads the received frame into buf. Returns its length without FCS,
// or 0 if it does not fit.
size_t readRxFrame(uint8_t *buf, size_t bufLen);

// ---------------------------------------------------------------------------
// Anchor -> gateway (Anchor 0) report, sent over ESP-NOW.
// ---------------------------------------------------------------------------
constexpr uint8_t ESPNOW_CHANNEL = 1;
constexpr uint8_t REPORT_VERSION = 2;
constexpr uint8_t REPORT_RANGE = 1;
constexpr uint8_t REPORT_HEARTBEAT = 2;
constexpr uint8_t REPORT_ACK = 3;
constexpr uint8_t REPORT_ANCHOR_RANGE = 4;

struct __attribute__((packed)) Report {
  uint8_t magic[2];   // 'F','T'
  uint8_t version;    // REPORT_VERSION
  uint8_t type;       // REPORT_RANGE, REPORT_HEARTBEAT, REPORT_ACK, REPORT_ANCHOR_RANGE
  uint8_t anchorId;
  uint8_t tagId;      // RANGE: tag; ANCHOR_RANGE: initiating anchor
  uint16_t cycleSeq;  // RANGE: tag cycle; ANCHOR_RANGE: command id
  int32_t rangeMm;    // RANGE or ANCHOR_RANGE
  uint32_t anchorMs;  // millis() on the sending anchor
  uint32_t okCount;   // successful ranges since boot
  uint32_t failCount; // aborted exchanges since boot
  uint8_t flags;      // RANGE: flags echoed by the tag; HEARTBEAT: alert mask
  uint8_t cmd;        // ACK: command code
  uint16_t cmdId;     // ACK: command id from the Pi
  uint8_t cmdOk;      // ACK: 1 if executed; CMD_RANGE: request accepted only
};

inline bool isValidReport(const uint8_t *data, int len) {
  if (len != int(sizeof(Report))) return false;
  const Report *r = reinterpret_cast<const Report *>(data);
  return r->magic[0] == 'F' && r->magic[1] == 'T' && r->version == REPORT_VERSION;
}

// ---------------------------------------------------------------------------
// Pi -> anchors. The Pi writes "CMD <id> <target> <name> <arg>" to Anchor 0's
// USB serial; Anchor 0 runs it and/or forwards it over ESP-NOW as Command.
// ---------------------------------------------------------------------------
constexpr uint8_t COMMAND_VERSION = 1;
constexpr uint8_t CMD_PING = 1;    // reply with an ACK
constexpr uint8_t CMD_REBOOT = 2;  // ACK, then restart
constexpr uint8_t CMD_ALERT = 3;   // arg = alert mask (bit n = tag n)
constexpr uint8_t CMD_RANGE = 4;   // arg = peer anchor id; ACK means accepted
constexpr uint8_t TARGET_ALL = 0xFF;

struct __attribute__((packed)) Command {
  uint8_t magic[2];  // 'F','C'
  uint8_t version;   // COMMAND_VERSION
  uint8_t target;    // anchor id or TARGET_ALL
  uint16_t cmdId;
  uint8_t cmd;
  uint8_t arg;
};

inline bool isValidCommand(const uint8_t *data, int len) {
  if (len != int(sizeof(Command))) return false;
  const Command *c = reinterpret_cast<const Command *>(data);
  return c->magic[0] == 'F' && c->magic[1] == 'C' && c->version == COMMAND_VERSION;
}

}  // namespace firetag
