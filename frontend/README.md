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
- `/krx/dashboard` 대시보드
- `/krx/insights` AI 인사이트
- `/krx` 시장 신호
- `/krx/news` 시장 뉴스
- `/krx/macro-calendar` 매크로 캘린더
- `/krx/watchlist` 관심종목(보조)

호환 redirect:
- `/krx/overview` -> `/krx/dashboard`
- `/krx/macro` -> `/krx/insights`
- `/krx/global-events` -> `/krx/macro-calendar`

## 성능 정책
- `/krx/news`는 `force-dynamic`과 클라이언트 폴링을 유지합니다.
- 시장 신호와 파생 관련 `/api/krx/*` fetch, `AI 인사이트`의 macro news fetch는 30초 재검증을 사용합니다.
- 상단 GNB는 안정 탭만 적극 prefetch하고 `시장 뉴스`는 prefetch하지 않습니다.

## 검증
```bash
pnpm --filter frontend lint
pnpm --filter frontend test
pnpm --filter frontend build
```

## 관련 문서
- `../doc/architecture/README.md`
- `../doc/architecture/implementation-status.md`
- `../doc/architecture/system-map.md`
- `../doc/architecture/krx-mvp-ia.md`
- `../doc/troubleshooting/README.md`
