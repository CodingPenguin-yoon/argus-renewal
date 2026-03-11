# Argus Renewal 프로젝트 구조

## 개요

금융 뉴스 웹 애플리케이션을 위한 모노레포 프로젝트입니다.
- **Frontend**: Next.js App Router 기반 웹앱
- **Backend**: Python FastAPI 기반 API 서버

---

## 디렉토리 구조

```
argus_renewal/
├── frontend/                 # Next.js 프론트엔드
├── backend/                  # Python FastAPI 백엔드
├── doc/                      # 프로젝트 문서
├── package.json              # 루트 패키지 (워크스페이스 스크립트)
├── pnpm-workspace.yaml       # pnpm 워크스페이스 설정
├── pnpm-lock.yaml            # 의존성 락 파일
├── agent.md                  # 프로젝트 가이드라인
├── README.md                 # 프로젝트 소개
└── .gitignore
```

---

## Frontend 구조 (`frontend/`)

```
frontend/
├── prisma/                   # 데이터베이스 스키마
│   ├── schema.prisma         # Prisma 스키마 정의
│   ├── init.sql              # 초기화 SQL
│   └── seed.ts               # 시드 데이터
├── public/                   # 정적 파일 (SVG 아이콘 등)
├── src/
│   ├── app/                  # Next.js App Router 페이지
│   │   ├── layout.tsx        # 루트 레이아웃
│   │   ├── page.tsx          # 메인 페이지 (/)
│   │   ├── loading.tsx       # 로딩 UI
│   │   ├── error.tsx         # 에러 UI
│   │   ├── not-found.tsx     # 404 페이지
│   │   ├── globals.css       # 전역 스타일
│   │   ├── news/
│   │   │   └── [id]/page.tsx # 뉴스 상세 페이지
│   │   ├── stocks/
│   │   │   └── [ticker]/page.tsx  # 종목 상세 페이지
│   │   └── watchlist/
│   │       └── page.tsx      # 관심 종목 페이지
│   ├── components/           # 리액트 컴포넌트
│   │   ├── layout/           # 레이아웃 컴포넌트
│   │   │   ├── app-shell.tsx
│   │   │   ├── top-nav.tsx
│   │   │   └── disclaimer-banner.tsx
│   │   ├── news/             # 뉴스 관련 컴포넌트
│   │   │   ├── home-dashboard.tsx
│   │   │   ├── news-card.tsx
│   │   │   └── event-card.tsx
│   │   ├── stocks/           # 종목 관련 컴포넌트
│   │   │   ├── stock-detail.tsx
│   │   │   └── stock-timeline.tsx
│   │   ├── search/           # 검색 컴포넌트
│   │   │   └── search-box.tsx
│   │   ├── watchlist/        # 관심 종목 컴포넌트
│   │   │   └── watchlist-manager.tsx
│   │   └── ui/               # 공통 UI 컴포넌트
│   │       ├── badge.tsx
│   │       ├── empty-state.tsx
│   │       ├── error-state.tsx
│   │       ├── filter-bar.tsx
│   │       ├── loading-state.tsx
│   │       └── section-header.tsx
│   ├── lib/                  # 유틸리티 및 비즈니스 로직
│   │   ├── providers/        # 데이터 제공자 (Provider 패턴)
│   │   │   ├── interfaces.ts
│   │   │   ├── index.ts
│   │   │   ├── mock-news-provider.ts
│   │   │   ├── mock-stock-provider.ts
│   │   │   └── mock-market-event-provider.ts
│   │   ├── analysis/         # 분석 로직
│   │   │   ├── heuristics.ts
│   │   │   └── __tests__/
│   │   ├── server/           # 서버 전용 유틸리티
│   │   │   └── data-service.ts
│   │   ├── mock/             # 목업 데이터
│   │   │   └── seed-data.ts
│   │   ├── __tests__/        # 유틸리티 테스트
│   │   ├── constants.ts      # 상수
│   │   ├── env.ts            # 환경변수
│   │   ├── prisma.ts         # Prisma 클라이언트
│   │   ├── utils.ts          # 헬퍼 함수
│   │   └── watchlist-storage.ts  # 관심종목 저장 로직
│   ├── types/                # TypeScript 타입 정의
│   │   └── domain.ts         # 도메인 타입
│   └── test/                 # 테스트 설정
│       └── setup.ts
├── eslint.config.mjs         # ESLint 설정
├── next.config.ts            # Next.js 설정
├── postcss.config.mjs        # PostCSS 설정
├── prisma.config.ts          # Prisma 설정
├── package.json
└── README.md
```

