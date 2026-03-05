# Frontend

Next.js(App Router) 기반 금융 뉴스 웹 앱입니다.

## 실행
```bash
pnpm --filter frontend dev
```

## DB 초기화/시드
```bash
pnpm --filter frontend db:generate
pnpm --filter frontend db:init
pnpm --filter frontend db:seed
```

## 검증
```bash
pnpm --filter frontend lint
pnpm --filter frontend test
pnpm --filter frontend build
```
