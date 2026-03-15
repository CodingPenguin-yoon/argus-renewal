# Current Code Structure Guide

현재 코드 기준으로 Argus Renewal 리포지토리의 코드 구조를 한 문서에서 훑기 위한 레퍼런스입니다.

이 문서는 "파일 하나가 무슨 책임을 가지는가"를 빠르게 잡기 위한 문서입니다.
세부 함수 설명보다 파일 책임과 연결 관계에 집중합니다.
뉴스 리빌드처럼 특정 서브시스템을 더 깊게 보려면 `../../domains/news/` 아래 문서를 함께 보면 됩니다.

## 이 문서의 범위
- 포함:
  - `frontend/src`
  - `backend/src`
  - `backend/tests`
  - `scripts`
  - 주요 migration
- 제외:
  - `node_modules`
  - `.next`
  - 에디터/도구 캐시
  - 이미지/정적 리소스 자체 설명

## 먼저 이해해야 하는 큰 구조

```text
browser
-> frontend/src/app/*
-> frontend/src/krx/server/*
-> backend/src/main.py
-> backend/src/krx/* 또는 backend/src/domains/*
-> SQLite DB / external providers

cron
-> backend/src/krx/source_ingestion/cli.py
-> backend/src/krx/source_ingestion/service.py
-> DB 적재
-> backend/src/krx/news/service.py 등 product materialization
```

한 줄로 말하면:
- 프런트는 Next.js App Router
- 백엔드는 FastAPI
- 배치는 앱 내부 scheduler가 아니라 `cron + CLI`
- 데이터 중심은 SQLite와 materialized read model

## 루트에서 먼저 보는 파일
- `README.md`
  - 리포 전체 실행법과 핵심 경로 요약
- `RUN_GUIDE.md`
  - 실행 보조 문서
- `.env.example`
  - 프런트/백엔드 기능 토글과 provider 설정 기준
- `AGENTS.md`
  - Codex 작업 원칙과 멀티 에이전트 규칙
- `package.json`
  - 루트 스크립트와 workspace 진입점
- `pnpm-workspace.yaml`
  - 모노레포 workspace 정의

## Frontend 구조

프런트는 `frontend/src/app`과 `frontend/src/krx` 두 층으로 나뉩니다.

- `src/app`
  - Next.js App Router route entry
- `src/krx`
  - KRX 도메인 전용 컴포넌트, 서버 데이터 조합, 타입, 유틸

### `frontend/src/app`

#### 전역 앱 entry
- `frontend/src/app/page.tsx`
  - `/`를 `/krx`로 보내는 루트 페이지
- `frontend/src/app/layout.tsx`
  - 전역 HTML shell
- `frontend/src/app/loading.tsx`
  - 전역 로딩 UI
- `frontend/src/app/error.tsx`
  - 전역 오류 경계
- `frontend/src/app/not-found.tsx`
  - 404 화면
- `frontend/src/app/globals.css`
  - 앱 전체 스타일 진입점

#### KRX 공통 route
- `frontend/src/app/krx/layout.tsx`
  - KRX 화면 공통 레이아웃
  - 헤더, 검색, 공통 shell, 공통 fetch가 여기서 시작됨
- `frontend/src/app/krx/layout.test.tsx`
  - 공통 레이아웃 회귀 테스트
- `frontend/src/app/krx/loading.tsx`
  - KRX 섹션 로딩 UI
- `frontend/src/app/krx/page.tsx`
  - `/krx` 시장 신호 메인
- `frontend/src/app/krx/page.test.tsx`
  - 시장 신호 페이지 테스트

#### 뉴스 route
- `frontend/src/app/krx/news/page.tsx`
  - `/krx/news` SSR entry
  - 초기 뉴스 탭 payload를 서버에서 받아옴
- `frontend/src/app/krx/news/page.test.tsx`
  - 뉴스 페이지 테스트
- `frontend/src/app/krx/news/loading.tsx`
  - 뉴스 탭 로딩 UI

#### 글로벌 이벤트 route
- `frontend/src/app/krx/global-events/page.tsx`
  - 글로벌 이벤트 탭 entry
