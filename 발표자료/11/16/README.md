# 11월 16일 발표 자료

이번 발표 범위는 **경량 UI 버전까지**입니다.

- [경량 버전 발표 자료](경량버전/11월16일_발표자료.md)
- [실제 Pi 접속 시험 영상](경량버전/Pi_경량UI_실제접속시험.mp4)
- [실제 화면 캡처](경량버전/Pi_경량UI_실제화면.png)

## 코드 버전 구분

| 버전 | 화면 파일 | 접속 경로 |
| --- | --- | --- |
| 경량·다운그레이드 | [index_lite.html](../../../raspberrypi/web/index_lite.html) | `/`, `/lite` |
| 기존 전체 화면 | [index_full.html](../../../raspberrypi/web/index_full.html) | `/full` |

수신기·SQLite·웹 API는 두 화면이 공유합니다. 전체 화면의 경보·명령·CSV 기능은 기존 API로 유지되며 경량 화면에는 표시하지 않습니다.
