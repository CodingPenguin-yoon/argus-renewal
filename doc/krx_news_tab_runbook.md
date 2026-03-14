# KRX News Tab Runbook

## 목적
- 뉴스 탭을 기사 피드가 아니라 이벤트 카드 중심으로 운영합니다.
- 화면에는 `한국 증시`, `글로벌 증시` 두 칼럼만 노출합니다.
- 섹터/테마 태그는 백엔드 내부 랭킹과 향후 필터링용으로만 유지하고, MVP 네비게이션에는 노출하지 않습니다.

## Provider 우선순위
- `DART`: 공식 이벤트 소스. 공시는 first-class event로 직접 승격합니다.
- `MK_RSS`: 주요 경제지 RSS source. 기사 메타데이터와 snippet을 persistent evidence로 보관합니다.
- `Naver News Search`: discovery 전용. 탐색 입력으로만 사용하고 canonical content로 취급하지 않습니다.
- `Naver Datalab`: 관심도/트렌드 점수만 공급합니다. 기사 source로 저장하지 않습니다.

## 필수/선택 환경 변수

### 기존 ingestion/provider
- `DART_API_KEY`
- `DART_MATERIAL_ONLY`
- `DART_MATERIAL_INCLUDE_PATTERNS`
- `DART_MATERIAL_EXCLUDE_PATTERNS`
- `MK_RSS_ENABLED`
- `MK_RSS_FEED_URLS`
- `NAVER_NEWS_ENABLED`
- `NAVER_NEWS_CLIENT_ID`
- `NAVER_NEWS_CLIENT_SECRET`
- `RAW_INGESTION_AUTOMATION_TIMEZONE`
- `RAW_INGESTION_AUTOMATION_WEEKDAYS`
- `RAW_INGESTION_AUTOMATION_MARKET_OPEN_TIME`
- `RAW_INGESTION_AUTOMATION_MARKET_CLOSE_TIME`
- `RAW_INGESTION_AUTOMATION_POST_CLOSE_END_TIME`
- `RAW_INGESTION_AUTOMATION_MARKET_OPEN_INTERVAL_MINUTES`
- `RAW_INGESTION_AUTOMATION_POST_CLOSE_INTERVAL_MINUTES`
- `RAW_INGESTION_AUTOMATION_OFF_HOURS_INTERVAL_MINUTES`
- `RAW_INGESTION_AUTOMATION_HOLIDAY_DATES`
- `RAW_INGESTION_AUTOMATION_REFRESH_MODE`

### 신규 attention/ranking
- `NAVER_DATALAB_ENABLED`
- `NAVER_DATALAB_CLIENT_ID`
- `NAVER_DATALAB_CLIENT_SECRET`
- `NAVER_DATALAB_BASE_URL`
- `NAVER_DATALAB_SEARCH_PATH`
- `NAVER_DATALAB_TIME_UNIT`

### 신규 materialization tuning
- `NEWS_PRODUCT_LOOKBACK_DAYS`
- `NEWS_PRODUCT_CARD_LIMIT`
- `NEWS_PRODUCT_REPRESENTATIVE_EVIDENCE_LIMIT`
- `NEWS_PRODUCT_REFRESH_TTL_SECONDS`
- `NEWS_PRODUCT_DATALAB_WINDOW_DAYS`
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

## Source Persistence Policy
- `raw_documents`
  - 수집 원천을 그대로 유지하는 입력 계층
- `news_batch_triage`
  - 뉴스/공시별 1차 시장 관련성 판단 결과
  - `market_scope`, `market_importance_prelim`, `impact_direction`를 저장
- `market_surface_candidates`
  - 메인 표면 후보 카드 read model
  - `news-card-*`, `disclosure-card-*` 안정 ID를 보관
- `market_surface_state`
  - 현재 표면 요약과 coverage 스냅샷을 저장
- `market_surface_history`
  - 표면 리프레시 이력 저장
- evidence policy
  - `DART` -> `CANONICAL_EVENT`
  - `MK_RSS` -> `PERSISTENT_EVIDENCE`
  - `NAVER_NEWS` -> `TRANSIENT_DISCOVERY`

## Ranking Logic
- score layers
  - `trust_score`: source credibility
  - `materiality_score`: 내용 영향도
  - `editorial_score`: 화면 우선순위
- 기본 점수
  - source trust (`DART` > `MK_RSS` > `NAVER_NEWS`)
  - materiality (`event_type`, `impact`, `scope`, canonical anchor 기반)
  - novelty (최근성 기반)
- 보너스
  - cross-source confirmation bonus
  - Naver Datalab attention bonus
- AI editorial enrichment
  - 상위 candidate 카드에만 optional `story_state`, `importance_label`, `editorial_reason`, `editorial_boost`를 적용
  - 실패 시 deterministic score만 사용
- 감점
  - 저품질 headline marker (`속보`, `관련주`, `급등` 등)
- 노이즈 억제
  - `company` scope 카드는 고신뢰/고랭크가 아니면 메인 탭에서 숨깁니다.

## Event Schema
- 카드 필수 필드
  - `title`
  - `one_line_summary`
  - `why_it_matters`
  - `market_impact`
  - `market_scope`
  - `primary_region`
  - `trust_score`
  - `materiality_score`
  - `novelty_score`
  - `attention_score`
  - `editorial_score`
  - `story_state`
  - `importance_label`
  - `editorial_reason`
  - `evidence`
  - `published_at`
  - `updated_at`

## 로컬 확인
```bash
cd backend
pytest -q tests/test_market_news_product.py tests/test_api.py

cd ../frontend
pnpm vitest run src/app/krx/news/page.test.tsx
```

## 운영 스케줄 방향
- canonical cron entry는 `python3 -m src.krx.source_ingestion.cli run-news-automation` 를 1분 간격으로 호출합니다.
- command 내부가 `Asia/Seoul` 기준 KRX session phase를 계산해 장중은 1분 cadence, 장 종료 후 18:00 전까지는 5분 cadence, 그 외 시간과 주말은 10분 cadence로 실제 실행 여부를 결정합니다.
- `RAW_INGESTION_AUTOMATION_HOLIDAY_DATES`에 등록된 날짜는 장중 시간이어도 off-hours cadence로 떨어집니다.
- due tick이면 raw sync(`sync-scheduled`와 동일 범위) 이후 event normalization, news product materialization refresh까지 한 번에 수행합니다.
- refresh는 `RAW_INGESTION_AUTOMATION_REFRESH_MODE`로 제어합니다.
  - `smart`: 새 source 또는 TTL 조건이 있을 때만 refresh
  - `force`: 매 due tick 강제 refresh
  - `skip`: automation refresh 생략
- due가 아니면 `SKIPPED_CADENCE` JSON만 남기고 종료합니다.

## API
- `GET /api/news/dashboard`
- `GET /api/news/kr`
- `GET /api/news/global`
- `GET /api/news/disclosures`
- `GET /api/news/header-context`
- `GET /api/news/coverage`
