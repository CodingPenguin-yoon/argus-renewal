# Argus Renewal Monorepo

Argus Renewal은 한국 주식 투자자를 위한 해석형 금융 뉴스 앱 모노레포입니다.  
현재 제품 중심은 KRX MVP이며, 단순 기사 모음이 아니라 `대시보드 / AI 인사이트 / 파생·수급 / 시장 뉴스 / 매크로 캘린더` 다섯 화면이 서로 다른 질문에 답하도록 설계되어 있습니다.

## 1. 프로젝트 한눈에 보기

### 제품 방향
- 한국장 기준으로 시장을 읽는 Korean-first 금융 정보 앱
- 초급~중급 개인투자자가 `무슨 일이 있었나`보다 `그래서 지금 무엇을 봐야 하나`를 빠르게 판단할 수 있게 돕는 해석형 UX
- 외부 API 키 없이도 mock/file 기반으로 로컬 실행 가능
- provider/adapter 패턴을 유지해 뉴스, 파생, 매크로 소스를 점진적으로 교체할 수 있는 구조

### 왜 이 프로젝트를 만드는가
- 기존 금융 뉴스 앱이나 포털형 서비스는 기사 수집과 속보 전달에는 강하지만, 초급~중급 투자자가 `지금 시장을 어떻게 읽어야 하는지`까지 바로 답해주지는 못하는 경우가 많습니다.
- 한국장은 미국장, 환율, 금리, 원자재, 야간선물, 외국인 수급 같은 바깥 변수의 영향을 강하게 받는데, 이 변수들이 실제로 `한국 증시 어느 경로로 들어오는지`는 흩어진 화면에서 따로 해석해야 하는 경우가 많습니다.
- 특히 개인투자자 입장에서는 기사 headline, 실제 수급, 파생 포지션, 매크로 이벤트가 서로 같은 방향을 가리키는지 아닌지를 빠르게 구분하는 것이 어렵습니다.
- Argus Renewal은 이 문제를 `기사 모음`이 아니라 `질문 중심 정보 구조`로 풀려는 프로젝트입니다. 사용자가 화면을 옮길 때마다 서로 다른 질문에 답하게 해서, 시장 판단 과정 자체를 더 짧고 명확하게 만드는 것이 목표입니다.

### 이 프로젝트의 의의
- `정보를 더 많이 보여주는 앱`이 아니라 `판단 비용을 줄여주는 앱`을 지향합니다.
- 뉴스, 파생, 매크로를 한곳에 모으는 수준이 아니라, 각 정보가 한국장 해석에 어떤 의미를 갖는지까지 surface 수준에서 설명합니다.
- 강세/약세 같은 단정적 결론만 주는 것이 아니라, 왜 그렇게 보는지, 무엇이 반대 근거인지, 언제 해석이 무효화되는지까지 같이 드러내는 구조를 지향합니다.
- 데이터가 비어 있는 경우에도 단순 `-`로 숨기지 않고, 어떤 소스가 없고 그래서 무엇을 대신 봐야 하는지까지 알려줘 신뢰 가능한 empty state를 만드는 것을 중요한 제품 원칙으로 둡니다.
- 개발 측면에서는 mock/file 기반으로도 전체 구조를 확인할 수 있게 해, 외부 provider 연동과 무관하게 제품 surface와 정보 구조를 먼저 완성해 나갈 수 있는 실험 환경을 제공합니다.

### 누구를 위한 프로젝트인가
- 한국 주식시장을 매일 보지만 거시/파생 해석까지는 아직 익숙하지 않은 초급~중급 개인투자자
- 뉴스 headline보다 `그래서 오늘 어떤 변수부터 확인해야 하는지`가 더 중요한 사용자
- 미국장, 환율, FOMC, 유가, 외국인 선물, 공시 같은 변수가 한국장에 어떤 방식으로 전이되는지 빠르게 보고 싶은 사용자
- 제품/데이터/UX 관점에서 `해석형 금융 인터페이스`를 실험하려는 개발자와 운영자

