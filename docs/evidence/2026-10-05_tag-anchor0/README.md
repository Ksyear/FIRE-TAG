# 요구조자 Tag ↔ Anchor 0 실기 통신 기록 (2026-10-05)

![Tag와 Anchor 0 실기 통신 기록](evidence.png)

## 무엇을 확인했나

| 확인 항목 | 방향 | 결과 |
|---|---|---|
| UWB 거리측정 | Tag → Anchor 0 | 30초 동안 292회(초당 10.0회), 깨진 줄 0, 사이클 번호 누락 0 |
| 거리값 (보정 전) | Anchor 0 계산 | 평균 234 mm, 중앙값 232 mm, 표준편차 29 mm, 범위 124~335 mm |
| Tag 쪽 성공률 | Tag 1초 요약 | 부팅 직후 1초를 빼고 매초 A0 10/10 |
| 경보 켜기 명령 | Mac → Anchor 0 → Tag | +10.013초 전송, +10.024초 Anchor 0 ACK, +10.161초 Tag 회신(`tag_alert:true`) → 148 ms |
| 경보 끄기 명령 | Mac → Anchor 0 → Tag | +20.014초 전송, +20.025초 ACK, +20.162초 Tag 회신(`tag_alert:false`) → 148 ms |
| 경보 유지 | Tag → Anchor 0 | 켜진 10초 동안 거리 보고 100회 모두 `tag_alert:true` |

경보 회신은 Tag가 FINAL 프레임에 "실제로 적용한 경보 상태"를 실어 보낸 값입니다. 따라서 명령이 앵커에서 Tag까지 무선으로 갔다가 다시 돌아온 것을 보여줍니다.

## 확인하지 않은 것

- **위치(x, y)**: 2D 위치는 앵커 3대의 거리가 필요합니다. 이 기록에서는 Anchor 0 한 대만 켜져 있었습니다.
- **실제 거리와의 오차**: 두 보드 사이 실제 거리를 줄자로 재지 않았습니다. 234 mm는 안테나 지연 보정 전 값입니다.
- **Anchor 1·2, ESP-NOW, Raspberry Pi**: 이 기록의 범위가 아닙니다.

## 기록 방법

- 장비: 요구조자 Tag = LOLIN D32 (MAC `B0:CB:D8:EB:94:EC`, `/dev/cu.usbserial-140`), Anchor 0 = ESP32 DevKitC (MAC `0C:B8:15:A6:25:A8`, `/dev/cu.usbserial-0001`). 둘 다 DWM3000EVB, 펌웨어는 PR #1의 커밋.
- Mac에서 두 시리얼 포트(115200 bps)를 동시에 열고, 두 보드를 RTS로 리셋한 뒤 30초 동안 받은 줄마다 Mac 시각과 경과 시간을 붙여 저장했습니다.
- 10초와 20초에 Anchor 0으로 `CMD 101 0 alert 1`, `CMD 102 0 alert 0`을 보냈습니다(`commands.log`).
- `evidence.png`의 그래프와 로그 발췌는 아래 원본 로그에서 그대로 그렸습니다.

| 파일 | 내용 |
|---|---|
| `tag.log` | Tag 시리얼 전체 (부팅, 1초 요약) |
| `anchor0.log` | Anchor 0 시리얼 전체 (부팅, 거리 JSON, ACK, 상태 보고) |
| `commands.log` | Mac이 Anchor 0으로 보낸 명령과 시각 |
| `evidence.png` | 위 기록을 한 장으로 정리한 캡처 |
