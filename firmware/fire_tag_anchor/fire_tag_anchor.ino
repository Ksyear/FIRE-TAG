// FIRE-TAG Anchor — ESP32 DevKitC + DWM3000EVB
//
// DS-TWR responder. Computes the tag distance when the FINAL frame arrives.
//   ANCHOR_ID 0    : gateway. Prints every range (its own and the ones received
//                    from Anchors 1/2 over ESP-NOW) as JSON lines on USB serial
//                    for the Raspberry Pi, and takes "CMD ..." lines from the Pi.
//   ANCHOR_ID 1, 2 : sends each range to Anchor 0 over ESP-NOW broadcast and
//                    runs commands Anchor 0 forwards.
// The Pi's alert mask rides in every RESP frame, so the tag sees it within one
// cycle and echoes it back in FINAL.
//
// Set ANCHOR_ID before uploading to each board (or pass -DANCHOR_ID=n).
// Board: "ESP32 Dev Module" (esp32:esp32:esp32). Needs DW3000 and FireTagUwb.

#ifndef ANCHOR_ID
#define ANCHOR_ID 0
#endif

#include <WiFi.h>
#include <esp_now.h>
#include <esp_wifi.h>
#include <FireTagUwb.h>

using namespace firetag;

static_assert(ANCHOR_ID < NUM_ANCHORS, "ANCHOR_ID must be 0..NUM_ANCHORS-1");
constexpr bool IS_GATEWAY = (ANCHOR_ID == 0);
constexpr uint32_t HEARTBEAT_MS = 1000;
constexpr uint32_t REBOOT_DELAY_MS = 300;  // let the ACK leave first

static const uint8_t BROADCAST_MAC[6] = {0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF};

static uint8_t macSeq = 0;
static uint8_t rxBuf[RX_BUF_LEN];
static uint32_t okCount = 0;
static uint32_t failCount = 0;
static uint32_t espNowFailCount = 0;
static uint32_t lastHeartbeatMs = 0;
static uint8_t alertMask = 0;  // bit n = rescue alert on for tag n; set by the Pi
static bool rebootPending = false;
static uint32_t rebootRequestedMs = 0;
static bool rangePending = false;
static uint8_t rangePeer = 0;
static uint16_t rangeCmdId = 0;

// ESP-NOW callbacks run in the Wi-Fi task, so hand data to loop() via queues.
struct Received {
  Report report;
  int8_t rssi;
};
static QueueHandle_t rxQueue = nullptr;   // gateway: reports from Anchors 1/2
static QueueHandle_t cmdQueue = nullptr;  // Anchors 1/2: commands from the gateway

static const char *cmdName(uint8_t cmd) {
  switch (cmd) {
    case CMD_PING: return "ping";
    case CMD_REBOOT: return "reboot";
    case CMD_ALERT: return "alert";
    case CMD_RANGE: return "range";
    default: return "unknown";
  }
}

static uint8_t cmdCode(const char *name) {
  for (uint8_t c : {CMD_PING, CMD_REBOOT, CMD_ALERT, CMD_RANGE}) {
    if (strcmp(name, cmdName(c)) == 0) return c;
  }
  return 0;
}