### 무엇이 다른가
- `대시보드`는 허브, `AI 인사이트`는 해석실, `파생·수급`은 포지셔닝 보드, `시장 뉴스`는 사건 추적기, `매크로 캘린더`는 한국장용 catalyst board라는 식으로 역할을 강하게 분리합니다.
- 뉴스 탭은 단순 리스트보다 `오늘 핵심 스토리 -> 종합 브리핑 -> 신뢰 참고` 순서로 읽히게 설계합니다.
- 매크로 캘린더는 글로벌 일정 raw feed가 아니라, 한국 증시에 실제로 어떤 전이 경로를 만들 수 있는지까지 설명하는 도구를 목표로 합니다.
- `/krx`는 route를 유지하되 display label을 `파생·수급`으로 노출해, 이 프로젝트의 중심 축이 `증시 흐름 + 파생 해석`이라는 점을 더 직접적으로 전달합니다.

### 현재 핵심 UX
- `대시보드`
  - 지금 뭐가 중요한가를 먼저 답하는 60초 cockpit
- `AI 인사이트`
  - 왜 그렇게 해석하는가를 주장/근거/반대근거/무효화 조건으로 설명하는 argument room
- `파생·수급`
  - `/krx` route를 유지하면서 누가 어떤 방향으로 베팅하는지 보여주는 포지셔닝 surface
- `시장 뉴스`
  - 오늘 시장을 실제로 움직이는 사건과 스토리 continuity를 보여주는 event-first 뉴스 surface
- `매크로 캘린더`
  - 해외 일정을 한국장 관점 catalyst view로 재해석한 macro board

## 2. 현재 사용자 표면

### Canonical 경로
- `http://localhost:3000/krx/dashboard`
- `http://localhost:3000/krx/insights`
- `http://localhost:3000/krx`
- `http://localhost:3000/krx/news`
- `http://localhost:3000/krx/macro-calendar`
- `http://localhost:3000/krx/watchlist`

### Route 정책
- `/krx`는 canonical route를 유지하고 상단 display label만 `파생·수급`으로 노출합니다.
- 호환 redirect는 유지합니다.
  - `/krx/overview` -> `/krx/dashboard`
  - `/krx/macro` -> `/krx/insights`
  - `/krx/global-events` -> `/krx/macro-calendar`
  - `/krx/derivatives` -> `/krx?subtab=derivatives`

### 각 탭이 답하는 질문
- `대시보드`
  - 지금 한눈에 뭐가 중요하지?
- `AI 인사이트`
  - 왜 그렇게 봐야 하지?
- `파생·수급`
  - 누가 어떤 방향으로 베팅하고 있지?
- `시장 뉴스`
  - 오늘 시장을 실제로 움직이는 사건이 뭐지?
- `매크로 캘린더`
  - 바깥 변수가 언제 어떤 경로로 들어오지?

## 3. 저장소 구조

```text
argus_renewal/
├── frontend/             # Next.js App Router 프론트엔드
├── backend/              # FastAPI API 서버 + 수집/가공 파이프라인
├── doc/                  # 현재 구조, 도메인 런북, 계획, 참고 문서
├── scripts/              # 검증/운영 보조 스크립트
├── README.md
├── RUN_GUIDE.md
├── AGENTS.md
├── package.json
├── pnpm-workspace.yaml
└── .env.example
```

### Frontend
- Next.js App Router
- TypeScript
- Tailwind CSS
- `/src/app/krx/*` 아래에 KRX 사용자 화면 엔트리
- `/src/krx/*` 아래에 도메인별 컴포넌트, 서버 결합 계층, 타입, 유틸리티

### Backend
- FastAPI
- SQLite 로컬 개발 환경
- 뉴스 수집/정규화/시장 표면 materialization
- 파생/시장 신호/글로벌 이벤트 API
- CLI 기반 자동화 및 provider probe 유틸리티

### Docs
- `doc/architecture/`
  - 현재 코드 기준 사실 문서
- `doc/domains/`
  - 뉴스, 매크로 캘린더, 파생 등 도메인 런북
- `doc/reference/`
  - 데이터 모델, provider 설계, env 가이드
