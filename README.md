# Argus Renewal

Argus Renewal은 **Argus v2** 기준으로 재구성 중인 한국장 시장 상황판입니다.

뉴스 피드나 종목 추천 서비스가 아니라, 장 시작 전과 장중에 `파생/옵션 포지셔닝 -> 실제 뉴스/매크로 트리거 -> 현물 반응` 순서로 시장 상태를 빠르게 읽기 위한 도구입니다.

## Product Direction

- 판단 라벨은 `강한 상방 / 상방 우위 / 중립 / 하방 우위 / 강한 하방`만 사용합니다.
- 첫 화면은 결론, 핵심 근거, 반대 증거, 전환 조건을 한 번에 보여줍니다.
- 상세 탭은 `시장 판단`, `옵션·선물`, `현물 반응`, `뉴스 트리거` 네 개만 유지합니다.
- AI 인사이트는 별도 탭이 아니라 각 화면 안의 해석 레이어입니다.
- 매수/매도 추천처럼 읽히는 표현은 쓰지 않습니다.

## Source Of Truth

- [Argus v2 PRD](doc/prd/argus-v2-prd.md)
- [Argus v2 Grill Me Decision Register](doc/prd/argus-v2-grill-me.md)
- [Current Status](doc/plans/current-status.md)
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

- Frontend: `/argus`, `/argus/derivatives`, `/argus/reaction`, `/argus/triggers`
- Backend: `/api/argus/v2/dashboard`, `/health`
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
pnpm dev:backend
```

Terminal 2:

```bash
pnpm dev:frontend
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

실뉴스 판단을 켜려면 `backend/.env`에 `ARGUS_NEWS_AI_PROVIDER=openai`, `ARGUS_NEWS_AI_MODEL`, `ARGUS_NEWS_AI_API_KEY`를 설정합니다. 키가 없으면 `mock` provider 또는 file import의 명시적 `ai_enrichment`로만 뉴스 트리거를 표시합니다.

## Validation

```bash
pnpm --filter frontend lint
pnpm --filter frontend test -- --runInBand
pnpm --filter frontend build

cd backend
pytest -q
```
