# Argus Renewal 프로젝트 구조

현재 리포지토리에 실제로 존재하는 디렉터리와 주요 역할만 정리한 문서입니다.

## 개요
- 프런트엔드: Next.js App Router 기반 KRX 해석형 웹앱
- 백엔드: FastAPI 기반 API 서버와 KRX 운영 파이프라인
- 문서: 현재 구조, 도메인 딥다이브, 계획, 참고 자료, 쉬운 설명 문서

## 루트 구조
```text
argus_renewal/
├── AGENTS.md
├── frontend/
├── backend/
├── scripts/
├── doc/
├── README.md
├── RUN_GUIDE.md
├── package.json
├── pnpm-workspace.yaml
└── .env.example
```

## Frontend 구조
```text
frontend/
├── src/app/
│   ├── page.tsx                          # / -> /krx/dashboard 리다이렉트
│   ├── layout.tsx
│   └── krx/
│       ├── layout.tsx                    # KRX 공통 레이아웃
│       ├── page.tsx                      # /krx (시장 신호)
│       ├── dashboard/page.tsx            # /krx/dashboard
│       ├── insights/page.tsx             # /krx/insights
│       ├── news/page.tsx                 # /krx/news SSR entry
│       ├── macro-calendar/page.tsx       # /krx/macro-calendar
│       ├── overview/page.tsx             # /krx/overview -> /krx/dashboard redirect
│       ├── macro/page.tsx                # /krx/macro -> /krx/insights redirect
│       ├── global-events/page.tsx        # /krx/global-events -> /krx/macro-calendar redirect
│       ├── derivatives/page.tsx          # /krx/derivatives -> /krx?subtab=derivatives redirect
│       └── watchlist/page.tsx
├── src/app/api/krx/news-tab/route.ts     # same-origin 뉴스 탭 polling route
├── src/krx/
│   ├── components/                       # 공통 화면 컴포넌트
│   ├── server/                           # 탭별 서버 데이터 결합 계층
│   ├── news/
│   │   ├── components/
│   │   │   ├── news-tab-dashboard.tsx
│   │   │   └── news-tab-live-dashboard.tsx
│   │   ├── server/data-service.ts
│   │   └── lib/
│   ├── market/
│   ├── market-signal/
│   ├── derivatives/
│   ├── global-events/
│   ├── macro/
│   ├── overview/
│   ├── lib/
│   └── types/
├── src/test/
└── package.json
```

## Backend 구조
```text
backend/
├── src/main.py                           # FastAPI 진입점
├── src/config/env.py                     # 환경 변수와 기능 토글
├── src/krx/
│   ├── app.py
│   ├── router.py                         # /api/krx 집계 라우터
│   ├── market_news/router.py             # /api/news/* 시장 표면 API
│   ├── news/
│   │   ├── router.py
│   │   ├── factory.py
│   │   ├── service.py
│   │   ├── batch_triage_ai.py
│   │   └── editorial_ai.py
│   ├── source_ingestion/
│   │   ├── cli.py
│   │   ├── service.py
│   │   ├── event_service.py
│   │   └── README.md
│   ├── company_master/
│   ├── market/
│   ├── market_signal/
│   ├── derivatives/
│   └── global_events/
├── tests/
└── README.md
```

## 문서 구조
- `doc/architecture/`: 현재 코드 사실 문서
- `doc/domains/`: 도메인별 심화 문서와 runbook
- `doc/plans/`: 현재 상태, 해결 로그, 과거 계획
- `doc/reference/`: 데이터 모델, 설계 참고
- `doc/troubleshooting/`: 비전공자용 작업 설명 문서

## 주요 사용자 경로
- `/` -> `/krx/dashboard`
- `/krx/dashboard`: 대시보드
- `/krx/insights`: AI 인사이트
- `/krx`: 시장 신호
- `/krx/news`: 시장 뉴스
- `/krx/macro-calendar`: 매크로 캘린더
- `/krx/watchlist`: 관심종목(보조)

## 호환 경로
- `/krx/overview` -> `/krx/dashboard`
- `/krx/macro` -> `/krx/insights`
- `/krx/global-events` -> `/krx/macro-calendar`
- `/krx/derivatives` -> `/krx?subtab=derivatives`

## 주요 API 경로
- `GET /health`
- `GET /api/app/header`
- `GET /api/news/*`
- `GET /api/global-events/*`
- `GET /api/krx/*`
- `GET /api/krx/news-tab` (frontend same-origin route)

## 현재 구조를 읽는 팁
- 전체 런타임 경로는 `system-map.md`
- IA와 URL 정책은 `krx-mvp-ia.md`
- 쉬운 설명 문서는 `../troubleshooting/README.md`

## 마지막 갱신
- 2026-03-16
