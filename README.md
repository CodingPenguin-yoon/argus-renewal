# Argus Renewal

한국 시장의 수급, KOSPI200 종목, 선물·옵션 상태를 장중에 빠르게 판독하기 위한 시장 데이터 터미널이다.

## 현재 구현

- 새 경계: `backend/src/market_data/`, `frontend/src/market_terminal/`
- 첫 수직 기능: KOSPI 현물과 KOSPI200 선물·콜·풋의 개인·외국인·기관 수급
- 데이터 모드: API key가 필요 없는 `mock` fixture만 구현
- 신뢰 표시: `estimate`와 simulated `confirmed`, source, observed time, fresh/stale/missing을 분리 표시
- 새 화면: `/market`, `/market/stocks`, `/market/derivatives`
- 새 API: `GET /api/market-data/v1/dashboard/market-flow`
- 레거시: `/argus`, `/api/argus/v2/*`, `argus_v2` 코드와 테스트는 아직 유지

`/market/stocks`와 `/market/derivatives`는 독립 URL과 탭 구조만 만들었으며 실제 종목·파생 데이터는 다음 수직 기능에서 연결한다.

## 로컬 실행

Python 3.11 환경에서 검증했다. 현재 고정된 Pydantic 버전은 로컬 Python 3.14에서 빌드되지 않는다.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
pnpm install --frozen-lockfile
```

환경 변수 파일을 만든 뒤 `backend/.env`의 `KIS_APP_KEY`, `KIS_APP_SECRET`에 발급받은 값을 입력한다. mock 화면만 사용할 때는 두 값을 비워둬도 된다.

```bash
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env.local
```

fixture를 SQLite에 먼저 적재한다.

```bash
pnpm seed:market-flow
```

두 터미널에서 backend와 frontend를 실행한다.

```bash
pnpm dev:backend
```

```bash
pnpm dev:frontend
```

브라우저에서 `http://localhost:3000/market`을 연다. 기본 DB는 `backend/data/argus.db`이며 설정은 `backend/.env.example`, `frontend/.env.example`을 기준으로 한다.

현재 `pnpm dev`는 레거시 market/news collector까지 함께 실행하므로 새 mock 화면만 확인할 때는 사용하지 않는다.

## 검증

```bash
.venv/bin/pytest -q backend/tests
pnpm --filter frontend test
pnpm --filter frontend lint
pnpm --filter frontend build
pnpm check:boundaries
```

boundary 검사는 새 backend/frontend가 `argus_v2`를 참조하지 않는지, market-flow API가 수집 adapter를 직접 호출하지 않는지 확인한다.

## 제품 범위

- 상단 정보구조: `대시보드 | 종목 | 파생`
- 종목 universe: 거래일 기준 KOSPI200 구성종목
- 종목 상세: 현재가 요약과 `차트 | 수급`
- 파생 상세: `KOSPI200 | 삼성전자 | SK하이닉스`
- 1차 시장 범위: `KRX`
- 데이터 신뢰 기준: 증권사 장중 수급은 `estimate`, KRX 장 마감 거래실적은 `confirmed`

## 공동 문서

- [Project Profile](project-docs/project-profile.md)
- [Project Specification](project-docs/specifications/project-specification.md)
- [Architecture Baseline](project-docs/architecture/overview.md)
- [Market Data API](project-docs/api/market-data-v1.md)
- [Market Flow Database](project-docs/database/market-flow.md)
- [Market Flow](project-docs/flows/market-flow.md)
- [Provider Architecture ADR](project-docs/decisions/ADR-001-capability-based-market-data-providers.md)
- [Clean Rebuild ADR](project-docs/decisions/ADR-002-clean-rebuild-with-selective-legacy-extraction.md)
- [Approved Clean Rebuild Plan](project-docs/plans/2026-07-21-clean-rebuild.md)

## 보호 대상과 다음 단계

- 실제 `.env`, access token cache와 운영 DB는 삭제·문서화 대상이 아니다.
- 시크릿은 환경 변수로만 주입하고 fixture·로그·DB raw sample에서 제거한다.
- 다음 구현은 live source 가능성 검증 후 KOSPI200 universe와 종목 시세·수급 수직 기능이다.
- 레거시 코드 삭제는 characterization 자산 이관과 별도 승인 후 진행한다.