- `frontend/src/app/krx/global-events/page.test.tsx`
  - 글로벌 이벤트 페이지 테스트

#### 파생/관심종목 route
- `frontend/src/app/krx/derivatives/page.tsx`
  - 파생상품 페이지
- `frontend/src/app/krx/derivatives/page.test.tsx`
  - 파생상품 페이지 테스트
- `frontend/src/app/krx/watchlist/page.tsx`
  - 관심종목 페이지

### `frontend/src/app/api`

이 폴더는 Next.js same-origin API route입니다.
브라우저에서 직접 backend base URL을 노출하지 않거나, 서버에서 다시 조합한 payload를 내보낼 때 씁니다.

- `frontend/src/app/api/krx/news-tab/route.ts`
  - `/api/krx/news-tab`
  - 뉴스 탭 열린 화면이 60초마다 치는 polling endpoint
- `frontend/src/app/api/krx/news-tab/route.test.ts`
  - same-origin polling route 테스트
- `frontend/src/app/api/krx/search-index/route.ts`
  - 검색 인덱스용 route

### `frontend/src/components/ui`

공용 UI primitive입니다.
도메인 로직은 거의 없고, 스타일이 입혀진 재사용 컴포넌트입니다.

- `badge.tsx`
- `button.tsx`
- `card.tsx`
- `scroll-area.tsx`
- `separator.tsx`
- `skeleton.tsx`
- `tabs.tsx`

### `frontend/src/krx/components`

#### 레이아웃
- `frontend/src/krx/components/layout/app-shell.tsx`
  - KRX 화면 외곽 shell
- `frontend/src/krx/components/layout/async-header.tsx`
  - 비동기 헤더 조합
- `frontend/src/krx/components/layout/disclaimer-banner.tsx`
  - 고지 배너
- `frontend/src/krx/components/layout/header-skeleton.tsx`
  - 헤더 로딩 스켈레톤
- `frontend/src/krx/components/layout/shared-market-header.tsx`
  - 시장 공통 헤더 렌더링
- `frontend/src/krx/components/layout/shared-market-header.test.tsx`
  - 공통 헤더 테스트
- `frontend/src/krx/components/layout/static-shell-header.tsx`
  - 고정 shell header
- `frontend/src/krx/components/layout/top-nav.tsx`
  - 상단 네비게이션
- `frontend/src/krx/components/layout/top-nav.test.tsx`
  - 상단 네비게이션 테스트

#### 검색
- `frontend/src/krx/components/search/search-box.tsx`
  - 검색 입력 박스

#### 종목
- `frontend/src/krx/components/stocks/stock-detail.tsx`
  - 종목 상세 뷰
- `frontend/src/krx/components/stocks/stock-timeline.tsx`
  - 종목 타임라인 UI

#### 공용 KRX UI
- `frontend/src/krx/components/ui/badge.tsx`
  - KRX 스타일 badge
- `frontend/src/krx/components/ui/empty-state.tsx`
  - empty state UI
- `frontend/src/krx/components/ui/filter-bar.tsx`
  - 필터 바 UI
- `frontend/src/krx/components/ui/section-header.tsx`
  - 섹션 헤더 UI

#### 관심종목
- `frontend/src/krx/components/watchlist/watchlist-manager.tsx`
  - 관심종목 상태 조작 UI

### `frontend/src/krx/market-signal`

- `frontend/src/krx/market-signal/components/market-signal-dashboard.tsx`
  - 시장 신호 메인 탭 렌더링
- `frontend/src/krx/market-signal/server/data-service.ts`
  - 시장 신호 탭용 서버 fetch 조합
- `frontend/src/krx/market-signal/lib/subtabs.ts`
  - 시장 신호 서브탭 규칙
- `frontend/src/krx/market-signal/lib/subtabs.test.ts`
  - 서브탭 규칙 테스트

### `frontend/src/krx/derivatives`

- `frontend/src/krx/derivatives/server/data-service.ts`
  - 파생상품 API fetch와 프런트 타입 변환

### `frontend/src/krx/global-events`

- `frontend/src/krx/global-events/components/global-events-dashboard.tsx`
  - 글로벌 이벤트 탭 렌더링
