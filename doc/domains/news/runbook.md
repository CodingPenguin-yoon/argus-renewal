# KRX 뉴스 탭 Runbook

현재 코드 기준으로 `/krx/news` 운영 규칙과 확인 포인트를 정리한 문서입니다.

## 목적
- 뉴스 탭의 현재 source-of-truth와 자동화 경계를 운영 관점에서 빠르게 확인합니다.
- `/api/news/*`와 `/api/krx/news/*`의 목적 차이를 헷갈리지 않게 정리합니다.
- 프런트 polling, batch triage, compare AI, event normalization의 경계를 구분합니다.

## 현재 구조 요약
- 수집 입력은 `raw_documents`입니다.
- 뉴스 탭 1차 판단 source-of-truth는 `news_batch_triage`입니다.
- 최종 대표 카드는 `market_surface_candidates -> market_surface_state -> market_surface_history`로 materialize 됩니다.
- 종합 탭용 실시간 브리핑도 `market_surface_state(surface_key='SUMMARY_BRIEFING')`에 함께 저장됩니다.
- `/krx/news`는 서버 렌더 초기 payload 후 60초 same-origin polling으로 갱신됩니다.
- event API는 같은 뉴스 라우터 아래 있어도 뉴스 탭 materialization과 별도 경로입니다.

## 주요 파일 책임
- 수집 automation: `backend/src/krx/source_ingestion/cli.py`
- raw ingestion orchestration: `backend/src/krx/source_ingestion/service.py`
- 뉴스 product factory: `backend/src/krx/news/factory.py`
- 1차 batch triage AI: `backend/src/krx/news/batch_triage_ai.py`
- 2차 compare AI: `backend/src/krx/news/editorial_ai.py`
- market surface materialization: `backend/src/krx/news/service.py`
- 뉴스 탭 API: `backend/src/krx/market_news/router.py`
- 뉴스 feed/detail/event API: `backend/src/krx/news/router.py`
- 뉴스 탭 SSR entry: `frontend/src/app/krx/news/page.tsx`
- 뉴스 탭 polling route: `frontend/src/app/api/krx/news-tab/route.ts`
- polling state holder: `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`
- dashboard render: `frontend/src/krx/news/components/news-tab-dashboard.tsx`

## 저장 테이블
- `news_batch_triage`
  - 문서별 1차 판단 결과
  - `market_scope`, `primary_region`, `market_importance_prelim`, `impact_direction`, `triage_metadata_json`
  - 뉴스 대시보드 materialization은 이 테이블을 source-of-truth로 읽습니다.
- `market_surface_candidates`
  - 표면 후보 카드 read model
  - candidate payload에 compare 결과와 provenance가 같이 들어갑니다.
- `market_surface_state`
  - surface별 현재 대표 카드 상태
  - lead title, ranking, story_state, importance_label, editorial reason, AI provenance 요약이 `state_json`에 들어갑니다.
  - `SUMMARY_BRIEFING` row에는 종합 탭 실시간 브리핑 headline, summary, key points, 링크 목록이 저장됩니다.
- `market_surface_history`
  - surface 대표 카드 이력
  - lead 교체 시 `refresh`
  - lead는 같지만 metadata가 바뀌면 `metadata_update`
  - `SUMMARY_BRIEFING`도 브리핑 payload가 바뀔 때 `metadata_update` 이력을 남깁니다.

## API 표면

### `/api/news/*`
- 뉴스 탭 화면 전용 market surface API
- 제공 경로:
  - `GET /api/news/dashboard`
  - `GET /api/news/kr`
  - `GET /api/news/global`
  - `GET /api/news/disclosures`
  - `GET /api/news/header-context`
  - `GET /api/news/coverage`

### `/api/krx/news/*`
- 더 넓은 뉴스 feed/detail/search/event API
- 제공 경로:
  - `GET /api/krx/news`
  - `GET /api/krx/news/top`
  - `GET /api/krx/news/search`
  - `GET /api/krx/news/by-ticker/{ticker}`
  - `GET /api/krx/news/events/recent`
  - `GET /api/krx/news/events/company/{company_id}`

## 프런트 갱신 규칙
- `/krx/news`는 `frontend/src/app/krx/news/page.tsx`에서 SSR 초기 데이터를 받습니다.
- 열린 탭은 `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`가 60초마다 `/api/krx/news-tab`을 폴링합니다.
- same-origin route는 `frontend/src/app/api/krx/news-tab/route.ts`에서 `getNewsTabData()`를 다시 호출합니다.
- polling 실패 시 마지막 성공 payload를 유지하고 다음 주기를 기다립니다.
- `종합` 탭은 대표 카드 1개 대신 실시간 브리핑 payload를 `다문단 시장 해설 + 오늘 체크할 변수 + 근거 기사` 구조로 렌더링합니다.
- 브리핑 본문은 refresh due tick 때 갱신되고, 하단 중요 뉴스 링크는 기존 evidence URL만 사용합니다.
- 브리핑 링크는 backend에서 `http/https`만 유지합니다. 안전하지 않거나 없는 URL은 항목은 유지하되 클릭 불가 텍스트로 렌더링합니다.
- automation은 `RAW_INGESTION_SCHEDULE_MARKET_NEWS_KEYWORDS`를 기본 시장-wide query bundle로 사용해 KR 뉴스를 먼저 모읍니다.
- `한국 증시` 탭은 KR 카드를 더 크게 받아 최신 시각 순 누적 피드로 렌더링하고, 5개 단위로 페이지를 넘깁니다.
- 이 페이지네이션은 서버 pagination이 아니라 클라이언트 상태입니다. 탭 전환 시 첫 페이지로 돌아가고, polling 후 카드 수가 줄면 마지막 유효 페이지로 자동 보정합니다.

