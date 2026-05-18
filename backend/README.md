# Backend

FastAPI 기반 Argus v2 백엔드입니다. 현재 런타임 surface는 `/api/argus/v2/dashboard`, `/api/argus/v2/futures`, `/api/argus/v2/option-quotes`, `/api/argus/v2/news-feed`, `/health`입니다.

## Run

```bash
cd backend
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 4000
```

환경 변수는 루트 `.env.example`을 기준으로 `backend/.env`에 둡니다.

## API

- `GET /health`
- `GET /api/argus/v2/dashboard`
- `GET /api/argus/v2/futures`
- `GET /api/argus/v2/option-quotes`
- `GET /api/argus/v2/news-feed`

## Storage

SQLite 마이그레이션은 `src/argus_v2/migrations/`에서 관리합니다.

- `argus_v2_provider_runs`
- `argus_v2_provider_samples`
- `argus_v2_derivatives_snapshots`
- `argus_v2_futures_investor_flow_snapshots`
- `argus_v2_option_chain_snapshots`
- `argus_v2_option_chain_levels`
- `argus_v2_market_reaction_snapshots` including KOSPI/KOSDAQ reaction and spot investor flow
- `argus_v2_market_reaction_sectors`
- `argus_v2_news_triggers`
- `argus_v2_news_feed_items`

## KIS Smoke

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

KIS access token은 `KIS_APP_KEY`, `KIS_APP_SECRET`으로 발급하고 `data/kis_token_cache.json`에만 캐시합니다.

## Context Collection

```bash
cd backend
python3 -m src.argus_v2.cli collect-context
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis
python3 -m src.argus_v2.cli collect-context --news-triggers-provider rss
python3 -m src.argus_v2.cli collect-context --news-triggers-provider naver
python3 -m src.argus_v2.cli collect-context --news-triggers-provider dart
python3 -m src.argus_v2.cli collect-context --news-triggers-provider macro
python3 -m src.argus_v2.cli collect-context --news-triggers-provider hybrid
```

## Session-aware Collection

`collect-once`는 현재 KST 세션을 판정한 뒤 market/news 수집을 분리해서 1회 실행합니다. 정규장 market 수집은 기본 enabled, 야간 파생 수집은 기본 disabled, 뉴스 수집은 장외/휴일에도 enabled입니다.

```bash
cd backend
python3 -m src.argus_v2.cli collect-once
python3 -m src.argus_v2.cli collect-once --market-only
python3 -m src.argus_v2.cli collect-once --news-only
python3 -m src.argus_v2.cli collect-once --force-market
python3 -m src.argus_v2.cli collect-loop --interval-seconds 60
```

세션 설정은 `ARGUS_COLLECTOR_REGULAR_START`, `ARGUS_COLLECTOR_REGULAR_END`, `ARGUS_COLLECTOR_NIGHT_START`, `ARGUS_COLLECTOR_NIGHT_END`를 사용합니다. `ARGUS_COLLECTOR_NIGHT_MARKET_ENABLED=true`를 켜면 야간 파생 세션 수집을 별도 활성화할 수 있습니다. 임시 휴장일은 `ARGUS_MARKET_HOLIDAYS=YYYY-MM-DD,...`로 보정합니다.
같은 DB에서 동일 collector가 중복 실행되면 `argus_v2_collector_leases` lease로 뒤에 뜬 프로세스가 `skipped` 처리됩니다.

루트 스크립트:

```bash
pnpm dev:collector:market
pnpm dev:collector:news
```

`collect-once`와 `collect-loop`의 뉴스 경로는 시장 판단용 `v2_news_triggers`와 원천 뉴스용 `v2_news_feed`를 분리해 저장합니다. `/api/argus/v2/news-feed`는 저장된 원천 뉴스가 있으면 DB를 먼저 읽고, 없을 때만 live provider를 직접 호출합니다.

배포 예시는 `doc/operations/deployment-collectors.md`를 참고합니다.

현물 반응은 `mock`, `file`, `kis`, 뉴스 트리거와 원천 뉴스 피드는 `mock`, `file`, `rss`, `naver`, `dart`, `macro`, `hybrid` provider를 지원합니다. KIS 현물 수급은 `ARGUS_MARKET_REACTION_INVESTOR_AMOUNT_MULTIPLIER`로 KRW 정규화합니다. KIS 옵션체인 거래대금은 `KIS_OPTION_CHAIN_TRADING_VALUE_MULTIPLIER`로 KRW 정규화합니다. 선물 투자자별 수급은 별도 원천을 `KIS_FUTURES_INVESTOR_FLOW_PROVIDER=file|api`로 연결하면 `KIS_FUTURES_INVESTOR_FLOW_AMOUNT_MULTIPLIER`로 KRW 정규화합니다. `macro`를 쓰려면 `ARGUS_MACRO_EVENTS_PROVIDER=mock` 또는 `file`을 설정합니다.

실뉴스의 호악재/중요도/연결강도는 키워드 규칙으로 판정하지 않습니다. Gemini는 `ARGUS_NEWS_AI_PROVIDER=gemini`, `ARGUS_GEMINI_MODEL=gemini-2.5-flash`, `ARGUS_GEMINI_API_KEY`를 설정했을 때 AI 구조화 JSON으로 트리거를 선별합니다. OpenAI-compatible provider는 `ARGUS_NEWS_AI_PROVIDER=openai`, `ARGUS_NEWS_AI_MODEL`, `ARGUS_NEWS_AI_API_KEY`를 사용합니다. AI가 꺼져 있으면 RSS/Naver/DART 원문은 수집하되 임의 판단으로 노출하지 않습니다.

`/api/argus/v2/news-feed`는 AI 선별을 거치지 않은 원천 뉴스 피드를 반환합니다. 기본 `ARGUS_NEWS_FEED_PROVIDER=rss`는 API 키 없이 동작하고, `ARGUS_NEWS_FEED_RSS_URLS`가 비어 있으면 `ARGUS_NEWS_TRIGGERS_RSS_URLS`를 재사용합니다.

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

## Validation

```bash
cd backend
pytest -q
python3 -m compileall src
```
