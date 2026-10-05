# Anchor Ranging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Tag를 움직여 앵커 위치를 추정하지 않고, 앵커 세 쌍의 UWB 거리로 Pi 좌표를 설정합니다.

**Architecture:** Pi가 한 쌍씩 측정 명령을 전송합니다. 앵커의 별도 DS-TWR 프레임으로 측정하고 Anchor 0이 ESP-NOW 보고를 USB로 전달합니다. Pi는 측정 산포와 삼각형을 검사한 뒤 좌표를 저장합니다.

**Tech Stack:** ESP32 Arduino, DW3000, ESP-NOW, Python 표준 라이브러리.

**Spec:** `docs/superpowers/specs/2026-10-05-anchor-ranging-design.md`

## Global Constraints

- Tag 프레임과 경보 동작 유지, 새 런타임 의존성 없음.
- 프레임 함수 `0x31/0x32/0x33`, Report type 4, CMD range=4.
- 세 쌍 각각 최소 20개, 삼각형 높이 최소 0.2 m.
- 실기와 시뮬레이션 검증 범위를 명시. 비밀번호를 파일·문서에 기록하지 않음.

## Task 1: Firmware

Files: `firmware/fire_tag_anchor/fire_tag_anchor.ino`, `firmware/libraries/FireTagUwb/src/FireTagUwb.h`.

- [x] range 명령 접수와 단일 진행 상태 추가.
- [x] 앵커 주소 및 별도 프레임으로 DS-TWR 요청·응답 구현.
- [x] type 4 보고와 anchor_range JSON 추가.
- [x] Tag와 앵커 0/1/2 컴파일, 코드 검토.

## Task 2: Pi calibration and startup

Files: `raspberrypi/anchor_pair_calibration.py`, `fire_tag_receiver.py`, `config.json`, `run_dev.sh`, `tests/`.

- [x] 시작 실패 회귀 테스트를 먼저 실패시킨 뒤 두 프로세스 확인 구현.
- [x] 세 변·노이즈·누락·높이 차이 테스트를 먼저 실행.
- [x] 중앙값 거리에서 좌표 생성 및 검증, 단일 명령 순환과 수신 처리 구현.
- [x] 명시적 gateway serial_port 설정 지원.
- [x] Python 테스트와 셸 문법 검사.

## Task 3: Hardware, evidence, PR

- [x] Pi USB 각 포트에서 앵커 번호를 확인.
- [x] 공식 패키지 esptool 준비, 컴파일된 펌웨어를 대상 보드에 업로드하고 검증.
- [x] Pi 코드 배포, 세 쌍 측정 및 전체 점검·좌표 갱신 확인.
- [x] 실제 대시보드 영상, 원본 기록, 보고서를 로컬에 저장.
- [x] 코드 검토, 검증 후 GitHub PR 생성. 미완료 실기 항목은 사실대로 기록. (PR #5)
