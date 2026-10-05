// FIRE-TAG 요구조자 Tag — LOLIN D32 + DWM3000EVB
//
// DS-TWR initiator. Every CYCLE_MS the tag ranges with Anchor 0, 1, 2 in turn
// (POLL -> RESP -> FINAL). The anchors compute the distance from the FINAL
// frame and forward it to the Raspberry Pi, so the tag needs no Wi-Fi.
// Downlink: RESP carries the Pi's rescue-alert flag; the tag blinks its LED
// and echoes the applied state in FINAL so the Pi can confirm delivery.
//
// Board: "LOLIN D32" (esp32:esp32:d32). Needs libraries DW3000 and FireTagUwb.

#include <FireTagUwb.h>

using namespace firetag;

constexpr uint8_t TAG_ID = 0;
constexpr uint32_t CYCLE_MS = 100;    // 10 Hz; one cycle of 3 exchanges takes ~15 ms
constexpr uint32_t SUMMARY_MS = 1000; // USB debug summary period
constexpr int PIN_LED = 5;            // LOLIN D32 onboard LED (3V3-2k-LED-IO5): LOW = on
constexpr uint32_t BLINK_HALF_MS = 250;

enum Result : uint8_t { EX_OK, EX_NO_RESP, EX_BAD_RESP, EX_LATE, EX_TX_FAIL, EX_RESULT_COUNT };
static const char *const RESULT_NAMES[EX_RESULT_COUNT] = {"OK", "NO_RESP", "BAD_RESP", "LATE", "TX_FAIL"};

static uint8_t macSeq = 0;
static uint16_t cycleSeq = 0;
static uint8_t rxBuf[RX_BUF_LEN];

// Alert state applied by the tag. Updated once per cycle from the RESP flags:
// on if any anchor said on, off if every responding anchor said off, and
// unchanged if no anchor answered (losing the link must not cancel an alert).
static bool alertOn = false;
static bool cycleAlertSeen = false;
static uint8_t cycleRespCount = 0;

static uint16_t okCount[NUM_ANCHORS];
static uint16_t tryCount[NUM_ANCHORS];
static Result lastFail[NUM_ANCHORS];
static uint32_t lastSummaryMs = 0;

static void clearExchangeEvents() {
  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK |
                                       SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
}

// One DS-TWR exchange with one anchor. Same flow as Qorvo ex_05a_ds_twr_init,
// with addressing and a cycle number so the Pi can group the three ranges.
static Result rangeWith(uint8_t anchorId) {
  const uint16_t me = tagAddr(TAG_ID);
  const uint16_t anchor = anchorAddr(anchorId);

  uint8_t poll[POLL_LEN];
  writeHeader(poll, macSeq++, anchor, me, FN_POLL, cycleSeq);
  dwt_setrxaftertxdelay(RX_AFTER_TX_DLY_UUS);
  dwt_setrxtimeout(RX_TIMEOUT_UUS);
  dwt_setpreambledetecttimeout(0);
  loadTxFrame(poll, POLL_LEN);
  if (dwt_starttx(DWT_START_TX_IMMEDIATE | DWT_RESPONSE_EXPECTED) != DWT_SUCCESS) {
    clearExchangeEvents();
    return EX_TX_FAIL;
  }

  const uint32_t status =
      waitStatus(SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_ALL_RX_TO | SYS_STATUS_ALL_RX_ERR);
  if (!(status & SYS_STATUS_RXFCG_BIT_MASK)) {
    clearExchangeEvents();
    return EX_NO_RESP;
  }
  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK);

  const size_t len = readRxFrame(rxBuf, sizeof(rxBuf));
  if (!isFrameFor(rxBuf, len, me, FN_RESP, RESP_LEN) || get16(rxBuf + IDX_SRC) != anchor ||
      get16(rxBuf + IDX_CYCLE) != cycleSeq) {
    return EX_BAD_RESP;
  }
  ++cycleRespCount;
  if (rxBuf[IDX_RESP_FLAGS] & FLAG_ALERT) cycleAlertSeen = true;

  const uint64_t pollTxTs = get_tx_timestamp_u64();
  const uint64_t respRxTs = get_rx_timestamp_u64();
  const uint32_t finalTxTime =
      (respRxTs + uint64_t(REPLY_DLY_UUS) * UUS_TO_DWT_TIME) >> 8;
  // Delayed TX ignores the lowest bit; the antenna delay is added by the chip.
  const uint64_t finalTxTs = (uint64_t(finalTxTime & 0xFFFFFFFEUL) << 8) + ANT_DLY;

  uint8_t fin[FINAL_LEN];
  writeHeader(fin, macSeq++, anchor, me, FN_FINAL, cycleSeq);
  final_msg_set_ts(fin + IDX_POLL_TX_TS, pollTxTs);
  final_msg_set_ts(fin + IDX_RESP_RX_TS, respRxTs);
  final_msg_set_ts(fin + IDX_FINAL_TX_TS, finalTxTs);
  fin[IDX_FINAL_FLAGS] = alertOn ? FLAG_ALERT : 0;
  dwt_setdelayedtrxtime(finalTxTime);
  loadTxFrame(fin, FINAL_LEN);
  if (dwt_starttx(DWT_START_TX_DELAYED) != DWT_SUCCESS) {
    clearExchangeEvents();
    return EX_LATE;  // CPU took longer than REPLY_DLY_UUS
  }
  if (!(waitStatus(SYS_STATUS_TXFRS_BIT_MASK) & SYS_STATUS_TXFRS_BIT_MASK)) {
    clearExchangeEvents();
    return EX_TX_FAIL;
  }
  dwt_write32bitreg(SYS_STATUS_ID, SYS_STATUS_TXFRS_BIT_MASK);
  return EX_OK;
}

static void updateLed() {
  const bool lit = alertOn && (millis() / BLINK_HALF_MS) % 2 == 0;
  digitalWrite(PIN_LED, lit ? LOW : HIGH);
}

static void printSummary() {
  Serial.printf("# tag=%u cycle=%u alert=%s", TAG_ID, cycleSeq, alertOn ? "ON" : "off");
  for (uint8_t a = 0; a < NUM_ANCHORS; ++a) {
    Serial.printf("  A%u %u/%u", a, okCount[a], tryCount[a]);
    if (okCount[a] < tryCount[a]) Serial.printf(" (%s)", RESULT_NAMES[lastFail[a]]);
    okCount[a] = 0;
    tryCount[a] = 0;
  }
  Serial.println();
}

void setup() {
  // GPIO5 is a strapping pin; only drive it after boot, starting with LED off.
  digitalWrite(PIN_LED, HIGH);
  pinMode(PIN_LED, OUTPUT);
  Serial.begin(SERIAL_BAUD);
  delay(200);
  Serial.printf("# FIRE-TAG Tag (DS-TWR initiator) TAG_ID=%u\n", TAG_ID);
  while (!initRadio()) {
    delay(1000);
  }
}

void loop() {
  const uint32_t cycleStart = millis();
  cycleAlertSeen = false;
  cycleRespCount = 0;

  for (uint8_t a = 0; a < NUM_ANCHORS; ++a) {
    const Result r = rangeWith(a);
    ++tryCount[a];
    if (r == EX_OK) {
      ++okCount[a];
    } else {
      lastFail[a] = r;
    }
  }
  ++cycleSeq;
  if (cycleRespCount) alertOn = cycleAlertSeen;

  if (millis() - lastSummaryMs >= SUMMARY_MS) {
    lastSummaryMs = millis();
    printSummary();
  }
  while (millis() - cycleStart < CYCLE_MS) {
    updateLed();
    delay(1);
  }
}
