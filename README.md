# Argus Renewal

Argus Renewal은 **Argus v2** 기준으로 재구성 중인 한국장 시장 상황판입니다.

종목 추천 서비스가 아니라, 장 시작 전과 장중에 `파생/옵션 포지셔닝 -> 실제 뉴스/매크로 트리거 -> 현물 반응` 순서로 시장 상태를 빠르게 읽기 위한 도구입니다. 원천 뉴스 피드는 `뉴스 분석` 탭 안에서 트리거 판단의 재료로 분리해 보여줍니다.

## Product Direction

- 판단 라벨은 `강한 상방 / 상방 우위 / 중립 / 하방 우위 / 강한 하방`만 사용합니다.
- 첫 화면은 결론, 핵심 근거, 반대 증거, 전환 조건을 한 번에 보여줍니다.
- 상세 탭은 `시장 판단`, `옵션·선물`, `현물 반응`, `뉴스 분석` 네 개만 유지합니다.
- `옵션·선물` 내부는 `메인`, `선물`, `옵션 시세표`, `풋콜 레이어`, `포지션` 서브탭으로 나눕니다.
- `뉴스 분석` 내부는 `메인`과 `뉴스` 서브탭으로 나눕니다. `메인`은 시장 판단에 연결된 트리거, `뉴스`는 실시간 원천 경제 뉴스 피드입니다.
- AI 인사이트는 별도 탭이 아니라 각 화면 안의 해석 레이어입니다.
- 매수/매도 추천처럼 읽히는 표현은 쓰지 않습니다.

## Source Of Truth

- [Argus v2 PRD](doc/prd/argus-v2-prd.md)
- [Argus v2 Grill Me Decision Register](doc/prd/argus-v2-grill-me.md)
- [Current Status](doc/plans/current-status.md)
- [MVP Closeout](doc/plans/mvp-closeout.md)
- [Argus v2 Roadmap](doc/plans/argus-v2-roadmap.md)

## Repository Structure

```text
argus_renewal/
├── backend/              # FastAPI, Argus v2 API, SQLite storage, KIS providers
├── frontend/             # Next.js App Router, Argus v2 화면
├── doc/
│   ├── prd/              # 제품 기준
│   └── plans/            # 현재 상태와 남은 작업
├── scripts/
├── README.md
├── RUN_GUIDE.md
├── package.json
├── pnpm-workspace.yaml
└── .env.example
```

## Runtime Surface

- Frontend: `/argus`, `/argus/derivatives`, `/argus/derivatives/futures`, `/argus/derivatives/option-quotes`, `/argus/derivatives/option-layer`, `/argus/derivatives/positions`, `/argus/reaction`, `/argus/triggers`, `/argus/triggers/news`
- Backend: `/api/argus/v2/dashboard`, `/api/argus/v2/futures`, `/api/argus/v2/option-quotes`, `/api/argus/v2/news-feed`, `/health`
- Legacy `/krx*`, `/api/krx*`, `/api/news*`, `/api/global-events*` runtime surface는 제거했습니다.
- Live news judgement는 키워드 포함 규칙이 아니라 AI enrichment JSON(`should_use`, `impact`, `relevance_score`, `connection_strength`)만 사용합니다. AI가 꺼져 있으면 임의로 호재/악재를 분류하지 않습니다.

## Storage

Argus v2는 `DB_PATH`가 가리키는 SQLite DB에 `argus_v2_*` 테이블을 만듭니다.

- provider run과 provider health
- 민감값 제거된 raw sample
- KIS 국내파생 snapshot
- KIS 옵션체인 snapshot/level
- v2 현물 반응 snapshot/sector와 현물 투자자 수급
- v2 뉴스 트리거

## News Analysis

- `/argus/triggers`는 뉴스 분석 메인 화면으로, AI 판단을 거친 시장 연결 트리거만 표시합니다.
- `/argus/triggers/news`는 `/api/argus/v2/news-feed`에서 받은 원천 뉴스 피드를 표시합니다.
- `ARGUS_NEWS_FEED_PROVIDER` 기본값은 `rss`라서 API 키 없이 RSS 경제 뉴스를 읽습니다. `ARGUS_NEWS_FEED_RSS_URLS`가 비어 있으면 `ARGUS_NEWS_TRIGGERS_RSS_URLS`를 재사용합니다.
- 원천 뉴스 피드는 AI 분류 없이 나열하고, 시장 판단용 뉴스 트리거는 기존처럼 AI enrichment 결과가 `should_use=true`인 항목만 사용합니다.

