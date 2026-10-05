#include <Arduino.h>
#include <SPI.h>

// Same wiring for ESP32 DevKitC and LOLIN D32.
constexpr int PIN_SCK = 18;
constexpr int PIN_MISO = 19;
constexpr int PIN_MOSI = 23;
constexpr int PIN_CS = 27;
constexpr int PIN_RST = 26;
constexpr int PIN_IRQ = 34;
constexpr uint32_t SERIAL_BAUD = 9600;
constexpr uint32_t EXPECTED_ID = 0xDECA0302;

void resetUwb() {
  // RSTn must only be pulled LOW, then released. Never drive it HIGH.
  pinMode(PIN_RST, OUTPUT_OPEN_DRAIN);
  digitalWrite(PIN_RST, LOW);
  delay(2);
  pinMode(PIN_RST, INPUT);
  delay(20);
}

uint32_t readDeviceId(uint8_t bytes[4]) {
  SPI.beginTransaction(SPISettings(1000000, MSBFIRST, SPI_MODE0));
  digitalWrite(PIN_CS, LOW);
  delayMicroseconds(2);

  SPI.transfer(0x00);  // Short read header: register 0x00, offset 0.
  for (int i = 0; i < 4; ++i) {
    bytes[i] = SPI.transfer(0x00);
  }

  delayMicroseconds(2);
  digitalWrite(PIN_CS, HIGH);
  SPI.endTransaction();

  // The lowest addressed byte is returned first.
  return uint32_t(bytes[0]) | (uint32_t(bytes[1]) << 8) |
         (uint32_t(bytes[2]) << 16) | (uint32_t(bytes[3]) << 24);
}

void setup() {
  Serial.begin(SERIAL_BAUD);
  pinMode(PIN_RST, INPUT);
  pinMode(PIN_IRQ, INPUT);
  pinMode(PIN_CS, OUTPUT);
  digitalWrite(PIN_CS, HIGH);
  SPI.begin(PIN_SCK, PIN_MISO, PIN_MOSI, PIN_CS);
  delay(500);
  resetUwb();

  Serial.println("FIRE-TAG DWM3000EVB SPI test");
  Serial.println("SCK=18 MISO=19 MOSI=23 CS=27 RST=26 IRQ=34");
  Serial.println("Expected DEV_ID=0xDECA0302; this test does not measure distance.");
}

void loop() {
  uint8_t bytes[4];
  const uint32_t id = readDeviceId(bytes);
  Serial.printf("RAW=%02X %02X %02X %02X  DEV_ID=0x%08lX  ",
                unsigned(bytes[0]), unsigned(bytes[1]),
                unsigned(bytes[2]), unsigned(bytes[3]),
                static_cast<unsigned long>(id));

  if (id == EXPECTED_ID) {
    Serial.println("PASS: device ID matches.");
  } else if (id == 0 || id == 0xFFFFFFFF) {
    Serial.println("FAIL: no valid SPI reply. Check power, J1 and SPI wiring.");
  } else {
    Serial.println("FAIL: unexpected ID. Report the complete RAW and DEV_ID line.");
  }
  delay(1000);
}
