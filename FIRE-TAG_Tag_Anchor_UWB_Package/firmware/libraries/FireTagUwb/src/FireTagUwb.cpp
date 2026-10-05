#include "FireTagUwb.h"

#include <SPI.h>

// Defined in the DW3000 library (dw3000_port.cpp / dw3000_config_options.cpp).
extern SPISettings _fastSPI;
extern dwt_txconfig_t txconfig_options_ch9;

namespace firetag {

// Channel 9 (7.99 GHz): inside the Korean UWB band in both the older
// (7.2-10.2 GHz) and newer (6.0-8.8 GHz) rules. Channel 5 (6.5 GHz) is not
// covered by the older rule. Every node must use exactly these values.
static dwt_config_t uwbConfig = {
    9,                 // channel
    DWT_PLEN_128,      // preamble length (TX)
    DWT_PAC8,          // preamble acquisition chunk (RX)
    9,                 // TX preamble code (PRF 64 MHz)
    9,                 // RX preamble code
    1,                 // SFD type: DW 8-symbol
    DWT_BR_6M8,        // data rate
    DWT_PHRMODE_STD,   // PHY header mode
    DWT_PHRRATE_STD,   // PHY header rate
    (129 + 8 - 8),     // SFD timeout
    DWT_STS_MODE_OFF,  // no STS
    DWT_STS_LEN_64,
    DWT_PDOA_M0,
};

void writeHeader(uint8_t *frame, uint8_t macSeq, uint16_t dst, uint16_t src,
                 uint8_t fn, uint16_t cycleSeq) {
  frame[0] = 0x41;
  frame[1] = 0x88;
  frame[IDX_SEQ] = macSeq;
  put16(frame + 3, PAN_ID);
  put16(frame + IDX_DST, dst);
  put16(frame + IDX_SRC, src);
  frame[IDX_FN] = fn;
  put16(frame + IDX_CYCLE, cycleSeq);
}

bool isFrameFor(const uint8_t *frame, size_t len, uint16_t myAddr,
                uint8_t fn, size_t minLen) {
  return len >= minLen && frame[0] == 0x41 && frame[1] == 0x88 &&
         get16(frame + 3) == PAN_ID && get16(frame + IDX_DST) == myAddr &&
         frame[IDX_FN] == fn;
}

bool initRadio() {
  // Fix the SPI pins first; the library's own SPI.begin() is then a no-op.
  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI);
  _fastSPI = SPISettings(UWB_SPI_HZ, MSBFIRST, SPI_MODE0);

  // Same bring-up order as the library's ESP32 examples.
  spiBegin(PIN_IRQ, PIN_RST);
  spiSelect(PIN_CS);
  delay(2);
  dwt_softreset();
  delay(2);

  if (!dwt_checkidlerc()) {
    Serial.println("# UWB init failed: chip not in IDLE_RC (check 3V3, RST, SPI wiring)");
    return false;
  }
  if (dwt_initialise(DWT_DW_INIT) == DWT_ERROR) {
    Serial.printf("# UWB init failed: dwt_initialise (DEV_ID=0x%08lX)\n",
                  static_cast<unsigned long>(dwt_readdevid()));
    return false;
  }
  if (dwt_configure(&uwbConfig)) {
    Serial.println("# UWB init failed: PLL or RX calibration (dwt_configure)");
    return false;
  }

  dwt_configuretxrf(&txconfig_options_ch9);
  dwt_setrxantennadelay(ANT_DLY);
  dwt_settxantennadelay(ANT_DLY);
  dwt_setlnapamode(DWT_LNA_ENABLE | DWT_PA_ENABLE);
  // TX/RX activity LEDs on the DWM3000EVB help when debugging placement.
  dwt_setleds(DWT_LEDS_ENABLE | DWT_LEDS_INIT_BLINK);

  Serial.printf("# UWB ready: DEV_ID=0x%08lX channel=%u\n",
                static_cast<unsigned long>(dwt_readdevid()), uwbConfig.chan);
  return true;
}

void loadTxFrame(uint8_t *frame, size_t len) {
  dwt_writetxdata(len, frame, 0);
  dwt_writetxfctrl(len + FCS_LEN, 0, 1);  // length includes FCS; ranging bit set
}

uint32_t waitStatus(uint32_t mask) {
  const uint32_t start = millis();
  uint32_t status;
  while (!((status = dwt_read32bitreg(SYS_STATUS_ID)) & mask)) {
    if (millis() - start > SW_GUARD_MS) {
      dwt_forcetrxoff();
      return 0;
    }
  }
  return status;
}

size_t readRxFrame(uint8_t *buf, size_t bufLen) {
  const uint32_t frameLen = dwt_read32bitreg(RX_FINFO_ID) & RXFLEN_MASK;  // includes FCS
  if (frameLen < FCS_LEN || frameLen - FCS_LEN > bufLen) return 0;
  dwt_readrxdata(buf, frameLen - FCS_LEN, 0);
  return frameLen - FCS_LEN;
}

}  // namespace firetag