// ---------------------------------------------------------------------------
// Output to the Raspberry Pi (gateway) — one JSON object per line.
// Lines starting with '#' are human-readable logs and are ignored by the Pi.
// ---------------------------------------------------------------------------
static void printReport(const Report &r, const char *via, bool hasRssi, int rssi) {
  if (r.type == REPORT_RANGE) {
    Serial.printf("{\"type\":\"range\",\"anchor\":%u,\"tag\":%u,\"seq\":%u,\"range_mm\":%ld,"
                  "\"tag_alert\":%s,\"anchor_ms\":%lu,\"via\":\"%s\"",
                  r.anchorId, r.tagId, r.cycleSeq, static_cast<long>(r.rangeMm),
                  (r.flags & FLAG_ALERT) ? "true" : "false",
                  static_cast<unsigned long>(r.anchorMs), via);
  } else if (r.type == REPORT_ANCHOR_RANGE) {
    Serial.printf("{\"type\":\"anchor_range\",\"anchor\":%u,\"peer\":%u,\"seq\":%u,\"range_mm\":%ld,"
                  "\"anchor_ms\":%lu,\"via\":\"%s\"",
                  r.anchorId, r.tagId, r.cycleSeq, static_cast<long>(r.rangeMm),
                  static_cast<unsigned long>(r.anchorMs), via);
  } else if (r.type == REPORT_ACK) {
    Serial.printf("{\"type\":\"ack\",\"anchor\":%u,\"id\":%u,\"cmd\":\"%s\",\"ok\":%s,"
                  "\"anchor_ms\":%lu,\"via\":\"%s\"",
                  r.anchorId, r.cmdId, cmdName(r.cmd), r.cmdOk ? "true" : "false",
                  static_cast<unsigned long>(r.anchorMs), via);
  } else {
    Serial.printf("{\"type\":\"status\",\"anchor\":%u,\"ok\":%lu,\"fail\":%lu,\"alert_mask\":%u,"
                  "\"anchor_ms\":%lu,\"via\":\"%s\"",
                  r.anchorId, static_cast<unsigned long>(r.okCount),
                  static_cast<unsigned long>(r.failCount), r.flags,
                  static_cast<unsigned long>(r.anchorMs), via);
  }
  if (hasRssi) Serial.printf(",\"link_rssi\":%d", rssi);
  Serial.println("}");
}

static void onEspNowRecv(const esp_now_recv_info_t *info, const uint8_t *data, int len) {
  if (IS_GATEWAY) {
    if (!isValidReport(data, len)) return;
    Received item;
    memcpy(&item.report, data, sizeof(Report));
    item.rssi = info->rx_ctrl ? info->rx_ctrl->rssi : 0;
    xQueueSend(rxQueue, &item, 0);  // drop if full rather than block Wi-Fi task
  } else if (isValidCommand(data, len)) {
    Command c;
    memcpy(&c, data, sizeof(Command));
    if (c.target == ANCHOR_ID || c.target == TARGET_ALL) xQueueSend(cmdQueue, &c, 0);
  }
}

// Gateway prints locally; Anchors 1/2 send to the gateway.
static void publish(const Report &r) {
  if (IS_GATEWAY) {
    printReport(r, "local", false, 0);
  } else if (esp_now_send(BROADCAST_MAC, reinterpret_cast<const uint8_t *>(&r), sizeof(r)) != ESP_OK) {
    ++espNowFailCount;
  }
}

static Report makeReport(uint8_t type) {
  Report r = {};
  r.magic[0] = 'F';
  r.magic[1] = 'T';
  r.version = REPORT_VERSION;
  r.type = type;
  r.anchorId = ANCHOR_ID;
  r.anchorMs = millis();
  r.okCount = okCount;
  r.failCount = failCount;
  return r;
}

// ---------------------------------------------------------------------------
// Commands from the Pi
// ---------------------------------------------------------------------------
static bool execute(uint16_t id, uint8_t cmd, uint8_t arg) {
  switch (cmd) {
    case CMD_PING:
      return true;
    case CMD_ALERT:
      alertMask = arg;
      return true;
    case CMD_REBOOT:
      rebootPending = true;
      rebootRequestedMs = millis();
      return true;
    case CMD_RANGE:
      // Keep one request, including duplicates, until loop() completes it.
      if (arg >= NUM_ANCHORS || arg == ANCHOR_ID || rangePending) return false;
      rangePeer = arg;
      rangeCmdId = id;
      rangePending = true;
      return true;
    default:
      return false;
  }
}

static void runCommand(uint16_t id, uint8_t cmd, uint8_t arg) {
  Report r = makeReport(REPORT_ACK);
  r.cmd = cmd;
  r.cmdId = id;
  r.cmdOk = execute(id, cmd, arg) ? 1 : 0;
  publish(r);
}

