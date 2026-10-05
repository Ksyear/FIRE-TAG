"""Run the real anchor sketch with host doubles at the radio/ESP32 boundary."""
import pathlib
import subprocess
import tempfile
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[1]

ARDUINO = r'''
#pragma once
#include <cstdint>
#include <cstddef>
#include <cstring>
#include <cmath>
#include <string>
#include <vector>
#include <deque>
#include <cstdarg>
#include <cstdio>
#include <cassert>
using QueueHandle_t = void *;
constexpr int pdTRUE = 1;
inline void *xQueueCreate(int, size_t) { return reinterpret_cast<void *>(1); }
inline int xQueueSend(void *, const void *, int) { return 1; }
inline int xQueueReceive(void *, void *, int) { return 0; }
inline uint32_t millis() { return 100; }
inline void delay(int) {}
struct SerialFake {
  std::string output;
  void printf(const char *fmt, ...) { char b[1024]; va_list a; va_start(a, fmt);
    vsnprintf(b, sizeof(b), fmt, a); va_end(a); output += b; }
  void println(const char *s) { output += std::string(s) + "\n"; }
  int available() { return 0; }
  int read() { return 0; }
  void setTxBufferSize(int) {}
  void begin(int) {}
} inline Serial;
struct { void restart() {} } inline ESP;
'''

RADIO = r'''
#pragma once
#define SYS_STATUS_ID 0
#define SYS_STATUS_RXFCG_BIT_MASK 1U
#define SYS_STATUS_TXFRS_BIT_MASK 2U
#define SYS_STATUS_ALL_RX_TO 4U
#define SYS_STATUS_ALL_RX_ERR 8U
#define DWT_START_RX_IMMEDIATE 0
#define DWT_START_TX_IMMEDIATE 0
#define DWT_START_TX_DELAYED 1
#define DWT_RESPONSE_EXPECTED 2
#define DWT_SUCCESS 0
#define UUS_TO_DWT_TIME 65536ULL
#define DWT_TIME_UNITS (1.0 / (499200000.0 * 128.0))
#define SPEED_OF_LIGHT 299702547.0
inline uint32_t radioStatus = 0;
inline bool listening = false;
inline std::vector<std::vector<uint8_t>> sentFrames;
inline std::deque<std::vector<uint8_t>> receivedFrames;
inline std::deque<uint32_t> waitEvents;
inline std::deque<int> txResults;
inline void dwt_setrxtimeout(uint32_t) {}
inline void dwt_setpreambledetecttimeout(uint32_t) {}
inline void dwt_setrxaftertxdelay(uint32_t) {}
inline void dwt_setdelayedtrxtime(uint32_t) {}
inline void dwt_rxenable(int) { listening = true; }
inline void dwt_forcetrxoff() { listening = false; }
inline uint32_t dwt_read32bitreg(int) { return radioStatus; }
inline void dwt_write32bitreg(int, uint32_t bits) { radioStatus &= ~bits; }
inline int dwt_starttx(int) {
  listening = false;
  assert(radioStatus == 0);  // stale RX/TX events must be cleared before a new TX
  if (txResults.empty()) return 0;
  int result = txResults.front(); txResults.pop_front(); return result;
}
inline uint64_t get_rx_timestamp_u64() { return receivedFrames.empty() ? 201200 : 1000; }
inline uint64_t get_tx_timestamp_u64() { return 101000; }
inline void final_msg_get_ts(const uint8_t *p, uint32_t *v) { memcpy(v, p, 4); }
inline void final_msg_set_ts(uint8_t *p, uint64_t v) { uint32_t n = v; memcpy(p, &n, 4); }
'''

