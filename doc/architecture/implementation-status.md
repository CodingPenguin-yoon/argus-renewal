# Implementation Status

## 요약
- 현재 KRX 사용자 표면은 `대시보드 / AI 인사이트 / 시장 신호 / 시장 뉴스 / 매크로 캘린더` 기준으로 정렬되어 있습니다.
- canonical 경로는 `/krx/dashboard`, `/krx/insights`, `/krx`, `/krx/news`, `/krx/macro-calendar` 입니다.
- 이전 경로 `/krx/overview`, `/krx/macro`, `/krx/global-events`는 호환 redirect만 유지합니다.

## 완료
- 상단 GNB와 주요 화면 제목을 새 IA 기준으로 정리했습니다.
- 공통 헤더는 compact status 중심으로 축소했고, `오늘의 시장 톤`은 `AI 인사이트` 중심 콘텐츠로 이동했습니다.
- `AI 인사이트`에 `시장 심리 / 변동성 온도 / AI 확신도` 게이지를 추가했고, gauge bar는 `progressbar` 접근성 속성을 가집니다.
- `대시보드` 상단에는 환율, WTI·에너지, 금리 미니 위젯을 추가했습니다.
- 공통 KRX fetch helper는 기본 `no-store`를 유지하면서 필요한 호출자만 `revalidate`를 줄 수 있게 정리했습니다.
- `시장 신호`, 파생 요약, `AI 인사이트`의 macro news는 30초 재검증 기준으로 분리했습니다.
- backend에는 `GET /api/krx/macro-reference/cards`가 추가됐고, `AI 인사이트`는 이 경로의 FRED 카드가 준비되면 기존 `금리` macro card 대신 우선 사용합니다.
- 상단 GNB는 안정 탭만 적극 prefetch하고 `시장 뉴스`는 제외합니다.
- 실제 사용자 표면 경로를 `/krx/dashboard`, `/krx/insights`, `/krx/macro-calendar`로 정리했고, 기존 경로는 redirect로 호환합니다.
- `doc/`에는 `troubleshooting/` 폴더를 추가해 오늘 변경의 배경과 이유를 쉬운 문서로 남겼습니다.

## 현재 기준 핵심 경로
- `architecture/system-map.md`: 실제 런타임 흐름과 데이터 조합 경로
- `architecture/project-structure.md`: 리포 구조와 주요 엔트리
- `architecture/krx-mvp-ia.md`: 현재 사용자 표면 IA와 canonical URL
- `plans/current-status.md`: 현재 라운드 요약
- `troubleshooting/README.md`: 비전공자용 설명 문서 인덱스

## 성능 상태
- `시장 뉴스`는 동적 유지와 60초 폴링을 계속 사용합니다.
- `대시보드`, `AI 인사이트`, 파생 관련 fetch는 30초 재검증을 사용합니다.
- selective prefetch 수동 측정 결과:
  - `/krx/dashboard` 최초 진입 시 `/krx`, `/krx/insights`, `/krx/macro-calendar` prefetch 확인
  - `/krx/news` prefetch는 확인되지 않음
  - 같은 세션에서 `AI 인사이트` 클릭 후 추가 리소스는 0건
  - `시장 뉴스` 클릭 후에는 뉴스 RSC와 탭별 리소스가 새로 요청됨

## 남은 일
- 현재 남은 구현은 FRED를 `대시보드`와 `시장 신호`까지 확장하는 일, 그리고 KIS 파생 source precedence를 고정하는 일입니다.
- 이후 추가 고도화 후보:
  - prefetch 계측 자동화
  - 게이지 계산식 세분화
  - redirect 이후 canonical metadata 정교화

## 리스크
- legacy redirect 경로는 당분간 유지해야 하므로, 문서와 테스트는 canonical 경로와 redirect 경로를 함께 구분해서 봐야 합니다.
- 아카이브 문서는 과거 계획과 경로를 포함하므로 현재 사실 문서처럼 읽으면 안 됩니다.

## 마지막 갱신
- 2026-03-16
