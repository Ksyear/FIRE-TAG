"""Exercise the actual sketches and shared recovery policy with radio boundary doubles."""
import pathlib
import subprocess
import tempfile
import unittest

from test_anchor_ranging import ARDUINO, RADIO, ESP32, ROOT


HARDWARE = r'''
inline unsigned initCalls = 0;
inline bool initOk = true;
namespace firetag {
bool initRadio() { ++initCalls; return initOk; }
void loadTxFrame(uint8_t *frame, size_t len) { sentFrames.emplace_back(frame, frame + len); }
uint32_t waitStatus(uint32_t) {
  const uint32_t status = waitEvents.empty() ? SYS_STATUS_ALL_RX_TO : waitEvents.front();
  if (!waitEvents.empty()) waitEvents.pop_front();
  radioStatus = status; return status;
}
size_t readRxFrame(uint8_t *buf, size_t len) {
  assert(!receivedFrames.empty()); auto frame = receivedFrames.front(); receivedFrames.pop_front();
  if (frame.size() > len) return 0;
  memcpy(buf, frame.data(), frame.size()); return frame.size();
}
}
'''

ANCHOR_TEST = r'''
int main() {
  alertMask = 5;
  fakeMillis = 1999; loop();
  assert(initCalls == 0 && !listening);
  fakeMillis = 2000; loop();
  assert(listening && initCalls == 0);  // silence first rearms RX without resetting
  assert(Serial.output.find("DEV_ID=0xDECA0302") != std::string::npos);
  assert(Serial.output.find("SYS_STATUS=") != std::string::npos);
  assert(Serial.output.find("SYS_STATE=") != std::string::npos);
  fakeMillis = 9999; loop(); assert(initCalls == 0);
  fakeMillis = 10000; loop(); assert(initCalls == 1 && listening);
  assert(alertMask == 5 && okCount == 0);  // configuring a radio is not a successful range
  fakeMillis = 19999; loop(); assert(initCalls == 1);
  initOk = false;
  fakeMillis = 20000; loop(); assert(initCalls == 2 && !listening);
  assert(alertMask == 5 && okCount == 0);
  assert(Serial.output.find("ready=false") != std::string::npos);
  // A failed init must leave control/heartbeat processing available, without using UWB.
  radioStatus = SYS_STATUS_RXFCG_BIT_MASK;
  fakeMillis = 21000; loop(); assert(initCalls == 2);
  assert(Serial.output.find("\"type\":\"status\"") != std::string::npos);
  radioStatus = 0; initOk = true;
  fakeMillis = 30000; loop(); assert(initCalls == 3 && listening);
  for (int i = 1; i <= 150; ++i) {
    fakeMillis = 30000 + i * 100;
    std::vector<uint8_t> poll(POLL_LEN), final(FINAL_LEN);
    writeHeader(poll.data(), 0, anchorAddr(0), tagAddr(0), FN_POLL, i);
    writeHeader(final.data(), 1, anchorAddr(0), tagAddr(0), FN_FINAL, i);
    final_msg_set_ts(final.data() + IDX_POLL_TX_TS, 0);
    final_msg_set_ts(final.data() + IDX_RESP_RX_TS, 100200);
    final_msg_set_ts(final.data() + IDX_FINAL_TX_TS, 200200);
    receivedFrames.push_back(poll); receivedFrames.push_back(final);
    radioStatus = SYS_STATUS_RXFCG_BIT_MASK;
    waitEvents.push_back(SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK);
    loop();
  }
  assert(initCalls == 3 && okCount == 150 && alertMask == 5 && listening);
}
'''

