# Argus Renewal 프로젝트 구조

현재 리포지토리에 실제로 존재하는 디렉터리와 주요 역할만 정리한 문서입니다.

## 개요
- 프런트엔드: Next.js App Router 기반 KRX 해석형 웹앱
- 백엔드: FastAPI 기반 API 서버와 KRX 운영 파이프라인
- 문서: 제품 런북, 구조 문서, 리스크 분석, Codex 운영 프롬프트

## 루트 구조
```text
argus_renewal/
├── AGENTS.md
├── .codex/
├── frontend/
├── backend/
├── scripts/
├── doc/
├── README.md
├── RUN_GUIDE.md
├── package.json
├── pnpm-workspace.yaml
├── pnpm-lock.yaml
└── .env.example
```

## Frontend 구조
```text
frontend/
├── src/app/
│   ├── page.tsx                  # / -> /krx 리다이렉트
│   ├── layout.tsx
│   └── krx/
│       ├── layout.tsx            # KRX 공통 레이아웃
│       ├── page.tsx              # /krx
│       ├── news/page.tsx         # /krx/news
│       ├── global-events/page.tsx
│       ├── derivatives/page.tsx
│       └── watchlist/page.tsx
├── src/krx/
│   ├── components/               # 화면 컴포넌트
│   ├── server/                   # 공통 서버 데이터 결합 계층
│   ├── market/server/            # 종목 데이터
│   ├── market-signal/server/     # 시장 신호 데이터
│   ├── derivatives/server/       # 파생상품 데이터
│   ├── news/server/              # 뉴스 탭 데이터
│   ├── global-events/server/     # 글로벌 이벤트 데이터
│   ├── lib/                      # env, 유틸, 탭 규칙, 스토리지
│   └── types/                    # 도메인 타입
├── src/test/
├── package.json
└── README.md
```

## Backend 구조
```text
backend/
├── src/main.py                   # FastAPI 진입점
├── src/config/env.py             # 환경 변수와 기능 토글
├── src/domains/health/           # 헬스체크
├── src/krx/
│   ├── app.py
│   ├── router.py                 # /api/krx 집계 라우터
│   ├── app_header/               # /api/app/header
│   ├── market/                   # 종목, watchlist 기반 데이터
│   ├── market_signal/            # /api/krx/market-signal/*
│   ├── derivatives/              # /api/krx/derivatives/*
│   ├── news/                     # /api/krx/news/*
│   ├── market_news/              # /api/news/*
│   ├── global_events/            # /api/global-events/*
│   ├── source_ingestion/         # 원문 수집, 이벤트 정규화, 브리핑, 동기화
│   └── company_master/           # 회사 마스터, 매핑, 마이그레이션
├── src/shared/
├── tests/
├── requirements.txt
├── pytest.ini
└── README.md
```

## 주요 사용자 경로
- `/` -> `/krx`
- `/krx`: 시장 신호 메인
- `/krx/news`: 뉴스 탭
- `/krx/global-events`: 글로벌 이벤트 탭
- `/krx/watchlist`: 관심종목

## 주요 API 경로
- `GET /health`
- `GET /api/app/header`
- `GET /api/news/*`
- `GET /api/global-events/*`
- `GET /api/krx/*`

## 현재 구조를 읽는 팁
- 디렉터리 구조는 이 문서에서 본다.
- 실제 실행 경로는 `architecture/current-system-map.md`에서 본다.
- 어디부터 점검할지는 `analysis/risk-priority.md`에서 본다.
- 운영 세부 규칙은 각 런북 문서를 본다.

## 주의
- 이 문서는 존재하는 주요 경로만 유지하고, 세부 파일을 모두 나열하지 않는다.
- 구조가 바뀌면 이 문서와 `architecture/current-system-map.md`를 함께 갱신한다.