- `frontend/src/krx/global-events/server/data-service.ts`
  - 글로벌 이벤트 서버 데이터 조합
- `frontend/src/krx/global-events/lib/tabs.ts`
  - 글로벌 이벤트 탭 규칙
- `frontend/src/krx/global-events/lib/tabs.test.ts`
  - 탭 규칙 테스트

### `frontend/src/krx/market`

- `frontend/src/krx/market/server/data-service.ts`
  - 종목 목록/상세 fetch

### `frontend/src/krx/news`

뉴스는 현재 가장 복잡한 프런트 도메인입니다.

#### 뉴스 컴포넌트
- `frontend/src/krx/news/components/market-news-card.tsx`
  - 시장 표면 카드 UI
- `frontend/src/krx/news/components/news-card.tsx`
  - 일반 뉴스 카드 UI
- `frontend/src/krx/news/components/news-tab-dashboard.tsx`
  - 순수 렌더링 dashboard
  - 주어진 payload를 화면으로 그리는 역할
- `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`
  - 60초 polling 상태를 들고 있는 wrapper
  - 마지막 성공 payload 유지, 탭 상태 보존
- `frontend/src/krx/news/components/news-tab-live-dashboard.test.tsx`
  - live polling 상태 테스트
- `frontend/src/krx/news/components/news-tab-scroll-reset.tsx`
  - 탭 전환 시 scroll 위치 제어

#### 뉴스 로직/서버 fetch
- `frontend/src/krx/news/server/data-service.ts`
  - `/api/news/*` 응답을 프런트 타입으로 정규화
- `frontend/src/krx/news/lib/tabs.ts`
  - 뉴스 탭 규칙
- `frontend/src/krx/news/lib/tabs.test.ts`
  - 탭 규칙 테스트

### `frontend/src/krx/server`

- `frontend/src/krx/server/client.ts`
  - backend 호출용 공통 client 유틸
- `frontend/src/krx/server/data-service.ts`
  - 프런트 전체에서 가장 중요한 서버 데이터 조합 파일 중 하나
  - 뉴스, 종목, 헤더, 시장 신호, 글로벌 이벤트 등 여러 domain data-service를 묶음

### `frontend/src/krx/types`

- `frontend/src/krx/types/domain.ts`
  - 프런트가 믿고 쓰는 주요 도메인 타입 정의

### `frontend/src/krx/lib`

- `frontend/src/krx/lib/constants.ts`
  - 상수 모음
- `frontend/src/krx/lib/env.ts`
  - 프런트 환경 변수 로더
- `frontend/src/krx/lib/market.ts`
  - 시장 관련 유틸
- `frontend/src/krx/lib/page-view.ts`
  - 페이지 뷰 추적 유틸
- `frontend/src/krx/lib/utils.ts`
  - 공통 유틸
- `frontend/src/krx/lib/watchlist-storage.ts`
  - 관심종목 로컬 스토리지 유틸
- `frontend/src/krx/lib/__tests__/page-view.test.ts`
  - 페이지 뷰 유틸 테스트
- `frontend/src/krx/lib/__tests__/utils.test.ts`
  - 공통 유틸 테스트
- `frontend/src/krx/lib/__tests__/watchlist-storage.test.ts`
  - 관심종목 스토리지 테스트

### 기타 프런트 공용
- `frontend/src/lib/utils.ts`
  - 프로젝트 공통 유틸
- `frontend/src/test/setup.ts`
  - 프런트 테스트 setup

## Backend 구조

백엔드는 `main.py -> config -> domains -> krx` 순서로 읽는 게 편합니다.

### 앱 entry와 공통

- `backend/src/main.py`
  - FastAPI 전체 앱 진입점
  - health, KRX, global/public route mount
- `backend/src/config/env.py`
  - 백엔드 환경 변수 로더
  - 거의 모든 기능 토글과 provider 설정이 여기로 모임
- `backend/src/shared/errors.py`
  - 공통 예외 처리

### health domain
- `backend/src/domains/health/router.py`
  - `/health`

### `backend/src/krx`

- `backend/src/krx/app.py`
  - KRX 하위 app factory
- `backend/src/krx/router.py`
  - `/api/krx` 집계 라우터
