# FIRE-TAG 11월 16일 — 학습용 손그림 인포그래픽 프롬프트

- 원본 자료: 11/16 발표 자료의 기존 생성 이미지 7장
- 학습 주제: Pi·ESP32·UWB 통신 구조와 당김식 전원 구상
- 강조색: 하늘색, 선 `#2799E6` / 옅은 채움 `#E9F5FD`
- 공통 스타일: `양식/학습용_손그림_인포그래픽_공통지침.md` 적용
- 생성 방식: 내장 image_gen, 기존 로컬 이미지 편집(style-transfer)
- 실제 UI 캡처는 생성·편집 대상에서 제외하고 원본 그대로 이동
- 기구·배치 그림은 설명용이며 실제 측정 배치도·실물 제작 결과가 아님

## 1. 실내 장치 구성 (권장)

- 결과 파일: [01_실내_전체구성.png](01_실내_전체구성.png)
- 삽입 위치: 전체 구성 소개
- 학습 목표: UWB 거리값이 A0를 거쳐 Pi로 전달되는 전체 구조
- 도해 유형: 공간·관계형
- 편집 원본: `발표자료/11/16/경량버전/images/실내_구성도.png` (이전 버전은 Git 이력에 보존)

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Edit the supplied target illustration: preserve its technical meaning and relative device positions, but completely redraw it as a clean HAND-DRAWN Korean educational infographic, NOT a render.
16:9 landscape. Flat warm ivory background (#FFF9ED), generous whitespace. Bold rounded BLACK handwritten Korean title top center (top 15%). Thin slightly irregular BLACK pen outlines and legible handwritten black labels. Simple board sketches, only a few chips/ports; NO logos, real PCB detail, shadows, gradients, gloss, photos, 3D or textured paper. Only accent is sky blue #2799E6 with pale fill #E9F5FD. No orange, red, green, yellow, navy or second accent. Use blue ONLY on the active path, selected elements and the bottom conclusion. Main drawing middle 65%, one pale-blue hand-drawn conclusion box bottom center. All text large, no overlap, no fake UI or invented measurements. Render only the exact text quoted below.

Learning objective: UWB 거리값이 A0를 거쳐 Pi로 전달되는 전체 구조.
Keep the target's room placement as a very simple light black-pen indoor sketch: rear-center table, Raspberry Pi on its left, A0 ESP32+small UWB module on its right, A1 at left foreground, A2 at right foreground, Tag centered in front. No wall/window/door detail needed. Preserve clearly separated Pi and A0. These are illustrative positions, never a scaled floor plan. Each ESP32 has a tiny adjacent UWB module, represented as simple flat pen rectangles.
Show USB cable Pi↔A0 as a black solid cable. UWB links are thin BLACK solid double-headed arrows between Tag and EACH of A0/A1/A2, never Pi. Two sky-BLUE dashed one-way ESP-NOW arrows run A1→A0 and A2→A0, ending on A0 board, not Pi. Keep links separated so arrowhead meaning is clear. One label per protocol as a small plain legend, no box clutter. Device labels near their boards. Main message is converging reports at A0. Bottom conclusion quoted below. Small provenance line below the conclusion.

Exact rendered text, no other text:
"실내 장치 구성"
"Raspberry Pi"
"A0 · ESP32"
"A1 · ESP32"
"A2 · ESP32"
"Tag · LOLIN D32"
"USB"
"UWB"
"ESP-NOW"
"Tag 거리값을 A0에 모아 Pi로 전달"
"구성 예시 · 실측 배치도 아님"

Use the title as top centered heading and the stated conclusion at bottom. Korean spelling, correct signal direction and contact state matter most.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "실내 장치 구성"
- [x] "Raspberry Pi"
- [x] "A0 · ESP32"
- [x] "A1 · ESP32"
- [x] "A2 · ESP32"
- [x] "Tag · LOLIN D32"
- [x] "USB"
- [x] "UWB"
- [x] "ESP-NOW"
- [x] "Tag 거리값을 A0에 모아 Pi로 전달"
- [x] "구성 예시 · 실측 배치도 아님"

### 내용 검수 포인트

- Tag↔앵커 UWB는 양방향. A1/A2→A0 ESP-NOW는 단방향 보고. Pi–A0만 USB 연결.

### 전체 구성도 화살표 보정 프롬프트

초안에서 화살표가 탁자 아래에 모여 보이는 문제를 수정했습니다. 장치 상대 위치를 유지하며 탁자를 제거하고 각 경로의 끝이 A0 보드에 닿도록 편집했습니다.

```text
Edit this hand-drawn overview only to correct the endpoint positions of the communication arrows.
Keep ALL exact rendered text, ivory/black/sky-blue-only hand-drawn style and relative device positions unchanged. REMOVE THE TABLE entirely to make the endpoints unmistakable. The Pi and A0 sketches stay at the rear/top row; A1 left, A2 right, Tag lower center. No new text.
The two BLUE DASHED ESP-NOW arrows must start at A1 and A2 boards and visibly TOUCH the actual A0 ESP32 board outline, at two separate points on its lower-left/lower-right edges. The A0 board is the right board next to Raspberry Pi at top, NOT the central USB cable. Do not let these arrows stop in empty space or at Pi.
The three BLACK solid double-headed UWB arrows must visibly TOUCH Tag board and EACH actual anchor board (A0,A1,A2), especially the top UWB endpoint must terminate at A0 board, not at USB cable or blank space. Route this Tag↔A0 line as a gentle curve to the right of center, ending on A0, so it does not pass through any words. ESP-NOW and UWB labels must be placed beside their respective paths, not obscure connections. Keep ample whitespace. No table, no card background, no box around all devices. Bottom conclusion and small disclaimer unchanged.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

## 2. 1. Pi와 A0 연결 (보조)

- 결과 파일: [02_Pi_A0_USB_연결.png](02_Pi_A0_USB_연결.png)
- 삽입 위치: 단계별 설명 1
- 학습 목표: Pi와 A0의 유선 연결만 설명
- 도해 유형: 공간·구조형
- 편집 원본: `발표자료/11/16/경량버전/images/단계별/01_Pi_A0_USB_연결.png` (이전 버전은 Git 이력에 보존)

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Edit the supplied target illustration: preserve its technical meaning and relative device positions, but completely redraw it as a clean HAND-DRAWN Korean educational infographic, NOT a render.
16:9 landscape. Flat warm ivory background (#FFF9ED), generous whitespace. Bold rounded BLACK handwritten Korean title top center (top 15%). Thin slightly irregular BLACK pen outlines and legible handwritten black labels. Simple board sketches, only a few chips/ports; NO logos, real PCB detail, shadows, gradients, gloss, photos, 3D or textured paper. Only accent is sky blue #2799E6 with pale fill #E9F5FD. No orange, red, green, yellow, navy or second accent. Use blue ONLY on the active path, selected elements and the bottom conclusion. Main drawing middle 65%, one pale-blue hand-drawn conclusion box bottom center. All text large, no overlap, no fake UI or invented measurements. Render only the exact text quoted below.

Learning objective: Pi와 A0의 유선 연결만 설명.
Keep the target's room placement as a very simple light black-pen indoor sketch: rear-center table, Raspberry Pi on its left, A0 ESP32+small UWB module on its right, A1 at left foreground, A2 at right foreground, Tag centered in front. No wall/window/door detail needed. Preserve clearly separated Pi and A0. These are illustrative positions, never a scaled floor plan. Each ESP32 has a tiny adjacent UWB module, represented as simple flat pen rectangles.
Only Pi and A0 are active bold black sketches, joined by a prominent sky-blue USB cable. The other three devices remain in their positions as pale-gray simple pen outlines, labels readable black. NO radio arrows, radio labels, Wi-Fi or extra devices. The active USB cable is physical, not a radio ray. Conclusion in pale-blue bottom box; provenance below.

Exact rendered text, no other text:
"1. Pi와 A0 연결"
"Raspberry Pi"
"A0 · ESP32"
"A1 · ESP32"
"A2 · ESP32"
"Tag · LOLIN D32"
"USB"
"Pi ↔ A0 · USB 시리얼"
"구성 예시 · 실측 배치도 아님"

Use the title as top centered heading and the stated conclusion at bottom. Korean spelling, correct signal direction and contact state matter most.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "1. Pi와 A0 연결"
- [x] "Raspberry Pi"
- [x] "A0 · ESP32"
- [x] "A1 · ESP32"
- [x] "A2 · ESP32"
- [x] "Tag · LOLIN D32"
- [x] "USB"
- [x] "Pi ↔ A0 · USB 시리얼"
- [x] "구성 예시 · 실측 배치도 아님"

### 내용 검수 포인트

- Pi와 A0 사이 USB만 강조. Pi에 UWB 모듈을 직접 연결하지 않음.

## 3. 2. Tag와 앵커 거리 측정 (보조)

- 결과 파일: [03_Tag_UWB_거리측정.png](03_Tag_UWB_거리측정.png)
- 삽입 위치: 단계별 설명 2
- 학습 목표: Tag와 세 앵커가 UWB 신호를 주고받아 거리 측정
- 도해 유형: 관계형
- 편집 원본: `발표자료/11/16/경량버전/images/단계별/02_Tag_UWB_거리측정.png` (이전 버전은 Git 이력에 보존)

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Edit the supplied target illustration: preserve its technical meaning and relative device positions, but completely redraw it as a clean HAND-DRAWN Korean educational infographic, NOT a render.
16:9 landscape. Flat warm ivory background (#FFF9ED), generous whitespace. Bold rounded BLACK handwritten Korean title top center (top 15%). Thin slightly irregular BLACK pen outlines and legible handwritten black labels. Simple board sketches, only a few chips/ports; NO logos, real PCB detail, shadows, gradients, gloss, photos, 3D or textured paper. Only accent is sky blue #2799E6 with pale fill #E9F5FD. No orange, red, green, yellow, navy or second accent. Use blue ONLY on the active path, selected elements and the bottom conclusion. Main drawing middle 65%, one pale-blue hand-drawn conclusion box bottom center. All text large, no overlap, no fake UI or invented measurements. Render only the exact text quoted below.

Learning objective: Tag와 세 앵커가 UWB 신호를 주고받아 거리 측정.
Keep the target's room placement as a very simple light black-pen indoor sketch: rear-center table, Raspberry Pi on its left, A0 ESP32+small UWB module on its right, A1 at left foreground, A2 at right foreground, Tag centered in front. No wall/window/door detail needed. Preserve clearly separated Pi and A0. These are illustrative positions, never a scaled floor plan. Each ESP32 has a tiny adjacent UWB module, represented as simple flat pen rectangles.
Pi and the existing USB cable are pale gray. All 3 anchors and Tag active black pen. Draw exactly THREE sky-blue solid double-headed UWB arrows: Tag↔A0, Tag↔A1, Tag↔A2. Arrowheads at both ends, stop at corresponding board edges. No anchor↔anchor links and no ESP-NOW links. Plain central UWB label and the exact sequence label above the conclusion; avoid covering arrows. Bottom conclusion and provenance.

Exact rendered text, no other text:
"2. Tag와 앵커 거리 측정"
"Raspberry Pi"
"A0 · ESP32"
"A1 · ESP32"
"A2 · ESP32"
"Tag · LOLIN D32"
"UWB"
"POLL → RESP → FINAL"
"Tag ↔ 세 앵커 · UWB 거리 측정"
"구성 예시 · 실측 배치도 아님"

Use the title as top centered heading and the stated conclusion at bottom. Korean spelling, correct signal direction and contact state matter most.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "2. Tag와 앵커 거리 측정"
- [x] "Raspberry Pi"
- [x] "A0 · ESP32"
- [x] "A1 · ESP32"
- [x] "A2 · ESP32"
- [x] "Tag · LOLIN D32"
- [x] "UWB"
- [x] "POLL → RESP → FINAL"
- [x] "Tag ↔ 세 앵커 · UWB 거리 측정"
- [x] "구성 예시 · 실측 배치도 아님"

### 내용 검수 포인트

- Tag↔A0/A1/A2 모두 양방향, Pi로 UWB 화살표 금지. 절차 POLL/RESP/FINAL 순서.

## 4. 3. A1·A2 보고를 A0로 전달 (보조)

- 결과 파일: [04_ESP_NOW_A0_보고전달.png](04_ESP_NOW_A0_보고전달.png)
- 삽입 위치: 단계별 설명 3
- 학습 목표: A1·A2 측정 보고의 수신 지점은 A0
- 도해 유형: 관계형
- 편집 원본: `발표자료/11/16/경량버전/images/단계별/03_ESP_NOW_A0_보고전달.png` (이전 버전은 Git 이력에 보존)

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Edit the supplied target illustration: preserve its technical meaning and relative device positions, but completely redraw it as a clean HAND-DRAWN Korean educational infographic, NOT a render.
16:9 landscape. Flat warm ivory background (#FFF9ED), generous whitespace. Bold rounded BLACK handwritten Korean title top center (top 15%). Thin slightly irregular BLACK pen outlines and legible handwritten black labels. Simple board sketches, only a few chips/ports; NO logos, real PCB detail, shadows, gradients, gloss, photos, 3D or textured paper. Only accent is sky blue #2799E6 with pale fill #E9F5FD. No orange, red, green, yellow, navy or second accent. Use blue ONLY on the active path, selected elements and the bottom conclusion. Main drawing middle 65%, one pale-blue hand-drawn conclusion box bottom center. All text large, no overlap, no fake UI or invented measurements. Render only the exact text quoted below.

Learning objective: A1·A2 측정 보고의 수신 지점은 A0.
Keep the target's room placement as a very simple light black-pen indoor sketch: rear-center table, Raspberry Pi on its left, A0 ESP32+small UWB module on its right, A1 at left foreground, A2 at right foreground, Tag centered in front. No wall/window/door detail needed. Preserve clearly separated Pi and A0. These are illustrative positions, never a scaled floor plan. Each ESP32 has a tiny adjacent UWB module, represented as simple flat pen rectangles.
A0, A1, A2 active black sketches, Pi/USB/Tag pale gray. Draw exactly TWO sky-blue dashed one-way arrows from A1 and A2, converging directly on the A0 ESP32 board. Each arrow head visibly ends at A0 and not at the table or Pi. NO UWB arrows. ESP-NOW label in free central space. Highlight A0 with pale blue fill but no glowing aura. Bottom conclusion and provenance.

Exact rendered text, no other text:
"3. A1·A2 보고를 A0로 전달"
"Raspberry Pi"
"A0 · ESP32"
"A1 · ESP32"
"A2 · ESP32"
"Tag · LOLIN D32"
"ESP-NOW"
"A0는 자신의 측정값도 함께 모음"
"구성 예시 · 실측 배치도 아님"

Use the title as top centered heading and the stated conclusion at bottom. Korean spelling, correct signal direction and contact state matter most.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "3. A1·A2 보고를 A0로 전달"
- [x] "Raspberry Pi"
- [x] "A0 · ESP32"
- [x] "A1 · ESP32"
- [x] "A2 · ESP32"
- [x] "Tag · LOLIN D32"
- [x] "ESP-NOW"
- [x] "A0는 자신의 측정값도 함께 모음"
- [x] "구성 예시 · 실측 배치도 아님"

### 내용 검수 포인트

- ESP-NOW 화살표 두 개의 끝은 A0 보드. Pi나 Tag에 도착하지 않음.

## 5. 4. Pi에서 위치 계산·화면 표시 (보조)

- 결과 파일: [05_Pi_위치계산_화면표시.png](05_Pi_위치계산_화면표시.png)
- 삽입 위치: 단계별 설명 4
- 학습 목표: Pi에서 USB 보고를 처리해 경량 웹 화면에 표시
- 도해 유형: 과정형
- 편집 원본: `발표자료/11/16/경량버전/images/단계별/04_Pi_위치계산_화면표시.png` (이전 버전은 Git 이력에 보존)

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Edit the supplied target illustration: preserve its technical meaning and relative device positions, but completely redraw it as a clean HAND-DRAWN Korean educational infographic, NOT a render.
16:9 landscape. Flat warm ivory background (#FFF9ED), generous whitespace. Bold rounded BLACK handwritten Korean title top center (top 15%). Thin slightly irregular BLACK pen outlines and legible handwritten black labels. Simple board sketches, only a few chips/ports; NO logos, real PCB detail, shadows, gradients, gloss, photos, 3D or textured paper. Only accent is sky blue #2799E6 with pale fill #E9F5FD. No orange, red, green, yellow, navy or second accent. Use blue ONLY on the active path, selected elements and the bottom conclusion. Main drawing middle 65%, one pale-blue hand-drawn conclusion box bottom center. All text large, no overlap, no fake UI or invented measurements. Render only the exact text quoted below.

Learning objective: Pi에서 USB 보고를 처리해 경량 웹 화면에 표시.
Keep the target's room placement as a very simple light black-pen indoor sketch: rear-center table, Raspberry Pi on its left, A0 ESP32+small UWB module on its right, A1 at left foreground, A2 at right foreground, Tag centered in front. No wall/window/door detail needed. Preserve clearly separated Pi and A0. These are illustrative positions, never a scaled floor plan. Each ESP32 has a tiny adjacent UWB module, represented as simple flat pen rectangles.
Pi/A0 active, other three devices in pale gray WITHOUT labels. A sky-blue USB cable and a single sky-blue report arrow above it points from A0 at right to Pi at left. Keep exactly USB label. Under the room sketch show one large pale-blue bottom conclusion box containing the exact processing sequence (not a fake app screenshot). Place the Wi-Fi sentence in black below that box, provenance line at lowest edge. No cloud, no extra screen UI, no radio arrows.

Exact rendered text, no other text:
"4. Pi에서 위치 계산·화면 표시"
"Raspberry Pi"
"A0 · ESP32"
"USB"
"수신 → 위치 계산 → SQLite 저장 → 경량 UI"
"Mac·휴대폰은 같은 Wi-Fi로 접속"
"구성 예시 · 실측 배치도 아님"

Use the title as top centered heading and the stated conclusion at bottom. Korean spelling, correct signal direction and contact state matter most.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "4. Pi에서 위치 계산·화면 표시"
- [x] "Raspberry Pi"
- [x] "A0 · ESP32"
- [x] "USB"
- [x] "수신 → 위치 계산 → SQLite 저장 → 경량 UI"
- [x] "Mac·휴대폰은 같은 Wi-Fi로 접속"
- [x] "구성 예시 · 실측 배치도 아님"

### 내용 검수 포인트

- USB 보고 방향 A0→Pi. SQLite는 위치 계산 이후. Wi-Fi는 Pi 웹 접속용이며 UWB와 분리.

## 6. 당김식 배터리 전원 구상 (보조)

- 결과 파일: [06_당김식_배터리트리거_구상.png](06_당김식_배터리트리거_구상.png)
- 삽입 위치: 트리거 구상 전체 연결
- 학습 목표: 배터리 양극 경로를 당김핀의 스위치로 끊고 연결하는 구상
- 도해 유형: 비교·신호상태형
- 편집 원본: `발표자료/11/16/트리거_구상/images/당김식_배터리트리거_구상.png` (이전 버전은 Git 이력에 보존)

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Edit the supplied target illustration: preserve its technical meaning and relative device positions, but completely redraw it as a clean HAND-DRAWN Korean educational infographic, NOT a render.
16:9 landscape. Flat warm ivory background (#FFF9ED), generous whitespace. Bold rounded BLACK handwritten Korean title top center (top 15%). Thin slightly irregular BLACK pen outlines and legible handwritten black labels. Simple board sketches, only a few chips/ports; NO logos, real PCB detail, shadows, gradients, gloss, photos, 3D or textured paper. Only accent is sky blue #2799E6 with pale fill #E9F5FD. No orange, red, green, yellow, navy or second accent. Use blue ONLY on the active path, selected elements and the bottom conclusion. Main drawing middle 65%, one pale-blue hand-drawn conclusion box bottom center. All text large, no overlap, no fake UI or invented measurements. Render only the exact text quoted below.

Learning objective: 배터리 양극 경로를 당김핀의 스위치로 끊고 연결하는 구상.
Replace all old dense paragraphs with two spacious side-by-side comparison sketches, no heavy card borders. Same simple LiPo battery on left of each half, pull-pin lever switch in center, simple LOLIN board on right. Upper positive path is battery + → COM → switch contact → NC → board +, lower negative path directly battery − → board −, no switch on negative. Use thin black wiring with only the active closed positive path in sky blue on right. No green/red wire color.
LEFT: insulating pin with ring inserted from above presses a spring lever DOWN; schematic COM–NC contact distinctly OPEN (visible gap), board unpowered. RIGHT: same pin pulled out upward (single blue upward movement arrow, no text), lever returns UP; COM–NC contact CLOSED (continuous line), board receives power and stays ON while pin absent. Use simple educational contact symbol, not claimed exact physical terminal layout. State headings above each sketch. Labels battery/board repeated as needed. Minimal "+","−" markings identify wiring. Below comparison one shared conclusion box, then the validation/USB sentence. No USB cable, chargers, explosion, fire, measured claims or product part-number dimensions.

Exact rendered text, no other text:
"당김식 배터리 전원 구상"
"핀 삽입 · OFF"
"핀 제거 · ON 유지"
"3.7V 배터리"
"LOLIN D32"
"COM"
"NC"
"+"
"−"
"배터리 +선에 스위치를 직렬 연결"
"USB 분리 기준 · 실물 동작 미검증"

Use the title as top centered heading and the stated conclusion at bottom. Korean spelling, correct signal direction and contact state matter most.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "당김식 배터리 전원 구상"
- [x] "핀 삽입 · OFF"
- [x] "핀 제거 · ON 유지"
- [x] "3.7V 배터리"
- [x] "LOLIN D32"
- [x] "COM"
- [x] "NC"
- [x] "+"
- [x] "−"
- [x] "배터리 +선에 스위치를 직렬 연결"
- [x] "USB 분리 기준 · 실물 동작 미검증"

### 내용 검수 포인트

- 핀 삽입→레버 눌림→COM–NC 개방/OFF. 핀 제거→레버 복귀→COM–NC 연결/ON. 음극 직결.

### 배터리 연결도 접점 보정 프롬프트

외부 레버와 내부 접점을 분리하고, 열린 접점도 COM에 연결된 상태가 보이도록 편집했습니다.

```text
Correct ONLY the switch cutaway details of this battery pull-trigger hand-drawn infographic. Keep all exact Korean text, battery/board positions, black hand lettering, ivory background and sky-blue-only accent. Keep both external battery positive and negative wire paths unchanged.
For each switch housing, draw a physical spring LEVER in the UPPER half and a SEPARATE simple electrical COM–NC contact symbol in the LOWER half. These are mechanically linked inside a microswitch but must not be conflated as one exposed metal bar.
LEFT (pin inserted OFF): pin visibly presses the UPPER lever DOWN. BELOW it, the moving electrical contact blade is hinged at COM (touches COM dot continuously), extends diagonally upward toward NC but STOPS short of NC with a very clear gap. Therefore positive path is OPEN. The blade must NOT float disconnected from both terminals.
RIGHT (pin removed ON): pin clear above switch, upper spring lever returns UP. BELOW it, COM–NC contact blade is CLOSED horizontally and continuously touches both COM and NC. Blue positive wire must pass through the closed contacts, not bypass them. Negative wire remains direct. No accidental short between positive and negative.
Do not add explanations, labels, symbols or text; COM/NC remain on the electrical terminal dots only. Remove the three decorative blue rays next to the inserted pin. Preserve the single upward pull arrow at right. Simple conceptual switch drawing, no manufacturer-exact terminal claims, no shadows, gradient or 3D.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

## 7. 당김식 전원 스위치 (보조)

- 결과 파일: [07_스위치_트리거_구상도.png](07_스위치_트리거_구상도.png)
- 삽입 위치: 전원 스위치 동작 확대 구상
- 학습 목표: 핀이 레버를 누르면 OFF, 핀을 제거하면 COM–NC가 연결되어 ON 유지
- 도해 유형: 비교·공간구조형
- 확대도는 사각 손잡이의 절연핀과 레버·접점으로 단순화한 설명용 기구 구상. 실제 제작 치수·완제품 형상이 아님.
- 편집 기준: 수정된 배터리 연결도. 이전 확대도의 문구 편집이 도구의 폭력 관련 분류로 두 차례 거절되어, 전자부품의 접점 중심으로 재구성.

### 복사용 이미지 생성 프롬프트

```text
Use case: style-transfer. Input image is an educational diagram of a wearable electronic sensor's battery power switch. Edit it into a CLOSE-UP educational illustration of the same low-voltage ELECTRICAL MICROSWITCH. Remove the battery and circuit-board pictures and enlarge only the two switch mechanisms. This is a conceptual electronics teaching diagram.
16:9 horizontal, flat warm ivory background #FFF9ED, ample whitespace, large rounded BLACK Korean handwritten title at top center, thin natural BLACK pen outlines, black legible handwritten labels, one sky-blue accent family #2799E6/#E9F5FD only. No photos, 3D, shadows, gradients, logos, texture or extra decorations.
Two side-by-side cutaway drawings of the same rectangular lever microswitch. Above each is a simple RECTANGULAR plastic insulating spacer tab (flat pull tab with a small rectangular handle, NO ring), sliding vertically through a slot in a little housing. UPPER part shows the mechanical spring lever; LOWER part shows separate schematic COM–NC electrical contacts.
LEFT: spacer tab inserted, presses upper lever down. Lower electrical blade is continuously hinged at COM and raised clear of NC, obvious OPEN GAP. Black positive wire battery endpoint→COM, NC→board endpoint, with no bridge across the gap.
RIGHT: spacer tab removed above slot, a single sky-blue upward movement arrow. Upper lever spring returned up. Lower COM–NC blade is closed continuously, positive path through contacts is sky blue. No negative wire in this close-up.
Only once on left use simple black callout lines identifying spacer and lever. Terminal labels COM and NC in both halves. External endpoint labels on both halves, no actual batteries or boards. Avoid exact manufacturer terminal positions or dimensions.
Exact rendered text:
Title: "당김식 전원 스위치"
Left heading: "핀 삽입 · OFF"
Right heading: "핀 제거 · ON 유지"
Callouts: "절연핀", "레버"
Terminals: "COM", "NC"
External endpoints: "배터리 +", "보드 BAT+"
Shared pale-blue bottom conclusion box: "핀이 빠진 동안 전원 ON 유지"
Small bottom disclaimer: "설명용 구상 · 실물 동작 미검증"
No other explanatory sentences. Do not invent a different conclusion.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```

### 렌더 텍스트 체크리스트

- [x] "당김식 전원 스위치"
- [x] "핀 삽입 · OFF"
- [x] "핀 제거 · ON 유지"
- [x] "절연핀"
- [x] "레버"
- [x] "COM"
- [x] "NC"
- [x] "배터리 +"
- [x] "보드 BAT+"
- [x] "핀이 빠진 동안 전원 ON 유지"
- [x] "설명용 구상 · 실물 동작 미검증"

### 내용 검수 포인트

- 삽입된 절연핀 끝단이 눌린 레버에 직접 맞닿음.
- 레버가 눌린 왼쪽은 COM–NC 개방, 레버가 복귀한 오른쪽은 COM–NC 연결.
- 전기 접점은 기구 레버와 분리해 표시. COM 쪽 접점은 배선과 계속 이어져 있음.
- 단자 위치·핀 치수·당김 힘을 실물 사양으로 제시하지 않음.

### 절연핀·레버 접촉 보정 프롬프트

```text
이 배터리 전원 마이크로스위치 교육 도해에서 왼쪽 절연핀 끝단의 접촉만 수정합니다.
왼쪽의 하늘색 절연핀은 현재 레버 위에 떠 있습니다. 절연핀의 세로 막대 아랫부분을 같은 수직축으로 약 45픽셀 더 아래까지 연장하여, 삽입 슬롯을 지나 눌린 레버의 윗면 중간에 끝단이 직접 맞닿도록 그립니다. 핀 끝과 레버 사이에 빈틈이 없어야 합니다. 핀이 레버를 아래로 눌러 유지하는 기구 접촉이 명확해야 합니다. 슬롯의 선은 핀 뒤로 가려집니다.
왼쪽 레버의 눌린 각도와 하단 COM–NC 열린 접점, 오른쪽 레버의 복귀 각도와 닫힌 접점, 오른쪽 제거된 핀은 바꾸지 않습니다.
모든 제목·라벨·결론·하단 문구·배선·화살표·배경·색·글씨·레이아웃은 그대로 유지합니다. 다른 글자·숫자·기호는 추가하지 않습니다.
위에 명시한 문구 외에는 어떤 글자·숫자·라벨도 추가하지 않는다. 설명에 필요한 도해만 그리며, 의미 없는 장식은 넣지 않는다.
```