---

## Backend 구조 (`backend/`)

```
backend/
├── src/
│   ├── main.py               # FastAPI 앱 진입점
│   ├── config/               # 설정
│   │   ├── __init__.py
│   │   └── env.py            # 환경변수 설정
│   ├── domains/              # 도메인별 모듈 (DDD 스타일)
│   │   ├── health/           # 헬스체크 도메인
│   │   │   ├── __init__.py
│   │   │   └── router.py
│   │   └── news/             # 뉴스 도메인
│   │       ├── __init__.py
│   │       ├── router.py     # API 라우터
│   │       ├── service.py    # 비즈니스 로직
│   │       ├── provider.py   # 데이터 제공자 인터페이스
│   │       ├── factory.py    # 팩토리 패턴
│   │       ├── news_types.py # 타입 정의
│   │       ├── providers/    # 제공자 구현체
│   │       │   ├── __init__.py
│   │       │   └── mock_provider.py
│   │       └── data/         # 목업 데이터
│   │           └── mock_news.py
│   └── shared/               # 공유 모듈
│       ├── __init__.py
│       └── errors.py         # 에러 정의
├── tests/                    # 테스트
│   └── test_api.py
├── requirements.txt          # Python 의존성
├── pytest.ini                # pytest 설정
└── README.md
```

---

## 주요 기술 스택

### Frontend
| 분류 | 기술 |
|------|------|
| 프레임워크 | Next.js 15 (App Router) |
| 언어 | TypeScript |
| 스타일링 | Tailwind CSS |
| ORM | Prisma |
| 데이터베이스 | SQLite (로컬 개발용) |
| 패키지 매니저 | pnpm |

### Backend
| 분류 | 기술 |
|------|------|
| 프레임워크 | FastAPI |
| 언어 | Python |
| 테스트 | pytest |

---

## 페이지 라우팅

| 경로 | 설명 |
|------|------|
| `/` | 메인 대시보드 (뉴스 + 이벤트) |
| `/news/[id]` | 뉴스 상세 페이지 |
| `/stocks/[ticker]` | 종목 상세 페이지 |
| `/watchlist` | 관심 종목 관리 |

---

## API 엔드포인트 (Backend)

| 경로 | 설명 |
|------|------|
| `GET /health` | 헬스체크 |
| `GET /api/news` | 뉴스 목록 조회 |

---

## 아키텍처 패턴

### Provider/Adapter 패턴
데이터 소스를 추상화하여 Mock/실제 API를 쉽게 교체할 수 있습니다.

```
interfaces.ts    → 인터페이스 정의
mock-*-provider.ts → Mock 구현체
index.ts         → Provider 팩토리
```

### 도메인 기반 구조 (Backend)
각 도메인(news, health 등)이 독립적인 모듈로 구성되어 있습니다.

```
domains/
├── news/
│   ├── router.py    → API 엔드포인트
│   ├── service.py   → 비즈니스 로직
│   ├── provider.py  → 데이터 추상화
│   └── factory.py   → 의존성 주입
```

---

## 개발 명령어

```bash
# 설치
pnpm install
pip install -r backend/requirements.txt

# DB 초기화 (frontend)
pnpm --filter frontend db:generate
pnpm --filter frontend db:init
pnpm --filter frontend db:seed

# 개발 서버
pnpm dev:backend   # http://localhost:4000
pnpm dev:frontend  # http://localhost:3000

# 검증
pnpm lint
pnpm test
pnpm build
```