- `backend/src/krx/provider_registry.py`
  - provider 정의 조회와 fallback 로직
- `backend/src/krx/publisher_registry.py`
  - publisher registry 관련 로직

### `backend/src/krx/app_header`

- `backend/src/krx/app_header/router.py`
  - `/api/app/header`
- `backend/src/krx/app_header/service.py`
  - 공통 헤더 payload 생성

### `backend/src/krx/market`

- `backend/src/krx/market/router.py`
  - 종목 API
- `backend/src/krx/market/data.py`
  - 로컬/예시 종목 데이터
  - 현재 구조에서는 mock 성격이 강함

### `backend/src/krx/market_signal`

- `backend/src/krx/market_signal/router.py`
  - 시장 신호 API
- `backend/src/krx/market_signal/service.py`
  - 시장 신호 payload 조합

### `backend/src/krx/derivatives`

- `backend/src/krx/derivatives/router.py`
  - 파생상품 API
- `backend/src/krx/derivatives/service.py`
  - 파생상품 read model 조합

### `backend/src/krx/global_events`

- `backend/src/krx/global_events/router.py`
  - 글로벌 이벤트 API
- `backend/src/krx/global_events/service.py`
  - 글로벌 이벤트 read model 핵심
- `backend/src/krx/global_events/factory.py`
  - service/provider 생성
- `backend/src/krx/global_events/models.py`
  - 글로벌 이벤트 모델/타입
- `backend/src/krx/global_events/adapters.py`
  - 외부 데이터 adapter
- `backend/src/krx/global_events/impact_llm.py`
  - 글로벌 이벤트 해석용 LLM 경로

### `backend/src/krx/news`

뉴스는 사용자 화면과 배치가 가장 많이 만나는 지점입니다.

- `backend/src/krx/news/router.py`
  - `/api/krx/news/*`
  - feed, search, detail, ticker/company, recent event API
- `backend/src/krx/news/service.py`
  - 뉴스 탭 핵심 service
  - `news_batch_triage`, `market_surface_candidates`, `market_surface_state`, `market_surface_history`를 읽고 쓰는 중심 파일
- `backend/src/krx/news/factory.py`
  - `NewsProductService`와 provider wiring
- `backend/src/krx/news/batch_triage_ai.py`
  - 1차 batch triage AI provider
- `backend/src/krx/news/editorial_ai.py`
  - 2차 compare AI provider
- `backend/src/krx/news/data.py`
  - 예시/기본 뉴스 데이터
  - 초기/보조 데이터 성격

### `backend/src/krx/market_news`

- `backend/src/krx/market_news/router.py`
  - `/api/news/*`
  - 뉴스 탭 화면 전용 market surface API
  - `/api/krx/news/*`와 목적이 다름

### `backend/src/krx/source_ingestion`

이 폴더는 수집, 정규화, 브리핑, 리포트, scheduler성 CLI를 모두 품고 있습니다.

#### 핵심 운영 파일
- `backend/src/krx/source_ingestion/cli.py`
  - 운영 CLI entrypoint
  - `run-news-automation`, `sync-scheduled`, `normalize-events` 등
- `backend/src/krx/source_ingestion/service.py`
  - raw document ingestion orchestration
- `backend/src/krx/source_ingestion/schedule.py`
  - 장중/장후/off-hours cadence 판단
- `backend/src/krx/source_ingestion/router.py`
  - 관리자/운영 route
- `backend/src/krx/source_ingestion/factory.py`
  - ingestion provider/service 생성
- `backend/src/krx/source_ingestion/factory_extensions.py`
  - 외부 descriptor 확장

#### event normalization
- `backend/src/krx/source_ingestion/event_service.py`
  - raw 문서를 이벤트로 정규화
- `backend/src/krx/source_ingestion/event_taxonomy.py`
  - 이벤트 분류 체계
- `backend/src/krx/source_ingestion/normalize.py`
  - 정규화 유틸
- `backend/src/krx/source_ingestion/llm.py`
  - event extraction LLM provider

#### raw document / provider 모델
- `backend/src/krx/source_ingestion/models.py`
  - ingestion domain model
