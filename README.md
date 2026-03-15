# Argus Renewal Monorepo

KRX 해석형 MVP를 위한 모노레포입니다.
핵심 UX는 `대시보드 / AI 인사이트 / 시장 신호 / 시장 뉴스 / 매크로 캘린더` 탭입니다.

## 구성
- `frontend`: Next.js App Router
- `backend`: FastAPI + SQLite
- `scripts`: lint/운영 스크립트
- `doc`: 런북/운영 문서

## 주요 경로
- `http://localhost:3000/krx/dashboard` (기본 진입. 앱 전체 허브인 대시보드. 핵심 테이크어웨이, 거시 미니 위젯, 중앙 리포트, 시장 신호/시장 뉴스/매크로 캘린더 게이트웨이를 제공합니다.)
- `http://localhost:3000/krx/insights` (AI 인사이트. 오늘의 시장 톤, 파생 기준점, AI 게이지를 함께 읽는 해석 탭입니다.)
- `http://localhost:3000/krx` (시장 신호 메인)
- `http://localhost:3000/krx/news` (시장 뉴스. 열려 있는 탭에서 60초마다 자동 갱신되며, 종합은 실시간 AI 브리핑을 다문단 리포트와 근거 링크로 정리합니다.)
- `http://localhost:3000/krx/macro-calendar` (매크로 캘린더. 한국 증시에 파급력이 큰 해외 촉매와 발표 일정을 이벤트 단위로 보여줍니다.)
- `http://localhost:3000/krx/watchlist` (보조)

호환 redirect:
- `/krx/overview` -> `/krx/dashboard`
- `/krx/macro` -> `/krx/insights`
- `/krx/global-events` -> `/krx/macro-calendar`

## KRX 성능 정책
- `시장 뉴스`는 동적 렌더링과 60초 폴링을 유지합니다.
- `시장 신호`와 관련 파생 데이터 fetch, `AI 인사이트`의 macro news fetch는 30초 재검증을 사용합니다.
- 상단 GNB는 안정적인 탭만 적극 prefetch하고, `시장 뉴스`는 제외합니다.

## KIS / FRED source 전략
- `파생 데이터`는 KIS로 유지합니다. 이 영역은 장기적으로 호가/체결/주문과 연결될 수 있는 시장 데이터 경로입니다.
- `미국채 10년물`과 `미국 금리 reference`는 FRED로 분리합니다.
- 1차 backend 구현은 `GET /api/krx/macro-reference/cards` 기준으로 들어가며, 초기 series는 `DGS10`과 `FEDFUNDS`만 고정합니다.
- `대시보드`와 `AI 인사이트`는 이미 이 backend route를 읽도록 연결됐고, FRED 카드가 준비되면 기존 macro news 기반 `금리` 표면보다 우선 사용합니다.
- 파생 summary contract에는 `KIS_DOMESTIC_DERIVATIVES` 기반 `pre_open_futures`가 추가되어, 개장 전 선물 snapshot을 별도 필드로 받을 수 있습니다.
- `KIS_DOMESTIC_DERIVATIVES` payload에 market-wide summary 필드가 있으면 `derivatives_daily_metrics` row도 함께 적재되며, KRX row가 없을 때 summary API가 이 경로로 fallback할 수 있습니다.
- `derivatives_daily_metrics` source priority는 `KRX_DERIVATIVES_MANUAL -> KIS_DOMESTIC_DERIVATIVES -> KRX_DERIVATIVES_REFERENCE -> others` 순서로 고정합니다.
- 로컬 기본값은 `FRED_PROVIDER=disabled`라서 외부 key 없이 그대로 실행됩니다. 실제 연동 전에는 `file` fixture로 먼저 검증할 수 있습니다.

## 뉴스 자동화 요약
- 수집/가공 스케줄은 앱 내부 루프가 아니라 `python3 -m src.krx.source_ingestion.cli run-news-automation` 를 1분 cron tick으로 호출하는 구조입니다.
- scheduled news sync는 기본 시장 키워드(`RAW_INGESTION_SCHEDULE_MARKET_NEWS_KEYWORDS`)로 KR 시장 뉴스를 먼저 모으고, 이후 batch triage가 걸러냅니다.
- command 내부가 장중 1분, 장 종료 직후 5분, 비장중 10분 cadence를 판단합니다.
- 뉴스 탭 1차 판단은 `news_batch_triage`를 source-of-truth로 사용하고, `NEWS_PRODUCT_BATCH_TRIAGE_*`를 켜면 짧은 뉴스 묶음을 OpenAI-compatible endpoint에 1회 보내는 batch triage로 업그레이드합니다.
- 2차 AI는 `NEWS_PRODUCT_EDITORIAL_AI_*`로 현재 표면과 top 후보를 한 번에 비교하는 compare pass를 돌리고, 같은 provider 설정으로 종합 탭 실시간 브리핑 headline/summary/key points도 생성합니다.

## 실행
```bash
pnpm install

python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt

cp .env.example backend/.env
cat > frontend/.env.local <<'ENV'
BACKEND_BASE_URL=http://localhost:4000
ENV

pnpm dev:backend
pnpm dev:frontend
```

## 검증
```bash
pnpm lint
pnpm test
pnpm build
```

## 문서
- 문서 인덱스: `doc/README.md`
- 아키텍처 입구: `doc/architecture/README.md`
- 현재 구현 상태: `doc/architecture/implementation-status.md`
- 현재 구조: `doc/architecture/project-structure.md`
- 현재 시스템 맵: `doc/architecture/system-map.md`
- 쉬운 설명 문서: `doc/troubleshooting/README.md`
- 뉴스 소스 파일 책임 맵: `doc/domains/news/source-map.md`
- 뉴스 리빌드 요약: `doc/domains/news/rebuild-summary.md`
- 도메인 기준 데이터 모델: `doc/reference/domain-oriented-data-model.md`
- provider 유연화 설계: `doc/reference/provider-flexibility-design.md`
- 리스크 우선순위: `doc/reference/risk-priority.md`
- 진행 현황 추적: `doc/plans/README.md`
- 실행/설치: `RUN_GUIDE.md`
- 프론트 상세: `frontend/README.md`
- 백엔드 상세: `backend/README.md`
- KRX MVP IA: `doc/architecture/krx-mvp-ia.md`
- Codex 멀티 에이전트 프롬프트: `doc/reference/codex-multi-agent-prompts.md`
