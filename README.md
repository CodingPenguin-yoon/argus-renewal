# Argus Renewal Monorepo

KRX 해석형 MVP를 위한 모노레포입니다.
핵심 UX는 `시장 신호 / 뉴스 / 글로벌 이벤트` 3개 탭입니다.

## 구성
- `frontend`: Next.js App Router
- `backend`: FastAPI + SQLite
- `scripts`: lint/운영 스크립트
- `doc`: 런북/운영 문서

## 주요 경로
- `http://localhost:3000/krx`
- `http://localhost:3000/krx/news`
- `http://localhost:3000/krx/global-events`
- `http://localhost:3000/krx/watchlist` (보조)

## 실행
```bash
pnpm install

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt

cp .env.example backend/.env
cat > frontend/.env.local <<'ENV'
BACKEND_BASE_URL=http://localhost:4000
ENV

pnpm dev:backend
pnpm dev:frontend
```

## 검증
```bash
pnpm lint
pnpm test
pnpm build
```

## 문서
- 실행/설치: `RUN_GUIDE.md`
- 프론트 상세: `frontend/README.md`
- 백엔드 상세: `backend/README.md`
- KRX MVP IA: `doc/krx_mvp_ia_runbook.md`