// Pi -> gateway: "CMD <id> <target> <name> [arg]", target 255 = all anchors.
static void handlePiLine(const char *line) {
  unsigned id = 0, target = 0, arg = 0;
  char name[16] = {};
  const int fields = sscanf(line, "CMD %u %u %15s %u", &id, &target, name, &arg);
  if (fields < 3) return;
  const uint8_t cmd = cmdCode(name);
  // Do not truncate an invalid peer into a valid uint8_t, or range all anchors.
  if (cmd == CMD_RANGE && (fields != 4 || arg >= NUM_ANCHORS || target >= NUM_ANCHORS)) {
    arg = NUM_ANCHORS;  // recipients return an explicit negative ACK
  }
  if (target == ANCHOR_ID || target == TARGET_ALL) {
    runCommand(uint16_t(id), cmd, uint8_t(arg));
  }
  if (target != ANCHOR_ID) {
    const Command c = {{'F', 'C'}, COMMAND_VERSION, uint8_t(target), uint16_t(id), cmd, uint8_t(arg)};
    if (esp_now_send(BROADCAST_MAC, reinterpret_cast<const uint8_t *>(&c), sizeof(c)) != ESP_OK) {
      ++espNowFailCount;
    }
  }
}

static void readPiSerial() {
  static char line[96];
  static size_t len = 0;
  while (Serial.available()) {
    const char ch = char(Serial.read());
    if (ch == '\n' || ch == '\r') {
      if (len) {
        line[len] = '\0';
        handlePiLine(line);
        len = 0;
      }
    } else if (len < sizeof(line) - 1) {
      line[len++] = ch;
    } else {
      len = 0;  // overlong line: drop it
    }
  }
}

static bool initEspNow() {
  WiFi.mode(WIFI_STA);
  WiFi.setChannel(ESPNOW_CHANNEL);
  esp_wifi_set_ps(WIFI_PS_NONE);  // do not miss packets while modem-sleeping
  if (esp_now_init() != ESP_OK) return false;

  if (IS_GATEWAY) {
    rxQueue = xQueueCreate(32, sizeof(Received));
    if (!rxQueue) return false;
  } else {
    cmdQueue = xQueueCreate(8, sizeof(Command));
    if (!cmdQueue) return false;
  }
  if (esp_now_register_recv_cb(onEspNowRecv) != ESP_OK) return false;

  // Broadcast peer: gateway forwards commands, Anchors 1/2 send reports.
  esp_now_peer_info_t peer = {};
  memcpy(peer.peer_addr, BROADCAST_MAC, sizeof(BROADCAST_MAC));
  peer.channel = ESPNOW_CHANNEL;
  peer.ifidx = WIFI_IF_STA;
  peer.encrypt = false;
  return esp_now_add_peer(&peer) == ESP_OK;
}

// ---------------------------------------------------------------------------
// UWB responder. Same flow as Qorvo ex_05b_ds_twr_resp, plus addressing.
// ---------------------------------------------------------------------------
static void clearExchangeEvents() {
  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK |
                                       SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
}

static void startListening() {
  dwt_forcetrxoff();
  clearExchangeEvents();
  dwt_setrxtimeout(0);
  dwt_setpreambledetecttimeout(0);
  dwt_rxenable(DWT_START_RX_IMMEDIATE);
}

static void failExchange() {
  dwt_forcetrxoff();
  clearExchangeEvents();
  ++failCount;
}

