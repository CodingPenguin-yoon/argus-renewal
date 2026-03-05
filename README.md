# Argus Renewal Monorepo

- `frontend`: Next.js 금융 뉴스 웹
- `backend`: Python(FastAPI) 도메인 기반 API 서버

## 1) 설치
```bash
pnpm install
python3 -m pip install -r backend/requirements.txt
```

## 2) DB 준비 (frontend)
```bash
pnpm --filter frontend db:generate
pnpm --filter frontend db:init
pnpm --filter frontend db:seed
```

## 3) 개발 서버
```bash
pnpm dev:backend   # http://localhost:4000
pnpm dev:frontend  # http://localhost:3000
```

## 4) 검증
```bash
pnpm lint
pnpm test
pnpm build
```
