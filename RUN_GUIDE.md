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
ARGUS_GEMINI_MODEL=gemini-3-flash
ARGUS_GEMINI_API_KEY=...
```

이미 `GEMINI_MODEL`, `GEMINI_API_KEY` 이름으로 저장돼 있어도 fallback으로 읽습니다.

## 3. 개발 서버

```bash
source .venv/bin/activate
pnpm dev:backend
```

```bash
pnpm dev:frontend
```

- backend: `http://localhost:4000`
- frontend: `http://localhost:3000`

## 4. 확인 경로

- 시장 판단: `http://localhost:3000/argus`
- 옵션·선물: `http://localhost:3000/argus/derivatives`
- 현물 반응: `http://localhost:3000/argus/reaction`
- 뉴스 트리거: `http://localhost:3000/argus/triggers`
- API: `http://localhost:4000/api/argus/v2/dashboard`

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
```

## 9. 검증

```bash
pnpm --filter frontend lint
pnpm --filter frontend test -- --runInBand
pnpm --filter frontend build

cd backend
pytest -q
```