// One calibration attempt; the responder calculates and reports the distance.
// A running Tag can collide with this exchange. The Pi retries missing reports.
static void rangeWithAnchor(uint8_t peerId, uint16_t id) {
  const uint16_t me = anchorAddr(ANCHOR_ID);
  const uint16_t peer = anchorAddr(peerId);
  dwt_forcetrxoff();
  clearExchangeEvents();

  uint8_t poll[POLL_LEN];
  writeHeader(poll, macSeq++, peer, me, FN_ANCHOR_POLL, id);
  dwt_setrxaftertxdelay(RX_AFTER_TX_DLY_UUS);
  dwt_setrxtimeout(RX_TIMEOUT_UUS);
  dwt_setpreambledetecttimeout(0);
  loadTxFrame(poll, POLL_LEN);
  if (dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED) != DWT_SUCCESS) {
    failExchange();
    return;
  }

  const uint32_t status =
      waitStatus(SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
  if (!(status & SYS_STATUS_RXFCG_BIT_MASK)) {
    failExchange();
    return;
  }
  clearExchangeEvents();
  const size_t len = readRxFrame(rxBuf, sizeof(rxBuf));
  if (!isFrameFor(rxBuf, len, me, FN_ANCHOR_RESP, RESP_LEN) ||
      get16(rxBuf + IDX_SRC) != peer || get16(rxBuf + IDX_CYCLE) != id) {
    failExchange();
    return;
  }

  const uint64_t pollTxTs = get_tx_timestamp_u64();
  const uint64_t respRxTs = get_rx_timestamp_u64();
  const uint32_t finalTxTime =
      (respRxTs + uint64_t(REPLY_DLY_UUS) * UUS_TO_DWT_TIME) >> 8;
  const uint64_t finalTxTs = (uint64_t(finalTxTime & 0xFFFFFFFEUL) << 8) + ANT_DLY;

  uint8_t fin[FINAL_LEN];
  writeHeader(fin, macSeq++, peer, me, FN_ANCHOR_FINAL, id);
  final_msg_set_ts(fin + IDX_POLL_TX_TS, pollTxTs);
  final_msg_set_ts(fin + IDX_RESP_RX_TS, respRxTs);
  final_msg_set_ts(fin + IDX_FINAL_TX_TS, finalTxTs);
  fin[IDX_FINAL_FLAGS] = 0;
  dwt_setdelayedtrxtime(finalTxTime);
  loadTxFrame(fin, FINAL_LEN);
  if (dwt_starttx(DWT_START_TX_DELAYED) != DWT_SUCCESS ||
      !(waitStatus(SYS_STATUS_TXFRS_BIT_MASK) & SYS_STATUS_TXFRS_BIT_MASK)) {
    failExchange();
    return;
  }
  clearExchangeEvents();
}

// Called with a good frame waiting in the RX buffer.
static void respondIfPoll() {
  const uint16_t me = anchorAddr(ANCHOR_ID);
  size_t len = readRxFrame(rxBuf, sizeof(rxBuf));
  const bool anchorExchange = isFrameFor(rxBuf, len, me, FN_ANCHOR_POLL, POLL_LEN);
  if (!anchorExchange && !isFrameFor(rxBuf, len, me, FN_POLL, POLL_LEN)) return;

  const uint16_t source = get16(rxBuf + IDX_SRC);
  if (anchorExchange) {
    if (source < ANCHOR_ADDR_BASE || source >= ANCHOR_ADDR_BASE + NUM_ANCHORS || source == me) return;
  } else if (source < TAG_ADDR_BASE || source >= TAG_ADDR_BASE + MAX_TAGS) {
    return;
  }
  const uint8_t peerId = uint8_t(source - (anchorExchange ? ANCHOR_ADDR_BASE : TAG_ADDR_BASE));
  const uint16_t cycle = get16(rxBuf + IDX_CYCLE);
  const uint64_t pollRxTs = get_rx_timestamp_u64();
  const uint32_t respTxTime =
      (pollRxTs + uint64_t(REPLY_DLY_UUS) * UUS_TO_DWT_TIME) >> 8;

  uint8_t resp[RESP_LEN];
  writeHeader(resp, macSeq++, source, me, anchorExchange ? FN_ANCHOR_RESP : FN_RESP, cycle);
  resp[IDX_RESP_FLAGS] = (!anchorExchange && (alertMask >> peerId) & 1) ? FLAG_ALERT : 0;
  dwt_setdelayedtrxtime(respTxTime);
  dwt_setrxaftertxdelay(RX_AFTER_TX_DLY_UUS);
  dwt_setrxtimeout(RX_TIMEOUT_UUS);
  loadTxFrame(resp, RESP_LEN);
  if (dwt_starttx(DWT_START_TX_DELAYED | DWT_RESPONSE_EXPECTED) != DWT_SUCCESS) {
    failExchange();  // too late for the scheduled reply
    return;
  }

  const uint32_t status =
      waitStatus(SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
  if (!(status & SYS_STATUS_RXFCG_BIT_MASK)) {
    failExchange();
    return;
  }
  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK);

  len = readRxFrame(rxBuf, sizeof(rxBuf));
  if (!isFrameFor(rxBuf, len, me, anchorExchange ? FN_ANCHOR_FINAL : FN_FINAL, FINAL_LEN) ||
      get16(rxBuf + IDX_SRC) != source ||
      get16(rxBuf + IDX_CYCLE) != cycle) {
    ++failCount;
    return;
  }

  const uint64_t respTxTs = get_tx_timestamp_u64();
  const uint64_t finalRxTs = get_rx_timestamp_u64();
  uint32_t pollTxTs, respRxTs, finalTxTs;
  final_msg_get_ts(rxBuf + IDX_POLL_TX_TS, &pollTxTs);
  final_msg_get_ts(rxBuf + IDX_RESP_RX_TS, &respRxTs);
  final_msg_get_ts(rxBuf + IDX_FINAL_TX_TS, &finalTxTs);

  // Asymmetric DS-TWR. 32-bit unsigned differences absorb counter wrap.
  const double ra = double(uint32_t(respRxTs - pollTxTs));
  const double rb = double(uint32_t(uint32_t(finalRxTs) - uint32_t(respTxTs)));
  const double da = double(uint32_t(finalTxTs - respRxTs));
  const double db = double(uint32_t(uint32_t(respTxTs) - uint32_t(pollRxTs)));
  const double tofDtu = (ra * rb - da * db) / (ra + rb + da + db);
  const double meters = tofDtu * DWT_TIME_UNITS * SPEED_OF_LIGHT;

  ++okCount;
  Report r = makeReport(anchorExchange ? REPORT_ANCHOR_RANGE : REPORT_RANGE);
  r.tagId = peerId;
  r.cycleSeq = cycle;
  r.rangeMm = int32_t(lround(meters * 1000.0));
  r.flags = anchorExchange ? 0 : rxBuf[IDX_FINAL_FLAGS];
  publish(r);
}