- `backend/src/krx/source_ingestion/provider_descriptors.py`
  - provider descriptor 규격
- `backend/src/krx/source_ingestion/document_time.py`
  - 문서 시각 해석 유틸

#### briefing / report
- `backend/src/krx/source_ingestion/briefing_models.py`
  - 브리핑 데이터 모델
- `backend/src/krx/source_ingestion/briefing_service.py`
  - 시장 브리핑 생성
- `backend/src/krx/source_ingestion/briefing_signal_service.py`
  - 브리핑용 신호 조합
- `backend/src/krx/source_ingestion/report_llm.py`
  - 리포트/브리핑 계열 LLM helper
- `backend/src/krx/source_ingestion/company_report_service.py`
  - 회사 리포트 생성

#### provider 구현
- `backend/src/krx/source_ingestion/providers/dart_provider.py`
  - DART 공시 provider
- `backend/src/krx/source_ingestion/providers/mk_rss_provider.py`
  - MK RSS provider
- `backend/src/krx/source_ingestion/providers/naver_news_provider.py`
  - Naver 뉴스 provider
- `backend/src/krx/source_ingestion/providers/naver_datalab_provider.py`
  - Naver Datalab provider
- `backend/src/krx/source_ingestion/providers/bigkinds_provider.py`
  - 과거/확장용 BigKinds provider
- `backend/src/krx/source_ingestion/providers/kis_domestic_derivatives_service.py`
  - KIS 파생 데이터 공급
- `backend/src/krx/source_ingestion/providers/kis_market_breadth_service.py`
  - KIS 시장 breadth 관련 공급
- `backend/src/krx/source_ingestion/providers/kis_night_futures_service.py`
  - KIS 야간선물 공급
- `backend/src/krx/source_ingestion/providers/krx_derivatives_reference_service.py`
  - KRX 파생 기준 데이터 공급
- `backend/src/krx/source_ingestion/providers/_briefing_common.py`
  - 브리핑 공통 helper

#### 운영 문서
- `backend/src/krx/source_ingestion/README.md`
  - ingestion 런북
- `backend/src/krx/source_ingestion/EVENT_PIPELINE.md`
  - event pipeline 설명
- `backend/src/krx/source_ingestion/MARKET_BRIEFING_RUNBOOK.md`
  - 시장 브리핑 런북
- `backend/src/krx/source_ingestion/MARKET_SIGNAL_BRIEFING_RUNBOOK.md`
  - 시장 신호 브리핑 런북
- `backend/src/krx/source_ingestion/COMPANY_REPORT_RUNBOOK.md`
  - 회사 리포트 런북

### `backend/src/krx/company_master`

이 폴더는 DB 초기화와 회사 매핑의 중심입니다.

- `backend/src/krx/company_master/db.py`
  - SQLite 연결과 migration 적용 핵심
- `backend/src/krx/company_master/service.py`
  - 회사 마스터 서비스
- `backend/src/krx/company_master/router.py`
  - 회사 마스터 API
- `backend/src/krx/company_master/cli.py`
  - 회사 마스터 CLI
- `backend/src/krx/company_master/normalize.py`
  - 회사 식별자/이름 normalize helper
- `backend/src/krx/company_master/providers/dart.py`
  - 회사 마스터용 DART source
- `backend/src/krx/company_master/providers/kis.py`
  - 회사 마스터용 KIS source

#### migration 파일
- `001_company_master.sql`
  - 회사/매핑 기본 스키마
- `002_raw_documents_ingestion.sql`
  - raw document ingestion 스키마
- `003_event_pipeline.sql`
  - event pipeline 스키마
- `004_market_briefing_inputs.sql`
  - 시장 브리핑 입력 스키마
- `005_market_briefing_signals.sql`
  - 브리핑 신호 스키마
- `006_company_reports.sql`
  - 회사 리포트 스키마
- `007_company_report_optional_inputs.sql`
  - 회사 리포트 보조 입력
- `008_market_news_product.sql`
  - 초기 뉴스 product 스키마
- `009_global_events.sql`
  - 글로벌 이벤트 스키마
- `010_provider_registry.sql`
  - provider registry
- `011_publisher_registry.sql`
  - publisher registry
