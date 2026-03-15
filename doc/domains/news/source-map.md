# KRX News Source Map

현재 코드 기준으로 뉴스 서브시스템의 end-to-end 흐름과 소스 파일 책임을 정리한 문서입니다.

## 개요
- 뉴스 서브시스템은 `수집`, `가공`, `API 표면`, `프런트 소비` 네 층으로 나뉩니다.
- 사용자 화면 `/krx/news`는 `raw_documents`를 직접 읽지 않고, `news_batch_triage`와 `market_surface_*` materialization을 읽습니다.
- `/api/news/*`와 `/api/krx/news/*`는 이름이 비슷하지만 목적이 다릅니다.

## End-to-End Flow
```text
cron
-> backend/src/krx/source_ingestion/cli.py run-news-automation
-> backend/src/krx/source_ingestion/service.py
-> raw_documents
-> backend/src/krx/news/service.py refresh_materialized()
-> news_batch_triage
-> market_surface_candidates
-> market_surface_state + market_surface_history
-> backend/src/krx/market_news/router.py (/api/news/*)
-> frontend/src/krx/news/server/data-service.ts
-> frontend/src/krx/server/data-service.ts
-> frontend/src/app/krx/news/page.tsx
-> frontend/src/krx/news/components/news-tab-live-dashboard.tsx
-> frontend/src/krx/news/components/news-tab-dashboard.tsx
```

polling 보조 경로:
```text
open tab
-> frontend/src/krx/news/components/news-tab-live-dashboard.tsx
-> frontend/src/app/api/krx/news-tab/route.ts
-> frontend/src/krx/server/data-service.ts
-> backend /api/news/*
```

## 수집 책임
- `backend/src/krx/source_ingestion/cli.py`
  - `run-news-automation`, `sync-scheduled`, `normalize-events` 같은 운영 entrypoint
  - 장중 1분, 장 종료 직후 5분, 비장중 10분 cadence 판단
- `backend/src/krx/source_ingestion/service.py`
  - provider adapter를 통해 raw 문서를 수집하고 `raw_documents`에 적재
- `backend/src/krx/source_ingestion/event_service.py`
  - `/api/krx/news/events/*`에서 쓰는 event normalization
  - 뉴스 탭 market surface 자체와는 별도

## 가공 책임
- `backend/src/krx/news/service.py`
  - 뉴스 탭 핵심 materialization
  - `news_batch_triage` upsert
  - cluster/candidate/state/history 재계산
  - coverage, header context, feed read model 제공
- `backend/src/krx/news/batch_triage_ai.py`
  - 1차 batch triage provider
  - 짧은 뉴스 묶음을 한 번에 보내 문서별 triage 결과를 받음
  - 실패 시 deterministic fallback 전제
- `backend/src/krx/news/editorial_ai.py`
  - 2차 compare provider
  - 현재 표면과 top 후보를 한 번에 비교
  - `story_state`, `importance_label`, `editorial_reason`, `editorial_boost`, `confidence` 반환
- `backend/src/krx/news/factory.py`
  - env 설정을 읽어 datalab, batch triage, editorial AI provider를 묶어 `NewsProductService` 생성

## API 책임
- `backend/src/krx/market_news/router.py`
  - `/api/news/*`
  - 뉴스 탭 화면 전용 market surface API
  - dashboard, KR, GLOBAL, disclosure, header-context, coverage 제공
- `backend/src/krx/news/router.py`
  - `/api/krx/news/*`
  - feed, search, detail, company/ticker 기반 조회, recent events API 제공
- `backend/src/main.py`
  - FastAPI mount 지점

## 프런트 책임
- `frontend/src/app/krx/news/page.tsx`
  - SSR entry
  - 초기 뉴스 탭 payload를 받아 live dashboard로 전달
- `frontend/src/app/api/krx/news-tab/route.ts`
  - same-origin polling route
  - 브라우저 탭이 60초마다 접근하는 JSON endpoint
- `frontend/src/krx/server/data-service.ts`
  - 뉴스 탭 전체 payload 조합 entry
  - `/api/news/*`와 공통 KRX API 호출을 함께 조립