void setup() {
  if (IS_GATEWAY) {
    // Never block the UWB loop on a slow USB host.
    Serial.setTxBufferSize(2048);
  }
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.printf("# FIRE-TAG Anchor %u (%s)\n", ANCHOR_ID, IS_GATEWAY ? "gateway" : "ESP-NOW sender");

  if (initEspNow()) {
    // MAC reads as zeros until Wi-Fi has started, so print it afterwards.
    Serial.printf("# ESP-NOW ready: MAC %s, channel %u\n", WiFi.macAddress().c_str(), ESPNOW_CHANNEL);
  } else {
    Serial.println("# ESP-NOW init failed");
  }
  while (!initRadio()) {
    delay(1000);
  }
  startListening();
}

void loop() {
  const uint32_t status = dwt_read32bitreg(SYS_STATUS_ID);
  if (status & SYS_STATUS_RXFCG_BIT_MASK) {
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK);
    respondIfPoll();
    startListening();
  } else if (status & (SYS_STATUS_ALL_RX_ERR | SYS_STATUS_ALL_RX_TO)) {
    dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_ALL_RX_ERR | SYS_STATUS_ALL_RX_TO);
    startListening();
  }

  if (IS_GATEWAY) {
    Received item;
    while (xQueueReceive(rxQueue, &item, 0) == pdTRUE) {
      printReport(item.report, "espnow", true, item.rssi);
    }
    readPiSerial();
  } else if (cmdQueue) {
    Command c;
    while (xQueueReceive(cmdQueue, &c, 0) == pdTRUE) {
      runCommand(c.cmdId, c.cmd, c.arg);
    }
  }

  if (rangePending) {
    const uint8_t peer = rangePeer;
    const uint16_t id = rangeCmdId;
    rangeWithAnchor(peer, id);
    rangePending = false;
    startListening();  // also runs after timeout, bad response or late TX
  }

  if (millis() - lastHeartbeatMs >= HEARTBEAT_MS) {
    lastHeartbeatMs = millis();
    Report hb = makeReport(REPORT_HEARTBEAT);
    hb.flags = alertMask;  // lets the Pi re-sync the alert after a reboot
    publish(hb);
    if (!IS_GATEWAY) {
      Serial.printf("# anchor=%u ok=%lu fail=%lu espnow_fail=%lu alert_mask=%u\n", ANCHOR_ID,
                    static_cast<unsigned long>(okCount), static_cast<unsigned long>(failCount),
                    static_cast<unsigned long>(espNowFailCount), alertMask);
    }
  }

  if (rebootPending && millis() - rebootRequestedMs >= REBOOT_DELAY_MS) {
    ESP.restart();
  }
}
