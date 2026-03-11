# Frontend

Next.js(App Router) 기반 KRX 해석 웹 앱입니다.
데이터는 백엔드 API를 통해 조회합니다.

```text
src/
  app/
    krx/
  krx/
    components/
    lib/
    types/
    news/server/
    market/server/
    market-signal/server/
    global-events/server/
    server/
```

## 환경 변수
```bash
BACKEND_BASE_URL=http://localhost:4000
```

## 실행
```bash
pnpm --filter frontend dev
```

## 주요 경로
- `/krx` 시장 신호
- `/krx/news` 뉴스
- `/krx/global-events` 글로벌 이벤트
- `/krx/watchlist` 관심종목(보조)

## 검증
```bash
pnpm --filter frontend lint
pnpm --filter frontend test
pnpm --filter frontend build
```
