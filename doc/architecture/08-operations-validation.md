# 운영과 검증

## 목적

이 문서는 Argus v2를 로컬에서 실행하고, 데이터 수집/화면/API가 정상인지 확인하는 기준을 정리합니다.

## 개발 서버

Backend:

```bash
pnpm dev:backend
```

기본 주소:

```text
http://localhost:4000
```

Frontend:

```bash
pnpm dev:frontend
```

기본 주소:

```text
http://localhost:3000
```

## 주요 화면 확인 경로

```text
http://localhost:3000/argus
http://localhost:3000/argus/derivatives
http://localhost:3000/argus/reaction
http://localhost:3000/argus/triggers
http://localhost:3000/argus/triggers/news
```

## 주요 API 확인 경로

```text
http://localhost:4000/health
http://localhost:4000/api/argus/v2/dashboard
http://localhost:4000/api/argus/v2/news-feed
```

## 기본 검증 명령

Frontend:

```bash
pnpm --filter frontend test
pnpm --filter frontend lint
pnpm --filter frontend build
```

Backend:

```bash
pytest -q backend/tests
PYTHONPYCACHEPREFIX=/private/tmp/argus_pycache python3 -m compileall backend/src
```

Diff:

```bash
git diff --check
```

## Smoke 명령

KIS:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

뉴스 AI:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

현물/뉴스 context:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context
```

뉴스만:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

현물 반응만:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

## API quick check

Dashboard:

```bash
curl -sS http://localhost:4000/api/argus/v2/dashboard
```

News feed:

```bash
curl -sS http://localhost:4000/api/argus/v2/news-feed
```

Frontend route:

```bash
curl -sS -I http://localhost:3000/argus/triggers/news
```

## 정상 동작 기준

### Dashboard

정상 기준:

- 판단 label이 표시됩니다.
- confidence가 표시됩니다.
- provider health가 표시됩니다.
- 파생/옵션 요약이 표시됩니다.
- trigger 또는 empty state가 표시됩니다.
- 현물 반응 또는 empty state가 표시됩니다.

### News feed

정상 기준:

- `/api/argus/v2/news-feed`가 200을 반환합니다.
- `items` 배열이 있습니다.
- 각 item에 title/source/published_at/source_url이 있습니다.
- `/argus/triggers/news`가 200을 반환합니다.
- 화면에서 원문 링크가 보입니다.

### Provider health

정상 기준:

- provider별 상태가 `fresh`, `partial`, `stale`, `missing` 중 하나로 표시됩니다.
- 실패 시 error 또는 missing field가 표시됩니다.
- observed_count가 수신 건수를 반영합니다.

## 자주 보는 문제

### Backend dev server가 안 켜짐

확인:

- port 4000 사용 중인지
- sandbox/권한 문제인지
- backend dependencies 설치 여부

### Frontend dev server가 안 켜짐

확인:

- port 3000 사용 중인지
- `frontend/.env.local`에 `BACKEND_BASE_URL`이 있는지
- Next.js build 오류가 있는지

### Build가 Google Fonts에서 실패

Next.js `next/font/google`이 빌드 시 Google Fonts를 가져옵니다.

네트워크가 막힌 환경이면 build가 실패할 수 있습니다. 이 경우 네트워크 허용 후 다시 검증합니다.

### 뉴스 trigger가 안 보임

확인 순서:

1. `smoke-news-ai` 성공 여부
2. `ARGUS_NEWS_AI_PROVIDER`
3. Gemini/OpenAI-compatible model/key
4. `collect-context --skip-market-reaction --news-triggers-provider rss`
5. provider run metadata
6. `ai_candidate_count`
7. `ai_enriched_count`
8. `ai_selected_count`
9. `argus_v2_news_triggers`
10. `/api/argus/v2/dashboard`
11. `/argus/triggers`

AI가 `should_use=false`로 판단하면 trigger가 없어도 정상일 수 있습니다.

### 원천 뉴스 feed가 안 보임

확인 순서:

1. `/api/argus/v2/news-feed`
2. `ARGUS_NEWS_FEED_PROVIDER`
3. `ARGUS_NEWS_FEED_RSS_URLS`
4. `ARGUS_NEWS_TRIGGERS_RSS_URLS`
5. `ARGUS_NEWS_FEED_LOOKBACK_HOURS`
6. provider credential
7. `/argus/triggers/news`

원천 뉴스 feed는 AI key가 없어도 RSS 기본 provider로 동작해야 합니다.

### KIS 데이터가 안 보임

확인 순서:

1. `KIS_APP_KEY`, `KIS_APP_SECRET`
2. `smoke-kis`
3. token cache 생성 여부
4. provider run status
5. raw sample 저장 여부
6. dashboard provider health

주의:

계좌 기반 API를 시장 전체 수급으로 오해하지 않습니다.

## 장중 운영 루틴

장 시작 전:

```text
1. smoke-news-ai
2. smoke-kis
3. collect-context --market-reaction-provider kis --news-triggers-provider rss
4. /argus 확인
5. /argus/triggers 확인
6. /argus/triggers/news 확인
```

장중:

```text
1. smoke-kis 반복
2. collect-context 반복
3. provider health 확인
4. 판단 label 변화 기록
5. trigger와 현물 반응이 실제 장 흐름과 맞는지 확인
```

## 변경 후 최소 검증 기준

문서만 바꿨을 때:

```bash
git diff --check
```

frontend 계약이나 UI를 바꿨을 때:

```bash
pnpm --filter frontend test
pnpm --filter frontend lint
pnpm --filter frontend build
```

backend API/provider/storage를 바꿨을 때:

```bash
pytest -q backend/tests
PYTHONPYCACHEPREFIX=/private/tmp/argus_pycache python3 -m compileall backend/src
```

API 계약을 바꿨을 때:

```bash
pytest -q backend/tests/test_argus_v2_api.py
pnpm --filter frontend test
```
