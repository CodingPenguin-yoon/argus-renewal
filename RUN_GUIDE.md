# Argus Renewal 실행 가이드

## 1. 의존성 설치

```bash
pnpm install

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

## 2. 환경 변수

```bash
cp .env.example backend/.env
cat > frontend/.env.local <<'ENV'
BACKEND_BASE_URL=http://localhost:4000
ENV
```

KIS 실데이터 smoke를 하려면 `backend/.env`에 `KIS_APP_KEY`, `KIS_APP_SECRET`만 채웁니다. token 값은 직접 넣지 않습니다.

뉴스 AI 판단을 Gemini로 돌리려면 `backend/.env`에 아래 값만 채웁니다.

```bash
ARGUS_NEWS_AI_PROVIDER=gemini
ARGUS_GEMINI_MODEL=gemini-2.5-flash
ARGUS_GEMINI_API_KEY=...
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

이미 `GEMINI_MODEL`, `GEMINI_API_KEY` 이름으로 저장돼 있어도 fallback으로 읽습니다.

## 3. 개발 서버

```bash
source .venv/bin/activate
pnpm dev
```

`pnpm dev`는 backend API, frontend, market collector, news collector를 함께 실행합니다. 개별 실행이 필요하면 아래 명령을 각각 사용합니다.

```bash
pnpm dev:backend
pnpm dev:frontend
pnpm dev:collector:market
pnpm dev:collector:news
```

- backend: `http://localhost:4000`
- frontend: `http://localhost:3000`

## 4. 확인 경로

- 시장 판단: `http://localhost:3000/argus`
- 옵션·선물: `http://localhost:3000/argus/derivatives`
- 옵션 시세표: `http://localhost:3000/argus/derivatives/option-quotes`
- 당일 옵션 풋콜 레이어: `http://localhost:3000/argus/derivatives/option-layer`
- 주체별 포지션: `http://localhost:3000/argus/derivatives/positions`
- 현물 반응: `http://localhost:3000/argus/reaction`
- 뉴스 분석 메인: `http://localhost:3000/argus/triggers`
- 실시간 뉴스: `http://localhost:3000/argus/triggers/news`
- API: `http://localhost:4000/api/argus/v2/dashboard`
- 옵션 시세표 API: `http://localhost:4000/api/argus/v2/option-quotes`
- 뉴스 피드 API: `http://localhost:4000/api/argus/v2/news-feed`

## 5. KIS Smoke

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

## 6. 현물/뉴스 컨텍스트 수집

```bash
cd backend
python3 -m src.argus_v2.cli collect-context
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis
python3 -m src.argus_v2.cli collect-context --news-triggers-provider rss
python3 -m src.argus_v2.cli collect-context --news-triggers-provider naver
python3 -m src.argus_v2.cli collect-context --news-triggers-provider dart
python3 -m src.argus_v2.cli collect-context --news-triggers-provider macro
```

세션-aware 1회 수집:

```bash
python3 -m src.argus_v2.cli collect-once
python3 -m src.argus_v2.cli collect-once --market-only
python3 -m src.argus_v2.cli collect-once --news-only
python3 -m src.argus_v2.cli collect-loop --interval-seconds 60
```

`collect-once`는 정규장 market 수집과 24시간 뉴스 수집을 분리합니다. 야간 파생은 `ARGUS_COLLECTOR_NIGHT_MARKET_ENABLED=true`일 때만 market 세션으로 취급합니다.

배포에서는 backend API와 collector를 별도 프로세스로 띄웁니다. Docker Compose/systemd 예시는 `doc/operations/deployment-collectors.md`에 있습니다.

## 7. 뉴스 AI Smoke

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

## 8. MVP 폐쇄 루프

Gemini key가 들어간 상태에서 아래 순서로 확인합니다.

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

화면:

```text
http://localhost:3000/argus
http://localhost:3000/argus/triggers
http://localhost:3000/argus/triggers/news
```

## 9. 검증

```bash
pnpm --filter frontend lint
pnpm --filter frontend test -- --runInBand
pnpm --filter frontend build

cd backend
pytest -q
```