- `012_document_observed_time.sql`
  - 문서 시각 보강
- `013_deactivate_bigkinds_provider.sql`
  - BigKinds provider 상태 변경
- `014_news_product_score_layers.sql`
  - 뉴스 점수 레이어 보강
- `015_news_editorial_enrichments.sql`
  - editorial AI 관련 스키마 보강
- `016_market_surface_materialization.sql`
  - 현재 뉴스 리빌드 핵심인 `news_batch_triage`, `market_surface_*`

## 테스트 구조

### 백엔드 테스트
- `backend/tests/test_api.py`
  - 공개 API 표면 회귀 테스트
- `backend/tests/test_raw_document_ingestion.py`
  - raw ingestion/automation 테스트
- `backend/tests/test_event_pipeline.py`
  - event normalization 테스트
- `backend/tests/test_market_news_product.py`
  - 뉴스 리빌드 핵심 테스트
- `backend/tests/test_global_events.py`
  - 글로벌 이벤트 테스트
- `backend/tests/test_company_master_pipeline.py`
  - 회사 마스터 파이프라인 테스트
- `backend/tests/test_company_report_pipeline.py`
  - 회사 리포트 테스트
- `backend/tests/test_market_briefing_pipeline.py`
  - 시장 브리핑 테스트
- `backend/tests/test_market_briefing_signal_engine.py`
  - 브리핑 신호 엔진 테스트
- `backend/tests/test_krx_market_signal_api.py`
  - 시장 신호 API 테스트
- `backend/tests/test_krx_derivatives_api.py`
  - 파생 API 테스트

### 프런트 테스트
- `frontend/src/app/krx/*.test.tsx`
  - route/page 수준 테스트
- `frontend/src/app/api/krx/news-tab/route.test.ts`
  - same-origin API route 테스트
- `frontend/src/krx/news/components/news-tab-live-dashboard.test.tsx`
  - 뉴스 polling 상태 테스트
- `frontend/src/krx/components/layout/*.test.tsx`
  - 레이아웃 테스트
- `frontend/src/krx/lib/__tests__/*`
  - 프런트 유틸 테스트

## scripts 구조

- `scripts/krx-raw-ingestion.crontab.example`
  - raw ingestion 자동화 예시 cron
- `scripts/krx-event-pipeline.crontab.example`
  - event pipeline cron 예시
- `scripts/krx-market-briefing.crontab.example`
  - 시장 브리핑 cron 예시
- `scripts/krx-company-report.crontab.example`
  - 회사 리포트 cron 예시
- `scripts/global-events.crontab.example`
  - 글로벌 이벤트 cron 예시
- `scripts/check-market-boundaries.sh`
  - 시장 경계 확인용 shell script

## 목적별로 어디부터 읽을까

### 뉴스 탭을 이해하고 싶을 때
1. `frontend/src/app/krx/news/page.tsx`
2. `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`
3. `frontend/src/krx/server/data-service.ts`
4. `backend/src/krx/market_news/router.py`
5. `backend/src/krx/news/service.py`
6. `backend/src/krx/company_master/migrations/016_market_surface_materialization.sql`

### 수집과 cron 경로를 이해하고 싶을 때
1. `backend/src/krx/source_ingestion/cli.py`
2. `backend/src/krx/source_ingestion/schedule.py`
3. `backend/src/krx/source_ingestion/service.py`
4. `backend/src/krx/source_ingestion/factory.py`
5. provider 파일들

### DB부터 이해하고 싶을 때
1. `backend/src/krx/company_master/db.py`
2. migration 파일들
3. `backend/src/krx/news/service.py`
4. `backend/tests/test_market_news_product.py`

## 같이 보면 좋은 문서
- `../../architecture/project-structure.md`
- `../../architecture/system-map.md`
- `../../domains/news/source-map.md`
- `krx_news/README.md`

## 문서 원칙
- 현재 구조 판단은 실제 코드와 테스트를 우선합니다.
- 오래된 설계 문서보다 현재 실행 경로와 migration 상태를 먼저 봅니다.
- 이 문서는 파일 책임 설명용이고, 세부 서브시스템 deep dive는 별도 study 문서를 따릅니다.
