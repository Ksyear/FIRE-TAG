# FIRE-TAG 피요구조자 위치추적 — 발표용 최소 부품 목록

---

# 최종 구매 부품

| 구분 | 제품 | 수량 | 사용하는 이유 | 개당 가격 | 소계 | 디바이스마트 제품 페이지 |
|---|---|---:|---|---:|---:|---|
| UWB | **Qorvo DWM3000EVB** | **4개** | Anchor 3개 + 피요구조자 Tag 1개에 각각 1개 사용. UWB Two-Way Ranging으로 거리를 측정. DWM3000이 보드에 이미 실장되어 있어 RF 모듈 납땜이 필요 없음 | 57,101원 | 228,404원 | https://m.devicemart.co.kr/goods/view/15532654 |
| Anchor MCU | **ESP32 DevKitC WROOM-32D V4 CP2102 [CMODULE-40]** | **3개** | Anchor 0·1·2의 DWM3000EVB 제어 및 ranging responder 역할 | 8,800원 | 26,400원 | https://m.devicemart.co.kr/goods/view/15313999 |
| Tag MCU | **[정품] LOLIN D32 V1.0.0 ESP-32** | **1개** | 피요구조자 Tag 제어. DWM3000EVB와 SPI 통신. 3.7V LiPo 연결 및 충전을 한 보드에서 처리해 별도 충전 모듈을 제거 | 14,300원 | 14,300원 | https://m.devicemart.co.kr/goods/view/1361841 |
| Tag 배터리 | **DTP652533 3.7V 500mAh KC인증 Li-Po** | **1개** | 피요구조자가 이동하는 동안 Tag에 전원 공급 | 4,620원 | 4,620원 | https://m.devicemart.co.kr/goods/view/15337888 |
| Anchor USB 케이블 | **USB A(M) / Micro USB(B) 1m [C3886]** | **3개** | Anchor 0·1·2의 ESP32 전원. 펌웨어 업로드에도 재사용 | 2,750원 | 8,250원 | https://m.devicemart.co.kr/goods/view/1061716 |
| Anchor 전원 | **5V 2A 2Port 충전기 [SR2172]** | **1개** | Anchor 1·2 전원 공급. Anchor 0은 Raspberry Pi USB에서 전원 공급하므로 2포트 충전기 1개만 필요 | 4,400원 | 4,400원 | https://m.devicemart.co.kr/goods/view/1384855 |

## 신규 구매 합계

```text
DWM3000EVB ×4            228,404원
ESP32 DevKitC ×3           26,400원
LOLIN D32 ×1               14,300원
500mAh LiPo ×1               4,620원
Micro USB 케이블 ×3          8,250원
2Port 5V 충전기 ×1           4,400원
--------------------------------
총                         286,374원
```

**총 약 28.6만 원**입니다.

---
