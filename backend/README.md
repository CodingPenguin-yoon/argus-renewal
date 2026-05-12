# Backend

FastAPI 기반 Argus v2 백엔드입니다. 현재 런타임 surface는 `/api/argus/v2/dashboard`와 `/health`만 유지합니다.

## Run

```bash
cd backend
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 4000
```

환경 변수는 루트 `.env.example`을 기준으로 `backend/.env`에 둡니다.

## API

- `GET /health`
- `GET /api/argus/v2/dashboard`

## Storage

SQLite 마이그레이션은 `src/argus_v2/migrations/`에서 관리합니다.

- `argus_v2_provider_runs`
- `argus_v2_provider_samples`
- `argus_v2_derivatives_snapshots`
- `argus_v2_option_chain_snapshots`
- `argus_v2_option_chain_levels`
- `argus_v2_market_reaction_snapshots` including KOSPI/KOSDAQ reaction and spot investor flow
- `argus_v2_market_reaction_sectors`
- `argus_v2_news_triggers`

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

현물 반응은 `mock`, `file`, `kis`, 뉴스 트리거는 `mock`, `file`, `rss`, `naver`, `dart`, `macro`, `hybrid` provider를 지원합니다. KIS 현물 수급은 `ARGUS_MARKET_REACTION_INVESTOR_AMOUNT_MULTIPLIER`로 KRW 정규화합니다. `macro`를 쓰려면 `ARGUS_MACRO_EVENTS_PROVIDER=mock` 또는 `file`을 설정합니다.

실뉴스의 호악재/중요도/연결강도는 키워드 규칙으로 판정하지 않습니다. `ARGUS_NEWS_AI_PROVIDER=openai`, `ARGUS_NEWS_AI_MODEL`, `ARGUS_NEWS_AI_API_KEY`를 설정했을 때만 AI가 반환한 구조화 JSON으로 트리거를 선별합니다. AI가 꺼져 있으면 RSS/Naver/DART 원문은 수집하되 임의 판단으로 노출하지 않습니다.

## Validation

```bash
cd backend
pytest -q
python3 -m compileall src
```
