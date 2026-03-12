# Current System Map

현재 코드 기준으로 Argus Renewal의 실제 실행 경로를 요약한 문서입니다.

## 런타임 개요
- 프런트엔드는 Next.js App Router이며 [`frontend/src/app/page.tsx`](../../frontend/src/app/page.tsx)에서 `/`를 `/krx`로 리다이렉트합니다.
- 백엔드는 FastAPI이며 [`backend/src/main.py`](../../backend/src/main.py)에서 앱을 만들고 `/api/krx`를 마운트합니다.
- KRX 사용자 화면은 `시장 신호`, `뉴스`, `글로벌 이벤트`, `관심종목` 네 갈래로 구성되며 공통 레이아웃을 공유합니다.
- 운영용 파이프라인과 관리자 기능은 `source_ingestion`, `company_master` 경로로 분리되어 있습니다.

## 공통 사용자 경로
```text
browser
-> frontend/src/app/page.tsx
-> /krx
-> frontend/src/app/krx/layout.tsx
-> frontend/src/krx/server/data-service.ts
-> frontend/src/krx/server/client.ts
-> backend/src/main.py
-> backend/src/krx/router.py 또는 /api/app/header, /api/news, /api/global-events
```

## KRX 공통 레이아웃
- [`frontend/src/app/krx/layout.tsx`](../../frontend/src/app/krx/layout.tsx)는 모든 KRX 페이지에서 먼저 실행됩니다.
- 이 레이아웃은 `getSearchIndex()`와 `getAppHeaderData()`를 동시에 호출합니다.
- 따라서 검색 인덱스, 헤더, 백엔드 연결 중 하나라도 깨지면 `/krx` 하위 전체 체감 품질이 같이 떨어집니다.

## 탭별 실행 경로

### 1) 시장 신호
```text
frontend/src/app/krx/page.tsx
-> getMarketSignalTabData()
-> frontend/src/krx/market-signal/server/data-service.ts
-> /api/krx/market-signal/*
-> backend/src/krx/market_signal/router.py
-> backend/src/krx/market_signal/service.py
```

### 2) 뉴스
```text
frontend/src/app/krx/news/page.tsx
-> getNewsTabData()
-> frontend/src/krx/news/server/data-service.ts
-> /api/news/*
-> backend/src/krx/market_news/router.py
-> backend/src/krx/news/service.py
```

추가 경로:
- 검색, 종목별 뉴스, 상세 조회는 [`frontend/src/krx/server/data-service.ts`](../../frontend/src/krx/server/data-service.ts)에서 `/api/krx/news/*`도 함께 사용합니다.
- 즉 뉴스 영역은 `/api/news/*`와 `/api/krx/news/*` 두 계층이 공존합니다.

### 3) 글로벌 이벤트
```text
frontend/src/app/krx/global-events/page.tsx
-> getGlobalEventsTabData()
-> frontend/src/krx/global-events/server/data-service.ts
-> /api/global-events/*
-> backend/src/krx/global_events/router.py
-> backend/src/krx/global_events/service.py
```

### 4) 관심종목
```text
frontend/src/app/krx/watchlist/page.tsx
-> getWatchlistPageData()
-> frontend/src/krx/server/data-service.ts
-> /api/krx/stocks + /api/krx/news
-> backend/src/krx/market/router.py + backend/src/krx/news/router.py
```

## 백엔드 공개 API 표면
- `/health`: 기본 헬스체크
- `/api/app/header`: 공통 헤더 데이터
- `/api/news/*`: 뉴스 카드, 헤더 컨텍스트, 커버리지
- `/api/global-events/*`: 글로벌 이벤트 하이라이트, upcoming, week, coverage
- `/api/krx/*`: 시장 신호, 파생상품, 종목, 뉴스, 관리자용 KRX 라우트

## 운영 및 배치 경로
- [`backend/src/krx/source_ingestion/router.py`](../../backend/src/krx/source_ingestion/router.py): 원문 수집, 이벤트 정규화, 브리핑 입력, 브리핑 생성, 글로벌 이벤트 동기화, 회사 리포트 생성
- [`backend/src/krx/source_ingestion/service.py`](../../backend/src/krx/source_ingestion/service.py): 원문 수집 서비스 핵심 로직
- [`backend/src/krx/company_master/`](../../backend/src/krx/company_master): 회사 매핑, 수동 오버라이드, 마이그레이션, DB 접근
- 운영 경로는 DB 쓰기, 외부 공급자, 관리자 인증을 함께 건드리므로 사용자 화면 경로보다 영향 반경이 큽니다.

## 설정 경계
- 프런트 환경 변수는 [`frontend/src/krx/lib/env.ts`](../../frontend/src/krx/lib/env.ts)에서 `BACKEND_BASE_URL`을 읽습니다.
- 백엔드 설정은 [`backend/src/config/env.py`](../../backend/src/config/env.py)에서 로드하며 `db_path`, provider 토글, API 키, LLM 플래그, `KRX_ADMIN_API_KEY`까지 한 곳에 모여 있습니다.
- `.env`와 `.env.example`이 실제 코드와 어긋나면 프런트와 백엔드가 서로 정상처럼 보여도 일부 기능만 비는 상태가 생길 수 있습니다.

## 변경할 때 먼저 확인할 위치
- KRX 화면 공통 이상: `frontend/src/app/krx/layout.tsx`, `frontend/src/krx/server/data-service.ts`, `backend/src/main.py`
- 시장 신호 이상: `frontend/src/krx/market-signal/server/data-service.ts`, `backend/src/krx/market_signal/router.py`, `backend/src/krx/market_signal/service.py`
- 뉴스 카드 이상: `frontend/src/krx/news/server/data-service.ts`, `backend/src/krx/market_news/router.py`, `backend/src/krx/news/service.py`
- 글로벌 이벤트 이상: `frontend/src/krx/global-events/server/data-service.ts`, `backend/src/krx/global_events/router.py`, `backend/src/krx/global_events/service.py`
- 관리자 또는 배치 이상: `backend/src/krx/source_ingestion/router.py`, `backend/src/krx/source_ingestion/service.py`, `backend/src/krx/company_master/`

## 관련 테스트
- 프런트 페이지와 레이아웃: `frontend/src/app/krx/*.test.tsx`
- 프런트 탭 유틸리티: `frontend/src/krx/**/tabs.test.ts`, `frontend/src/krx/market-signal/lib/subtabs.test.ts`
- 백엔드 공개 API: `backend/tests/test_api.py`
- 백엔드 기능별 파이프라인: `backend/tests/test_market_news_product.py`, `backend/tests/test_global_events.py`, `backend/tests/test_event_pipeline.py`, `backend/tests/test_company_master_pipeline.py`
