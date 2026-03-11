# Argus Renewal 실행 가이드

## 0) 사전 요구사항
- Node.js 20+
- `pnpm`
- Python 3.10+

## 1) 워크스페이스 의존성 설치
```bash
pnpm install
```

## 2) Python 가상환경(venv) 생성 및 백엔드 의존성 설치
```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

## 3) 환경 변수 준비
```bash
cp .env.example backend/.env
cat > frontend/.env.local <<'ENV'
BACKEND_BASE_URL=http://localhost:4000
ENV
```

## 4) 개발 서버 실행
```bash
source .venv/bin/activate
pnpm dev:backend
```

```bash
pnpm dev:frontend
```

- backend: `http://localhost:4000`
- frontend: `http://localhost:3000`

## 5) 동작 확인
- `http://localhost:3000/krx`
- `http://localhost:3000/krx/news`
- `http://localhost:3000/krx/global-events`

## 6) 검증 명령
```bash
source .venv/bin/activate
pnpm lint
pnpm test
pnpm build
```

작업 종료 후:
```bash
deactivate
```
