# 백엔드 API와 계약

## 역할

backend API는 frontend와 backend 내부 구현 사이의 경계입니다.

frontend는 DB 테이블, KIS 응답, RSS XML, Gemini 응답을 직접 알지 않습니다. frontend는 FastAPI가 내려주는 Pydantic 계약만 신뢰합니다.

현재 API surface:

```text
GET /health
GET /api/argus/v2/dashboard
GET /api/argus/v2/news-feed
```

## 주요 파일

```text
backend/src/main.py
backend/src/argus_v2/api/router.py
backend/src/argus_v2/contracts.py
frontend/src/argus_v2/contracts/dashboard.ts
frontend/src/argus_v2/server/dashboard.ts
```

## `/api/argus/v2/dashboard`

### 목적

시장 판단 화면 전체가 필요한 데이터를 한 번에 내려줍니다.

응답 모델:

```text
MarketDashboard
```

포함 영역:

- `as_of`
- `session_phase`
- `derivatives`
- `triggers`
- `reaction`
- `judgement`
- `provider_health`

### 처리 흐름

```text
request
-> get_settings()
-> get_connection(settings.db_path)
-> build_dashboard_from_storage(ArgusV2Storage(connection))
   -> DB 최신 snapshot 조회
   -> DerivativesPressure 구성
   -> TriggerEvent 구성
   -> MarketReaction 구성
   -> ProviderHealth 구성
   -> build_market_judgement()
-> live_dashboard가 있으면 반환
-> DB가 비어 있으면 build_mock_dashboard_inputs()
-> mock 기반 judgement 생성 후 반환
```

### fallback 조건

DB에 아래 데이터가 모두 없으면 mock dashboard로 fallback합니다.

- derivatives snapshot
- option chain snapshot
- market reaction snapshot
- news trigger

mock fallback은 로컬 실행성과 UI 개발을 위한 장치입니다.

## `/api/argus/v2/news-feed`

### 목적

`뉴스 분석 > 뉴스` 화면이 보는 원천 뉴스 피드 API입니다.

응답 모델:

```text
NewsFeedResponse
```

포함 영역:

- `as_of`
- `provider`
- `status`
- `observed_count`
- `error`
- `items`

### 처리 흐름

```text
request
-> get_settings()
-> ArgusNewsTriggerService 생성
   - provider = ARGUS_NEWS_FEED_PROVIDER
   - rss_urls = ARGUS_NEWS_FEED_RSS_URLS or ARGUS_NEWS_TRIGGERS_RSS_URLS
   - query = ARGUS_NEWS_FEED_QUERY or ARGUS_NEWS_TRIGGERS_QUERY
   - limit = ARGUS_NEWS_FEED_LIMIT
-> fetch_feed()
   -> 외부 source에서 raw records fetch
   -> AI enrichment 없이 dedupe/sort/limit
-> NewsFeedItem으로 변환
-> NewsFeedResponse 반환
```

### dashboard trigger와 다른 점

`news-feed`는 AI 판단 결과가 아닙니다.

```text
dashboard.triggers
-> AI enrichment
-> should_use=true
-> impact/connection_strength/ai_reason 포함

news-feed.items
-> AI enrichment 없음
-> title/summary/source/published_at/source_url 중심
```

## Backend Pydantic 계약

파일:

```text
backend/src/argus_v2/contracts.py
```

### 공통 타입

```text
FreshnessStatus = fresh | partial | stale | missing
DirectionTone = positive | neutral | negative
OptionPressureSide = CALL | PUT | NEUTRAL | UNKNOWN
ConnectionStrength = strong | medium | weak | unclear
ConfidenceLevel = low | medium | high
```

### `DataPoint`

단일 숫자/문자 데이터의 공통 포맷입니다.

```text
value
unit
source
observed_at
freshness
```

예:

- KOSPI 변화율
- basis
- PCR
- 외국인 현물 순매수
- 상승 종목 수

### `DerivativesPressure`

옵션·선물 화면과 판단 엔진이 보는 파생 압력입니다.

주요 필드:

- 외국인/기관/개인 선물 수급
- basis
- put/call ratio
- open interest change
- KOSPI200 futures change rate
- option pressure
- option open interest change
- key levels
- summary
- freshness

주의:

현재 KOSPI200 시장 전체 선물 투자자별 수급 endpoint는 공식 확인 전입니다. 그래서 외국인/기관/개인 선물 수급은 미수신 상태가 될 수 있습니다.

### `TriggerEvent`

시장 판단에 사용되는 뉴스/매크로 trigger입니다.

주요 필드:

- `id`
- `title`
- `summary`
- `impact`
- `source`
- `published_at`
- `connection_strength`
- `ai_reason`
- `ai_confidence`
- `affected_factors`
- `freshness`

이 계약은 AI enrichment를 거친 항목을 표현합니다.

### `NewsFeedItem`

원천 뉴스 피드용 항목입니다.

주요 필드:

- `id`
- `title`
- `summary`
- `source`
- `published_at`
- `source_url`
- `freshness`

이 계약에는 `impact`, `ai_reason`, `connection_strength`가 없습니다. 원천 뉴스는 아직 시장 판단으로 확정되지 않았기 때문입니다.

### `MarketReaction`

현물 반응과 섹터 흐름입니다.

주요 필드:

- KOSPI/KOSDAQ 변화율
- KOSPI200 futures 변화율
- 상승/하락 종목 수
- 외국인/기관/개인 현물 순매수
- 강한 섹터
- 약한 섹터
- summary
- freshness

### `MarketJudgement`

판단 엔진 결과입니다.

주요 필드:

- `label`: 5단계 시장 판단
- `summary`
- `primary_driver`
- `confidence`
- `data_reliability`
- `reasons`
- `counter_evidence`
- `transition_condition`
- `watch_points`
- `source`

## Frontend Zod 계약

파일:

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

frontend는 backend 응답을 그대로 믿지 않고 Zod schema로 검증합니다.

이유:

- backend와 frontend 계약 불일치를 빠르게 발견
- 화면에서 undefined/null 오류 방지
- 테스트 fixture가 실제 계약과 맞도록 유지

현재 frontend schema:

- `marketDashboardSchema`
- `newsFeedResponseSchema`

## API 호출 wrapper

파일:

```text
frontend/src/argus_v2/server/dashboard.ts
```

제공 함수:

```text
getArgusV2Dashboard()
getArgusV2NewsFeed()
```

역할:

- `BACKEND_BASE_URL` 정리
- `fetch(..., { cache: "no-store" })`
- HTTP error 처리
- Zod parse

## 계약 변경 시 체크리스트

계약을 바꿀 때는 아래를 같이 수정해야 합니다.

1. `backend/src/argus_v2/contracts.py`
2. API router 또는 dashboard builder
3. `frontend/src/argus_v2/contracts/dashboard.ts`
4. frontend component
5. test fixture
6. README 또는 architecture 문서

계약 변경 후 최소 검증:

```bash
pytest -q backend/tests
pnpm --filter frontend test
pnpm --filter frontend lint
pnpm --filter frontend build
```