- `doc/troubleshooting/`
  - 비전공자도 읽기 쉬운 설명 문서
- `doc/plans/`
  - 진행 상태, 오픈 이슈, 과거 계획/로그

## 4. 아키텍처 요약

### 프런트엔드 렌더 구조
- App Router page는 최대한 얇게 유지합니다.
- 각 탭 page는 탭별 dashboard 컴포넌트와 서버 데이터 결합 함수에 위임합니다.
- 공통 헤더는 status shell 역할만 수행하고, 메인 해석은 각 탭 첫 섹션이 담당합니다.

### 서버 데이터 결합 계층
- 프런트엔드의 `src/krx/server/data-service.ts`가 탭별 조합 데이터를 만듭니다.
- 같은 원천 데이터를 여러 탭에서 재조합하되, 각 탭이 서로 다른 질문에 답하도록 화면 책임을 나눕니다.

### 백엔드 도메인 흐름
- 뉴스
  - raw ingestion -> triage/materialization -> `/api/news/*`, `/api/krx/news/*`
- 파생/시장 신호
  - KIS/KRX source -> summary/trends/investor flow -> `/api/krx/market-signal/*`, `/api/krx/derivatives/*`
- 글로벌 이벤트
  - official source/vendor adapter -> impact 해석 -> `/api/global-events/*`
- 앱 헤더/공통 상태
  - `/api/app/header?market=krx`

## 5. 주요 런타임 동작

### 캐시/갱신 정책
- `시장 뉴스`
  - `force-dynamic` + 클라이언트 60초 polling 유지
- `파생·수급(/krx)`과 관련 파생 fetch
  - 30초 재검증
- `AI 인사이트`의 macro news fetch
  - 30초 재검증
- 상단 GNB
  - 안정 탭만 적극 prefetch
  - `시장 뉴스`는 제외

### 데이터 소스 전략
- 기본 로컬 실행은 mock/file 중심으로 동작합니다.
- 외부 키 없이도 앱 구조와 기본 surface를 확인할 수 있습니다.
- 실제 live 확장 시 주요 소스는 아래처럼 분리합니다.
  - 뉴스 수집: NAVER, RSS, DART 등
  - 파생/시장 데이터: KIS, KRX reference
  - 매크로 reference: FRED

### 뉴스 자동화
- 앱 내부 루프가 아니라 CLI + cron tick 구조를 전제로 합니다.
- 대표 명령:
  - `python3 -m src.krx.source_ingestion.cli run-news-automation`
- 기본 cadence:
  - 장중 1분
  - 장 종료 직후 5분
  - 비장중 10분

## 6. 로컬 실행

### 사전 요구사항
- Node.js 20+
- `pnpm`
- Python 3.10+

### 1) 의존성 설치
```bash
pnpm install

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

### 2) 환경 변수 준비
```bash
cp .env.example backend/.env
cat > frontend/.env.local <<'ENV'
BACKEND_BASE_URL=http://localhost:4000
ENV
```

### 3) 개발 서버 실행
터미널 1:
```bash
source .venv/bin/activate
pnpm dev:backend
```

터미널 2:
```bash
pnpm dev:frontend
```

### 기본 접속 주소
- frontend: `http://localhost:3000`
- backend: `http://localhost:4000`

### 첫 확인 추천 경로
- `http://localhost:3000/krx/dashboard`
- `http://localhost:3000/krx/insights`
- `http://localhost:3000/krx`
- `http://localhost:3000/krx/news`
- `http://localhost:3000/krx/macro-calendar`

## 7. 환경 변수 가이드

루트 `.env.example`은 frontend + backend 공용 샘플입니다. 실제 값은 보통 `backend/.env`와 `frontend/.env.local`에 나눠 넣습니다.

### 최소 로컬 실행에 필요한 값
- frontend
  - `BACKEND_BASE_URL=http://localhost:4000`
- backend
  - 기본값만으로도 mock/file 중심 실행 가능

### live 확장 시 먼저 보게 될 섹터
- 뉴스 수집
  - `NAVER_NEWS_ENABLED`
  - `NAVER_NEWS_CLIENT_ID`
  - `NAVER_NEWS_CLIENT_SECRET`