## Derivatives Analysis

- `/argus/derivatives`는 옵션·선물 메인 화면으로, 파생 포지셔닝의 핵심 요약과 주요 레벨을 표시합니다.
- `/argus/derivatives/futures`는 `/api/argus/v2/futures`에서 받은 KOSPI200 근월 선물 snapshot의 현재가, 등락률, 거래량, 미결제약정, basis를 표시합니다.
- `/argus/derivatives/option-quotes`는 `/api/argus/v2/option-quotes`에서 받은 풋·콜 행사가별 시세, 거래량, 거래대금, OI 값을 좌우 배치한 HTS형 옵션 시세표입니다.
- `/argus/derivatives/option-layer`는 당일 옵션 풋콜 레이어 화면으로, 현재 수신된 옵션 OI 변화와 핵심 행사가를 표시합니다.
- `/argus/derivatives/positions`는 외국인·기관·개인의 선물/현물 수급, 선물 시장 레이어, 옵션 거래대금 레이어, 옵션 매수·매도·순계약 영역을 한 화면에 모으는 포지션 종합 화면입니다.

## Local Run

```bash
pnpm install

python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt

cp .env.example backend/.env
cat > frontend/.env.local <<'ENV'
BACKEND_BASE_URL=http://localhost:4000
ENV
```

Terminal 1:

```bash
source .venv/bin/activate
pnpm dev
```

`pnpm dev`는 backend API, frontend, market collector, news collector를 함께 실행합니다. 개별로 띄우려면 아래 명령을 각각 사용합니다.

```bash
pnpm dev:backend
pnpm dev:frontend
pnpm dev:collector:market
pnpm dev:collector:news
```

## Live Smoke

KIS app key/secret을 `backend/.env`에 넣은 뒤 실행합니다. access token은 env에 저장하지 않고 로컬 캐시에만 둡니다.

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

현물 반응과 뉴스 트리거 컨텍스트를 적재합니다.

```bash
cd backend
python3 -m src.argus_v2.cli collect-context
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis
python3 -m src.argus_v2.cli collect-context --news-triggers-provider rss
python3 -m src.argus_v2.cli collect-context --news-triggers-provider naver
python3 -m src.argus_v2.cli collect-context --news-triggers-provider dart
python3 -m src.argus_v2.cli collect-context --news-triggers-provider hybrid
```

세션-aware collector는 파생/현물 market 수집과 뉴스 수집을 나눠 1회 실행합니다. 정규장 market 수집은 세션이 열렸을 때만 돌고, 뉴스는 장외/휴일에도 돌 수 있습니다. 야간 파생 수집은 `ARGUS_COLLECTOR_NIGHT_MARKET_ENABLED=true`로 별도 활성화합니다.

```bash
cd backend
python3 -m src.argus_v2.cli collect-once
python3 -m src.argus_v2.cli collect-once --market-only
python3 -m src.argus_v2.cli collect-once --news-only
python3 -m src.argus_v2.cli collect-once --force-market
python3 -m src.argus_v2.cli collect-loop --interval-seconds 60
```

collector 뉴스 경로는 시장 판단용 `v2_news_triggers`와 원천 뉴스용 `v2_news_feed`를 분리해 DB에 저장합니다. `/api/argus/v2/news-feed`는 저장된 원천 뉴스가 있으면 DB를 우선 조회합니다.

배포 시에는 backend API와 collector를 별도 프로세스로 띄웁니다. 예시는 `doc/operations/deployment-collectors.md`를 참고합니다.

실뉴스 판단을 켜려면 `backend/.env`에 AI provider와 모델/key를 설정합니다. Gemini는 `ARGUS_NEWS_AI_PROVIDER=gemini`, `ARGUS_GEMINI_MODEL=gemini-2.5-flash`, `ARGUS_GEMINI_API_KEY`를 사용합니다. OpenAI-compatible provider는 `ARGUS_NEWS_AI_PROVIDER=openai`, `ARGUS_NEWS_AI_MODEL`, `ARGUS_NEWS_AI_API_KEY`를 사용합니다. 키가 없으면 `mock` provider 또는 file import의 명시적 `ai_enrichment`로만 뉴스 트리거를 표시합니다.

AI 뉴스 판단 smoke test:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

## Validation

```bash
pnpm --filter frontend lint
pnpm --filter frontend test -- --runInBand
pnpm --filter frontend build

cd backend
pytest -q
```
