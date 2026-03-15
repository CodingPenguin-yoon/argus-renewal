# Current System Map

현재 코드 기준으로 Argus Renewal의 실제 실행 경로를 요약한 문서입니다.

## 런타임 개요
- 프런트엔드는 Next.js App Router이며 `frontend/src/app/page.tsx`에서 `/`를 `/krx/dashboard`로 리다이렉트합니다.
- 백엔드는 FastAPI이며 `/api/app/header`, `/api/krx/*`, `/api/news/*`, `/api/global-events/*`를 제공합니다.
- KRX 상단 정보 구조는 `대시보드 / AI 인사이트 / 시장 신호 / 시장 뉴스 / 매크로 캘린더 / 관심종목(보조)` 입니다.
- 운영 배치는 앱 내부 루프가 아니라 `backend/src/krx/source_ingestion/cli.py`의 CLI 명령을 `cron`에서 호출하는 구조입니다.

## 공통 사용자 경로
```text
browser
-> frontend/src/app/page.tsx
-> /krx/dashboard 또는 /krx
-> frontend/src/app/krx/layout.tsx
-> frontend/src/krx/components/layout/async-header.tsx
-> frontend/src/krx/server/data-service.ts
-> backend/src/main.py
-> /api/app/header 또는 /api/krx/*, /api/news/*, /api/global-events/*
```

## 탭별 실행 경로

### 1) 대시보드 `/krx/dashboard`
```text
frontend/src/app/krx/dashboard/page.tsx
-> getOverviewTabData()
-> frontend/src/krx/server/data-service.ts
-> 시장 신호 + 시장 뉴스 + 매크로 캘린더 요약 조합
```

### 2) AI 인사이트 `/krx/insights`
```text
frontend/src/app/krx/insights/page.tsx
-> getMacroTabData() + getAppHeaderData()
-> frontend/src/krx/server/data-service.ts
-> 오늘의 시장 톤 + AI 게이지 + 파생 기준점 + 거시 참고 카드 조합
```

### 3) 시장 신호 `/krx`
```text
frontend/src/app/krx/page.tsx
-> getMarketSignalTabData()
-> frontend/src/krx/market-signal/server/data-service.ts
-> /api/krx/market-signal/*
-> backend/src/krx/market_signal/router.py
-> backend/src/krx/market_signal/service.py
```

### 4) 시장 뉴스 `/krx/news`
```text
frontend/src/app/krx/news/page.tsx
-> getNewsTabData()
-> frontend/src/krx/server/data-service.ts
-> frontend/src/krx/news/server/data-service.ts
-> /api/news/*
-> backend/src/krx/market_news/router.py
-> backend/src/krx/news/service.py
```

추가 live polling 경로:
```text
open /krx/news tab
-> frontend/src/krx/news/components/news-tab-live-dashboard.tsx
-> frontend/src/app/api/krx/news-tab/route.ts
-> frontend/src/krx/server/data-service.ts
-> backend /api/news/*
```

### 5) 매크로 캘린더 `/krx/macro-calendar`
```text
frontend/src/app/krx/macro-calendar/page.tsx
-> normalizeGlobalEventsTab()
-> getGlobalEventsTabData()
-> frontend/src/krx/global-events/components/global-events-dashboard.tsx
-> /api/global-events/*
-> backend/src/krx/global_events/router.py
-> backend/src/krx/global_events/service.py
```

### 6) 관심종목 `/krx/watchlist`
```text
frontend/src/app/krx/watchlist/page.tsx
-> getWatchlistPageData()
-> frontend/src/krx/server/data-service.ts
-> /api/krx/stocks + /api/krx/news/*
-> backend/src/krx/market/router.py + backend/src/krx/news/router.py
```

## 호환 redirect
- `/krx/overview` -> `/krx/dashboard`
- `/krx/macro` -> `/krx/insights`
- `/krx/global-events` -> `/krx/macro-calendar`
- `/krx/global-events?tab=*` -> `/krx/macro-calendar?tab=*`
- `/krx/derivatives` -> `/krx?subtab=derivatives`

## KRX 공통 레이아웃
- `frontend/src/app/krx/layout.tsx`는 모든 KRX 페이지에서 먼저 실행됩니다.
- 레이아웃은 공통 셸을 제공하고 `AsyncMarketHeader`를 통해 공통 헤더 데이터를 비동기로 가져옵니다.
- 공통 헤더는 상태/속보/네비게이션 중심으로 얇게 유지하고, 메인 해석은 `AI 인사이트`에 둡니다.

## 변경할 때 먼저 확인할 위치
- IA/탭 구조 이상: `frontend/src/krx/components/layout/top-nav.tsx`, `frontend/src/krx/components/layout/shared-market-header.tsx`
- 대시보드/AI 인사이트 데이터 이상: `frontend/src/krx/server/data-service.ts`, `frontend/src/krx/macro/components/macro-dashboard.tsx`
- 뉴스 automation 이상: `backend/src/krx/source_ingestion/cli.py`, `backend/src/krx/source_ingestion/service.py`
- 뉴스 카드 이상: `backend/src/krx/news/service.py`, `backend/src/krx/market_news/router.py`
- 프런트 polling 이상: `frontend/src/app/api/krx/news-tab/route.ts`, `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`

## 관련 문서
- 현재 구현 상태: `implementation-status.md`
- 현재 프로젝트 구조: `project-structure.md`
- IA 정책: `krx-mvp-ia.md`
- 쉬운 설명 문서: `../troubleshooting/README.md`