## automation 규칙
- 운영 진입점은 `python3 -m src.krx.source_ingestion.cli run-news-automation` 입니다.
- 이 명령은 1분 cron tick으로 호출하되 내부에서 실제 due 여부를 계산합니다.
- cadence:
  - 장중: 1분
  - 장 종료 직후: 5분
  - 비장중: 10분
- holiday override는 `RAW_INGESTION_AUTOMATION_HOLIDAY_DATES`로 제어합니다.
- due tick이면 `sync -> normalize -> refresh`를 순서대로 수행합니다.
- 기본 normalize는 `RAW_INGESTION_AUTOMATION_NORMALIZE_INCLUDE_LLM=false`라서 deterministic event freshness만 유지합니다.

## AI 사용 규칙

### 1차 batch triage
- env:
  - `NEWS_PRODUCT_BATCH_TRIAGE_ENABLED`
  - `NEWS_PRODUCT_BATCH_TRIAGE_PROVIDER`
  - `NEWS_PRODUCT_BATCH_TRIAGE_BASE_URL`
  - `NEWS_PRODUCT_BATCH_TRIAGE_API_KEY`
  - `NEWS_PRODUCT_BATCH_TRIAGE_MODEL`
  - `NEWS_PRODUCT_BATCH_TRIAGE_TIMEOUT_SECONDS`
  - `NEWS_PRODUCT_BATCH_TRIAGE_MAX_RETRIES`
  - `NEWS_PRODUCT_BATCH_TRIAGE_BACKOFF_SECONDS`
  - `NEWS_PRODUCT_BATCH_TRIAGE_BATCH_SIZE`
  - `NEWS_PRODUCT_BATCH_TRIAGE_UPGRADE_LEGACY_ROWS`
- 역할:
  - 누락 row와 provenance 없는 legacy row를 짧은 배치로 묶어 1회 호출합니다.
  - 실패 시 deterministic triage로 fallback 합니다.

### 2차 compare AI
- env:
  - `NEWS_PRODUCT_EDITORIAL_AI_ENABLED`
  - `NEWS_PRODUCT_EDITORIAL_AI_PROVIDER`
  - `NEWS_PRODUCT_EDITORIAL_AI_BASE_URL`
  - `NEWS_PRODUCT_EDITORIAL_AI_API_KEY`
  - `NEWS_PRODUCT_EDITORIAL_AI_MODEL`
  - `NEWS_PRODUCT_EDITORIAL_AI_TIMEOUT_SECONDS`
  - `NEWS_PRODUCT_EDITORIAL_AI_MAX_RETRIES`
  - `NEWS_PRODUCT_EDITORIAL_AI_BACKOFF_SECONDS`
  - `NEWS_PRODUCT_EDITORIAL_AI_CANDIDATE_LIMIT`
  - `NEWS_PRODUCT_EDITORIAL_AI_MIN_EDITORIAL_SCORE`
- 역할:
  - 현재 표면과 top 후보를 한 번에 compare 합니다.
  - `story_state`, `importance_label`, `editorial_reason`, `editorial_boost`, `confidence`를 candidate payload에 반영합니다.
  - 같은 provider 설정을 재사용해 종합 탭용 실시간 브리핑 headline/summary/key points도 생성합니다.

## 로컬 확인
```bash
PYTHONPYCACHEPREFIX=/tmp/pycache python3 -m compileall -q backend/src
cd backend && pytest -q tests/test_market_news_product.py
cd backend && pytest -q tests/test_api.py
pnpm --filter frontend test -- src/app/krx/news/page.test.tsx src/krx/news/components/news-tab-live-dashboard.test.tsx
```

## 혼동하기 쉬운 경계
- `event_service.py`는 뉴스 탭이 아니라 event API용 정규화 경로입니다.
- `/api/news/*`는 market surface API이고 `/api/krx/news/*`는 feed/detail/event API입니다.
- `news_batch_triage`는 현재 source-of-truth이고, 설계 문서의 예전 `normalized_events -> news_cards` 설명보다 우선합니다.

## 남은 known gap
- story continuity가 여전히 `cluster_key` 중심이라 날짜/스코프가 바뀌면 같은 흐름도 새 이야기처럼 보일 수 있습니다.
- 휴장일 캘린더는 자동 동기화가 아니라 운영자가 날짜를 넣는 방식입니다.
