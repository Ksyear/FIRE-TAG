# 두 Wi-Fi에서 대시보드 사용

설정·확인일: 2026-11-09. Raspberry Pi `smart`에 적용했습니다.

| Wi-Fi | 설정 | 실제 접속 시험 |
| --- | --- | --- |
| Mobile_504 | 기존 설정 유지 | Pi 연결과 Mac에서 HTTP 접속 확인 |
| Hanbat_506 | 추가 등록, 실행 중인 Wi-Fi 관리기에 반영 | 사용자 요청으로 나중에 진행 |

Pi는 두 네트워크를 저장하고 사용 가능한 네트워크에 접속합니다. Wi-Fi 한 인터페이스로 두 공유기에 동시에 접속한다는 의미는 아닙니다. 네트워크마다 DHCP로 받은 IP가 달라질 수 있습니다.

- 기존 설정: `/etc/netplan/50-cloud-init.yaml`
- 추가 설정: `/etc/netplan/90-fire-tag-client.yaml` — Pi에서만 저장, root 전용 권한 `600`
- `netplan generate` 검사 통과, `wpa_cli list_networks`에서 두 SSID 등록 확인
- 현재 연결: `Mobile_504`, Pi IP `192.168.68.102`

비밀번호는 저장소·PR·발표 자료에 포함하지 않습니다. ESP32에는 공유기 접속 기능을 추가하지 않았습니다. 앵커 간 ESP-NOW, Tag와 앵커 간 UWB 통신은 Pi의 Wi-Fi와 별개입니다.

## 접속 주소

Pi에서 `hostname -I`로 IP를 확인한 뒤, 같은 Wi-Fi의 기기에서 접속합니다.

- 경량 화면: `http://<Pi IP>:8080/lite` 또는 기본 주소 `/`
- 기존 화면: `http://<Pi IP>:8080/full`

실행: Pi에서 `cd ~/fire-tag && ./run_dev.sh start`.
상태 확인: `./run_dev.sh status`. 현재 시험 실행은 수동 방식이며 부팅 자동 실행 서비스를 새로 등록하지 않았습니다.

## Hanbat_506 현장 확인

1. Pi와 접속 기기를 Hanbat_506에 연결합니다.
2. Pi의 새 IP를 확인하고 `/lite`, `/full`, `/api/state`에 접속합니다.
3. SSID 등록만으로 다른 기기 간 접속까지 검증된 것은 아닙니다. 공유기의 기기 간 통신 제한 여부도 실제 접속으로 확인합니다.
4. 위치 시험 전에는 세 앵커의 배치와 상호 거리를 다시 확인합니다.

설정 형식 근거: [Netplan Wi-Fi access-points 문서](https://netplan.readthedocs.io/en/latest/netplan-yaml/).