TAG_TEST = r'''
void noResponseCycle() { loop(); }
void successfulCycle() {
  for (uint8_t a = 0; a < 3; ++a) {
    std::vector<uint8_t> response(RESP_LEN);
    writeHeader(response.data(), 0, tagAddr(TAG_ID), anchorAddr(a), FN_RESP, cycleSeq);
    receivedFrames.push_back(response);
    waitEvents.push_back(SYS_STATUS_RXFCG_BIT_MASK | SYS_STATUS_TXFRS_BIT_MASK);
    waitEvents.push_back(SYS_STATUS_TXFRS_BIT_MASK);
  }
  loop();
}
int main() {
  alertOn = true;
  // A stale event must not escape the previous failed exchange into the next TX.
  radioStatus = SYS_STATUS_TXFRS_BIT_MASK | SYS_STATUS_ALL_RX_ERR;
  noResponseCycle();
  assert(alertOn && initCalls == 0);
  fakeMillis = 2000; noResponseCycle(); assert(initCalls == 0 && alertOn);
  assert(Serial.output.find("last_status=0x00000004") != std::string::npos);
  assert(Serial.output.find("last_state=") != std::string::npos);
  fakeMillis = 10000; noResponseCycle(); assert(initCalls == 1 && alertOn);
  fakeMillis = 19900; noResponseCycle(); assert(initCalls == 1 && alertOn);
  initOk = false;
  fakeMillis = 20000; noResponseCycle(); assert(initCalls == 2 && alertOn);
  const auto sent = sentFrames.size();
  fakeMillis = 20100; noResponseCycle(); assert(sentFrames.size() == sent && alertOn);
  initOk = true;
  fakeMillis = 30000; noResponseCycle(); assert(initCalls == 3 && alertOn);
  // Real responses resume ranging and can clear the retained alert.
  fakeMillis = 30100; successfulCycle(); assert(!alertOn);
  for (int i = 0; i < 150; ++i) successfulCycle();
  assert(initCalls == 3);  // continuous successful exchanges must not cause resets
  fakeMillis = UINT32_MAX - 50; successfulCycle(); successfulCycle();
  assert(initCalls == 3);  // millis wrap must not look like a long outage
  static_assert(sizeof(Report) == 29, "ESP-NOW report wire size changed");
}
'''


class RadioRecoveryTest(unittest.TestCase):
    def compile_and_run(self, role, checks, defines=()):
        shared = (ROOT / "libraries/FireTagUwb/src/FireTagUwb.cpp").read_text()
        # Real frame handling and recovery code, only the physical radio init/I/O is doubled.
        shared = shared[shared.index("void writeHeader("):shared.index("bool initRadio()")]
        arduino = ARDUINO.replace("inline uint32_t millis() { return 100; }", "inline uint32_t fakeMillis = 0;\ninline uint32_t millis() { return fakeMillis; }")
        arduino = arduino.replace("inline void delay(int) {}", "inline void delay(int ms) { fakeMillis += ms; }\n#define LOW 0\n#define HIGH 1\n#define OUTPUT 1\ninline void digitalWrite(int, int) {}\ninline void pinMode(int, int) {}")
        arduino = arduino.replace("void println(const char *s)", 'void println(const char *s = "")')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            (tmp / "Arduino.h").write_text(arduino)
            (tmp / "dw3000.h").write_text(RADIO)
            for name in ("WiFi.h", "esp_now.h", "esp_wifi.h"):
                (tmp / name).write_text(ESP32 if name == "WiFi.h" else '#include "WiFi.h"\n')
            src = '#include "' + str(ROOT / f"fire_tag_{role}/fire_tag_{role}.ino") + '"\n'
            src += "namespace firetag {\n" + shared + "}\n" + HARDWARE + checks
            (tmp / "test.cpp").write_text(src)
            subprocess.run(["c++", "-std=c++17", *defines, "-I" + str(tmp),
                            "-I" + str(ROOT / "libraries/FireTagUwb/src"),
                            str(tmp / "test.cpp"), "-o", str(tmp / "test")], check=True)
            subprocess.run([str(tmp / "test")], check=True)

    def test_anchor_recovers_silent_receiver_without_losing_alerts(self):
        self.compile_and_run("anchor", ANCHOR_TEST)

    def test_tag_clears_stale_events_and_retains_alert_during_recovery(self):
        self.compile_and_run("tag", TAG_TEST)

    def test_build_tag_id_sets_its_wire_address(self):
        self.compile_and_run("tag", r'''int main() {
          rangeWith(0);
          assert(get16(sentFrames[0].data() + IDX_SRC) == 0x5403);
        }''', defines=("-DTAG_ID=3",))


if __name__ == "__main__":
    unittest.main()