ESP32 = r'''
#pragma once
#include <Arduino.h>
#define WIFI_STA 0
#define WIFI_IF_STA 0
#define WIFI_PS_NONE 0
#define ESP_OK 0
struct { void mode(int) {} void setChannel(int) {}
  std::string macAddress() { return "00:00:00:00:00:00"; } } inline WiFi;
struct rx_ctrl_t { int8_t rssi; };
struct esp_now_recv_info_t { rx_ctrl_t *rx_ctrl; };
struct esp_now_peer_info_t { uint8_t peer_addr[6]; int channel, ifidx; bool encrypt; };
inline int esp_now_send(const uint8_t *, const uint8_t *, size_t) { return 0; }
inline int esp_now_init() { return 0; }
inline int esp_now_register_recv_cb(void (*)(const esp_now_recv_info_t *, const uint8_t *, int)) { return 0; }
inline int esp_now_add_peer(esp_now_peer_info_t *) { return 0; }
inline void esp_wifi_set_ps(int) {}
'''

TESTS = r'''
namespace firetag {
bool initRadio() { return true; }
void loadTxFrame(uint8_t *frame, size_t len) { sentFrames.emplace_back(frame, frame + len); }
uint32_t waitStatus(uint32_t) {
  assert(!waitEvents.empty()); uint32_t s = waitEvents.front(); waitEvents.pop_front();
  radioStatus = s; return s;
}
size_t readRxFrame(uint8_t *buf, size_t len) {
  assert(!receivedFrames.empty()); auto f = receivedFrames.front(); receivedFrames.pop_front();
  if (f.size() > len) return 0; memcpy(buf, f.data(), f.size()); return f.size();
}
}
std::vector<uint8_t> frame(uint8_t fn, uint16_t src, uint16_t seq, size_t len) {
  std::vector<uint8_t> f(len); writeHeader(f.data(), 0, anchorAddr(0), src, fn, seq); return f;
}
void resetRadio() { sentFrames.clear(); receivedFrames.clear(); waitEvents.clear();
  txResults.clear(); radioStatus = 0; Serial.output.clear(); }
void ack(bool ok) { assert(Serial.output.find(ok ? "\"ok\":true" : "\"ok\":false") != std::string::npos); }
int main() {
  // A valid request is accepted; invalid, same-anchor and concurrent requests are rejected.
  runCommand(123, 4, 1); ack(true);
  Serial.output.clear(); runCommand(124, 4, 2); ack(false);
  resetRadio(); radioStatus = SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK;
  receivedFrames.push_back(frame(0x7f, tagAddr(0), 99, POLL_LEN)); // previously received unrelated frame
  receivedFrames.push_back(frame(0x32, anchorAddr(1), 123, RESP_LEN));
  waitEvents = {SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK, SYS_STATUS_TXFRS_BIT_MASK};
  loop();
  assert(listening && radioStatus == 0);
  assert(sentFrames.size() == 2 && sentFrames[0][IDX_FN] == 0x31 && sentFrames[1][IDX_FN] == 0x33);
  assert(get16(sentFrames[0].data() + IDX_DST) == anchorAddr(1));
  assert(get16(sentFrames[0].data() + IDX_SRC) == anchorAddr(0));
  assert(get16(sentFrames[1].data() + IDX_CYCLE) == 123);
  assert(sentFrames[1][IDX_FINAL_FLAGS] == 0);
  assert(Serial.output.find("anchor_range") == std::string::npos); // initiator does not invent a range
  Serial.output.clear(); runCommand(125, 4, 0); ack(false);
  Serial.output.clear(); runCommand(126, 4, 3); ack(false);
  Serial.output.clear(); handlePiLine("CMD 127 0 range 257"); ack(false);
  Serial.output.clear(); handlePiLine("CMD 128 0 range"); ack(false);

  // An unrelated source cannot advance the initiator to FINAL.
  resetRadio(); runCommand(130, 4, 1);
  receivedFrames.push_back(frame(0x32, anchorAddr(2), 130, RESP_LEN));
  waitEvents = {SYS_STATUS_RXFCG_BIT_MASK}; loop();
  assert(sentFrames.size() == 1 && listening && radioStatus == 0);
  resetRadio(); runCommand(131, 4, 1); waitEvents = {SYS_STATUS_ALL_RX_TO}; loop();
  assert(sentFrames.size() == 1 && listening && radioStatus == 0);
  resetRadio(); runCommand(132, 4, 1); txResults = {-1}; loop();
  assert(listening && radioStatus == 0);

  // The responder alone publishes a range, with the initiating peer and command sequence.
  resetRadio(); receivedFrames.push_back(frame(0x31, anchorAddr(1), 140, POLL_LEN));
  auto fin = frame(0x33, anchorAddr(1), 140, FINAL_LEN);
  final_msg_set_ts(fin.data() + IDX_POLL_TX_TS, 0);
  final_msg_set_ts(fin.data() + IDX_RESP_RX_TS, 100200);
  final_msg_set_ts(fin.data() + IDX_FINAL_TX_TS, 200200);
  fin[IDX_FINAL_FLAGS] = FLAG_ALERT;
  receivedFrames.push_back(fin); waitEvents = {SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK};
  respondIfPoll();
  assert(sentFrames.size() == 1 && sentFrames[0][IDX_FN] == 0x32);
  assert(sentFrames[0][IDX_RESP_FLAGS] == 0);
  assert(Serial.output.find("\"type\":\"anchor_range\",\"anchor\":0,\"peer\":1,\"seq\":140,\"range_mm\":469") != std::string::npos);

  // Tag rescue flags still travel in the existing RESP/FINAL protocol.
  resetRadio(); alertMask = 1;
  receivedFrames.push_back(frame(FN_POLL, tagAddr(0), 150, POLL_LEN));
  fin = frame(FN_FINAL, tagAddr(0), 150, FINAL_LEN);
  final_msg_set_ts(fin.data() + IDX_POLL_TX_TS, 0);
  final_msg_set_ts(fin.data() + IDX_RESP_RX_TS, 100200);
  final_msg_set_ts(fin.data() + IDX_FINAL_TX_TS, 200200);
  fin[IDX_FINAL_FLAGS] = FLAG_ALERT; receivedFrames.push_back(fin);
  waitEvents = {SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK}; respondIfPoll();
  assert(sentFrames[0][IDX_FN] == FN_RESP && sentFrames[0][IDX_RESP_FLAGS] == FLAG_ALERT);
  assert(Serial.output.find("\"tag_alert\":true") != std::string::npos);
  resetRadio(); receivedFrames.push_back(frame(0x31, tagAddr(0), 160, POLL_LEN)); respondIfPoll();
  assert(sentFrames.empty() && Serial.output.empty());
  resetRadio(); receivedFrames.push_back(frame(FN_POLL, anchorAddr(1), 161, POLL_LEN)); respondIfPoll();
  assert(sentFrames.empty() && Serial.output.empty());
  static_assert(sizeof(Report) == 29, "ESP-NOW report wire size changed");
}
'''


class AnchorRangingTest(unittest.TestCase):
    def test_real_sketch_commands_frames_and_recovery(self):
        # Keep the real shared frame parser/builder; double only hardware access.
        shared = (ROOT / "libraries/FireTagUwb/src/FireTagUwb.cpp").read_text()
        frames = shared[shared.index("void writeHeader("):shared.index("bool initRadio()")]
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "Arduino.h").write_text(ARDUINO)
            (tmp / "dw3000.h").write_text(RADIO)
            for name in ("WiFi.h", "esp_now.h", "esp_wifi.h"):
                (tmp / name).write_text(ESP32 if name == "WiFi.h" else '#include "WiFi.h"\n')
            src = '#include "' + str(ROOT / "fire_tag_anchor/fire_tag_anchor.ino") + '"\n'
            src += "namespace firetag {\n" + frames + "}\n" + TESTS
            (tmp / "test.cpp").write_text(src)
            subprocess.run(["c++", "-std=c++17", "-I" + str(tmp),
                            "-I" + str(ROOT / "libraries/FireTagUwb/src"),
                            str(tmp / "test.cpp"), "-o", str(tmp / "test")], check=True)
            subprocess.run([str(tmp / "test")], check=True)


if __name__ == "__main__":
    unittest.main()
