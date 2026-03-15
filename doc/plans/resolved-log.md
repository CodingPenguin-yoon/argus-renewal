# Resolved Log

## 2026-03-16
- backend에 `GET /api/krx/macro-reference/cards`를 추가하고, `DGS10`과 `FEDFUNDS`를 읽는 FRED reference contract를 `disabled / file / api` 모드로 고정했습니다.
- `AI 인사이트`가 `/api/krx/macro-reference/cards`를 읽도록 연결하고, FRED 카드가 준비되면 기존 macro news의 `금리` 카드를 대체하도록 정리했습니다.
- `대시보드`도 같은 FRED reference 경로를 읽도록 연결하고, overview 위젯에서는 `미국채 10년물` 카드를 우선 사용하도록 정리했습니다.
- `시장 신호`는 KIS/KRX provenance를 raw code 대신 사용자용 label badge로 노출하도록 정리했습니다.
- derivatives summary contract에 `pre_open_futures`를 추가하고, 파생 탭은 `KIS_DOMESTIC_DERIVATIVES` 개장 전 선물 변동률을 우선 노출하도록 정리했습니다.
- KRX IA를 `대시보드 / AI 인사이트 / 시장 신호 / 시장 뉴스 / 매크로 캘린더` 기준으로 정리했습니다.
- 공통 헤더의 대형 해석 블록을 축소하고, `오늘의 시장 톤`을 `AI 인사이트` 중심 콘텐츠로 이동했습니다.
- `doc/`를 `architecture / domains / plans / reference / troubleshooting` 구조로 정리했습니다.
- KRX 공통 fetch helper에 호출자 범위 `revalidate` 옵션을 추가하고, 시장 신호/파생 요약 fetch를 30초 재검증으로 전환했습니다.
- 상단 GNB는 안정 탭만 적극 prefetch하고, `시장 뉴스`는 동적 유지 정책에 맞춰 prefetch에서 제외했습니다.
- `AI 인사이트` 전용으로 macro news에 `revalidate: 30`을 적용해 캐시 경로를 분리했습니다.
- `대시보드`에 환율, WTI·에너지, 금리 거시 미니 위젯을 추가했습니다.
- `AI 인사이트`에 `시장 심리 / 변동성 온도 / AI 확신도` 게이지를 추가하고 gauge 접근성을 보강했습니다.
- canonical 경로를 `/krx/dashboard`, `/krx/insights`, `/krx/macro-calendar`로 정리했고, 기존 `/krx/overview`, `/krx/macro`, `/krx/global-events`는 redirect로 유지했습니다.
- route 테스트를 canonical 페이지 테스트와 redirect 테스트로 재정리했습니다.
- 오늘 변경의 배경과 이유를 설명하는 `doc/troubleshooting/` 문서를 추가했습니다.
- 다음 라운드 source 전략 문서로 `KIS 파생 + FRED 금리` 기준과 rollout plan을 추가했습니다.

## 2026-03-15
- 뉴스 리빌드 관련 현재 코드 기준 문서와 source map, rebuild summary를 정리했습니다.