- `frontend/src/krx/news/server/data-service.ts`
  - `/api/news/*` 응답을 프런트 도메인 타입으로 정규화
- `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`
  - polling interval, visibility resume, 마지막 성공 payload 유지
- `frontend/src/krx/news/components/news-tab-dashboard.tsx`
  - 실제 카드/탭 렌더링
- `frontend/src/krx/types/domain.ts`
  - 뉴스 탭 payload 타입

## 파일 책임 표
| 파일 | 책임 | 주요 입력 | 주요 출력 | 변경 시 같이 볼 파일 |
| --- | --- | --- | --- | --- |
| `backend/src/krx/source_ingestion/cli.py` | automation cadence와 batch entrypoint | env, cron tick | raw sync, normalize, refresh 실행 | `backend/src/config/env.py`, `backend/src/krx/source_ingestion/service.py` |
| `backend/src/krx/source_ingestion/service.py` | raw 수집 orchestration | provider adapter, query target | `raw_documents` | `backend/src/krx/source_ingestion/cli.py`, `backend/src/krx/provider_registry.py` |
| `backend/src/krx/news/service.py` | triage/candidate/state/history materialization | `raw_documents`, datalab score, optional AI | `news_batch_triage`, `market_surface_*`, API read model | `backend/src/krx/news/factory.py`, `backend/tests/test_market_news_product.py` |
| `backend/src/krx/news/batch_triage_ai.py` | 1차 AI batch triage | 짧은 뉴스 묶음 | 문서별 triage 결과 | `backend/src/krx/news/service.py`, `backend/src/config/env.py` |
| `backend/src/krx/news/editorial_ai.py` | 2차 compare AI | 현재 표면 + top 후보 | compare 결과 | `backend/src/krx/news/service.py`, `backend/src/config/env.py` |
| `backend/src/krx/market_news/router.py` | 뉴스 탭 market surface API | `NewsProductService` | `/api/news/*` 응답 | `frontend/src/krx/news/server/data-service.ts` |
| `backend/src/krx/news/router.py` | feed/detail/search/event API | `NewsProductService`, `EventNormalizationService` | `/api/krx/news/*` 응답 | `frontend/src/krx/server/data-service.ts` |
| `frontend/src/app/krx/news/page.tsx` | 뉴스 탭 SSR entry | `getNewsTabData()` | initial props | `frontend/src/krx/news/components/news-tab-live-dashboard.tsx` |
| `frontend/src/app/api/krx/news-tab/route.ts` | same-origin polling endpoint | `getNewsTabData()` | no-store JSON payload | `frontend/src/krx/news/components/news-tab-live-dashboard.tsx` |
| `frontend/src/krx/news/components/news-tab-live-dashboard.tsx` | 60초 polling 상태 보유 | initialData, activeTab | live-updated dashboard props | `frontend/src/app/api/krx/news-tab/route.ts`, `frontend/src/krx/news/components/news-tab-dashboard.tsx` |
| `frontend/src/krx/news/components/news-tab-dashboard.tsx` | 최종 뉴스 탭 렌더링 | `NewsTabData` | UI | `frontend/src/krx/types/domain.ts` |

## 혼동하기 쉬운 경계
- event pipeline vs market surface pipeline
  - `event_service.py`는 event API를 위한 문서 정규화다.
  - `/krx/news` 메인 표면은 `news_batch_triage`와 `market_surface_*`를 읽는다.
- `/api/news/*` vs `/api/krx/news/*`
  - 전자는 뉴스 탭 화면 전용 market surface
  - 후자는 feed/detail/search/event API
- 설계 문서 vs 현재 구조
  - `../../plans/archive/krx-market-news-rebuild-plan.md`는 의도와 방향
  - 현재 runtime 설명은 이 문서와 `../../architecture/system-map.md`를 기준으로 본다.

## 검증 포인트
- 프런트:
  - `frontend/src/app/krx/news/page.test.tsx`
  - `frontend/src/krx/news/components/news-tab-live-dashboard.test.tsx`
- 백엔드:
  - `backend/tests/test_market_news_product.py`
  - `backend/tests/test_api.py`
  - `backend/tests/test_raw_document_ingestion.py`
