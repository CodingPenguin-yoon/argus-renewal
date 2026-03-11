# KRX 3축 IA API 구현안 (Codex 입력용)

## 목표
- 상단 메인 탭을 `시장 신호 / 뉴스 / 글로벌 이벤트` 3축으로 고정합니다.
- 공통 헤더는 `오늘의 시장 톤 + 근거 2~3개 + 장 상태 + 업데이트 시각`만 표시합니다.
- 속보는 공통 헤더 하단의 조건부 레이어로만 노출합니다.
- 탭 간 중복을 제거합니다.
  - `시장 신호`: 현재 포지션/수급 해석
  - `뉴스`: 배경(한국/글로벌 2열)
  - `글로벌 이벤트`: 향후 촉매(24시간/주간 + 영향 해석)

## API 계약

### 1) 공통 헤더
- `GET /api/app/header?market=krx`
- 사용 필드
  - `market_tone_line`
  - `supporting_points[]` (UI에서는 최대 3개)
  - `phase`
  - `updated_at`
  - `breaking_news` (있을 때만 배너 노출)

### 2) 시장 신호 탭
- `GET /api/krx/market-signal/summary`
- 사용 필드
  - `item.interpretation_line`
  - `item.explanation_text`
  - `item.cards[]` (`오늘 시장 결론`, `자금 흐름`, `선물·옵션 신호`, `오늘 체크포인트`)
  - `item.last_updated_at`
- 주의
  - 이 탭에서 별도 일정 API를 결합하지 않습니다.

### 3) 뉴스 탭
- `GET /api/news/kr?limit=12`
- `GET /api/news/global?limit=12`
- `GET /api/news/header-context`
- `GET /api/news/coverage`
- UI 사용 규칙
  - `market_scope`가 `kr_market/global_market`인 카드만 노출
  - 카드 노출 필드: `title`, `one_line_summary`, `why_it_matters`, `market_impact`, `published_at`
  - `한국 증시 / 글로벌 증시` 2열 유지

### 4) 글로벌 이벤트 탭
- `GET /api/global-events/highlight?limit=6`
- `GET /api/global-events/upcoming?window=24h`
- `GET /api/global-events/week`
- `GET /api/global-events/coverage` (탑 배지 용도)
- UI 사용 필드
  - `event_time_kst`, `title`, `importance`, `release.previous/forecast/actual`, `impact.summary_ko`
  - 레이아웃: 좌측 시간순 이벤트 리스트, 우측 영향 해석 카드

## 프론트 구현 체크리스트
- `AppShellHeader`
  - `파생` 직접 버튼 제거
  - `관심종목`만 유틸 액션으로 유지
  - 장 상태/업데이트 시각 표시
- `SharedMarketHeader`
  - 커버리지 상세 패널 제거
  - supporting point 3개까지만 노출
  - 속보 레이어는 `breaking_news` 존재 시에만 노출
- `MarketSignalDashboard`
  - 일정 섹션 제거 (탭 경계 유지)
- `NewsTabDashboard`
  - 과밀 메타(신뢰/신규성/대표근거) 노출 제거
  - 2열 구조 고정
- `GlobalEventsDashboard`
  - 우측 보조 패널은 영향 해석 중심으로 유지
  - 커버리지 상세 리스트는 제거

## 실패/폴백 규칙
- 각 API 실패 시 탭 단위 EmptyState를 노출하고 페이지 전체는 유지합니다.
- `breaking_news`가 없으면 속보 UI를 렌더하지 않습니다.
- `published_at`/`updated_at`이 비어 있으면 `시간 미상` 또는 `업데이트 정보 없음`으로 표기합니다.

## 테스트 기준
- 탭 구조
  - `시장 신호/뉴스/글로벌 이벤트` 3개 링크만 메인 탭에 존재
  - `파생`은 메인 헤더에서 노출되지 않음
- 시장 신호
  - `주요 일정` 섹션 미노출
- 뉴스
  - `한국 증시/글로벌 증시` 2열 유지
  - 카드에서 `MARKET IMPACT` 노출
- 글로벌 이벤트
  - `이번 주 핵심 이벤트`, `다음 24시간`, `이번 주 일정`, `영향 해석 카드` 노출

## Codex 실행 프롬프트 (복붙)
```text
KRX 웹 IA를 3축(시장 신호/뉴스/글로벌 이벤트)으로 고정하고 탭 간 중복을 제거해줘.

요구사항:
1) 공통 헤더는 오늘의 시장 톤/근거(최대 3개)/장 상태/업데이트 시각만 표시.
2) 속보는 공통 헤더 아래 조건부 배너로만 노출.
3) 시장 신호 탭은 /api/krx/market-signal/summary만 사용하고 일정 섹션 제거.
4) 뉴스 탭은 /api/news/kr, /api/news/global, /api/news/header-context, /api/news/coverage를 사용.
   - market_scope가 kr_market/global_market인 카드만 노출.
   - 카드 표시 필드는 title/one_line_summary/why_it_matters/market_impact/published_at.
   - 한국 증시/글로벌 증시 2열 고정.
5) 글로벌 이벤트 탭은 /api/global-events/highlight, /upcoming?window=24h, /week, /coverage를 사용.
   - 좌측 시간순 리스트 + 우측 영향 해석 카드 구조 유지.
6) 메인 헤더에서 파생 버튼 제거, 관심종목은 유틸 액션으로 유지.
7) 변경 후 테스트와 린트 실행:
   - pnpm --filter frontend test
   - pnpm --filter frontend lint
```