- KIS 파생 1차 live
  - `KIS_APP_KEY`
  - `KIS_APP_SECRET`
  - `KIS_ACCESS_TOKEN`
  - `KIS_DOMESTIC_DERIVATIVES_PROVIDER`
  - `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON`
- FRED reference
  - `FRED_PROVIDER`
  - `FRED_API_KEY`

자세한 정리는 [env-by-sector.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/reference/env-by-sector.md)를 참고하면 됩니다.

## 8. 자주 쓰는 명령

### 전체 검증
```bash
pnpm lint
pnpm test
pnpm build
```

### 프런트만
```bash
pnpm --filter frontend lint
pnpm --filter frontend test
pnpm --filter frontend build
```

### 백엔드만
```bash
cd backend
pytest -q
```

### 경계 검증
```bash
pnpm check:boundaries
```

## 9. 현재 문서에서 주의할 점

- 루트 README는 입구 문서입니다.
- 세부 구현 사실은 아래 문서를 우선 기준으로 봐야 합니다.
  - 현재 화면/경로/IA: `doc/architecture/krx-mvp-ia.md`
  - 현재 구현 상태: `doc/architecture/implementation-status.md`
  - 실제 구조: `doc/architecture/project-structure.md`
  - 런타임 흐름: `doc/architecture/system-map.md`
- 과거 계획/아카이브 문서는 현재 사실 문서가 아닙니다.

## 10. 추천 문서 순서

### 처음 보는 경우
1. [doc/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/README.md)
2. [doc/architecture/krx-mvp-ia.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/krx-mvp-ia.md)
3. [doc/architecture/project-structure.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/project-structure.md)
4. [doc/architecture/system-map.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/system-map.md)
5. [doc/architecture/implementation-status.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/implementation-status.md)

### 뉴스 파이프라인을 볼 때
- [backend/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/backend/README.md)
- [doc/domains/news/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/domains/news/README.md)
- [doc/domains/news/source-map.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/domains/news/source-map.md)
- [doc/domains/news/rebuild-summary.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/domains/news/rebuild-summary.md)

### 프런트 surface를 볼 때
- [frontend/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/frontend/README.md)
- [doc/troubleshooting/navigation-and-ia.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/troubleshooting/navigation-and-ia.md)
- [doc/troubleshooting/dashboard-and-insights.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/troubleshooting/dashboard-and-insights.md)

## 11. 현재 한계와 전제

- `매크로 캘린더`의 가격 보드는 일부 구간에서 structured fallback 설명을 사용합니다.
- `파생·수급`은 상단 label만 바뀐 것이 아니라 `/krx` 내부에서 파생/수급 surface를 더 직접적으로 설명하도록 정리된 상태입니다.
- 뉴스 surface와 자동화는 계속 확장 중이므로, provider/AI 관련 env는 기본적으로 꺼져 있는 항목이 많습니다.
- live provider를 붙이지 않아도 앱은 실행되지만, 실제 시장 품질은 provider 설정과 데이터 freshness에 크게 의존합니다.

## 12. 관련 문서 맵

- 문서 인덱스
  - [doc/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/README.md)
- 실행 가이드
  - [RUN_GUIDE.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/RUN_GUIDE.md)
- 프런트/백엔드 상세
  - [frontend/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/frontend/README.md)
  - [backend/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/backend/README.md)
- 아키텍처 핵심
  - [doc/architecture/README.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/README.md)
  - [doc/architecture/project-structure.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/project-structure.md)
  - [doc/architecture/system-map.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/system-map.md)
  - [doc/architecture/krx-mvp-ia.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/architecture/krx-mvp-ia.md)
- 참고 자료
  - [doc/reference/domain-oriented-data-model.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/reference/domain-oriented-data-model.md)
  - [doc/reference/provider-flexibility-design.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/reference/provider-flexibility-design.md)
  - [doc/reference/risk-priority.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/reference/risk-priority.md)
  - [doc/reference/codex-multi-agent-prompts.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/reference/codex-multi-agent-prompts.md)
