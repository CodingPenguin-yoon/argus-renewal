# 프로젝트 프로필

- 상태: `APPROVED`
- 하네스 버전: `1.0.0`
- 최종 검토일: `2026-07-22`
- 최종 승인자: 사용자
- 문서 기준 언어: 한국어

## 프로젝트 기본 정보

- 프로젝트명: Argus Renewal
- 한 줄 목적: 한국 시장의 수급, KOSPI200 종목, 선물·옵션 상태를 장중에 빠르게 판독하는 시장 데이터 터미널
- 주요 사용자: 한국 주식시장과 파생시장을 매일 확인하는 개인 투자자
- 저장소 형태: FastAPI backend와 Next.js frontend를 포함한 pnpm workspace monorepo
- 신규 또는 기존 프로젝트: `existing`

## 선택한 Preset

- 활성 preset: `fastapi + react`
- 선택 이유: backend는 FastAPI, frontend는 Next.js와 React로 구현되어 있다.

## 기술 스택과 버전

| 영역 | 선택 기술·버전 | 선택 이유 | 확인 기준 |
|---|---|---|---|
| backend 언어·런타임 | Python 3.11 검증, 저장소 고정은 미결정 | 고정된 Pydantic 2.11.7이 로컬 Python 3.14에서 빌드되지 않아 3.11로 검증 | 로컬 `.venv`, `backend/requirements.txt` |
| backend framework | FastAPI 0.116.1, Pydantic 2.11.7 | 기존 구현 유지 | `backend/requirements.txt` |
| frontend | Next.js 16.1.6, React 19.2.3, TypeScript 5 계열 | 기존 구현 유지 | `frontend/package.json` |
| build·패키지 관리 | pnpm workspace, Python requirements | monorepo와 기존 실행 명령 유지 | `package.json`, `pnpm-lock.yaml` |
| 데이터 접근 | Python `sqlite3`, SQL 직접 실행 | 기존 저장소와 새 capability repository가 동일 SQLite를 사용 | `backend/src/argus_v2/db.py`, `backend/src/market_data/db.py` |
| 데이터베이스·migration | SQLite, 순차 SQL migration | 현재 로컬·단일 프로세스 운영에 적합 | `backend/src/argus_v2/migrations/`, `backend/src/market_data/migrations/` |
| 현재 외부 시스템 | 한국투자증권 KIS, RSS, Naver, DART, 선택적 AI provider | 현재 코드에서 확인됨 | `backend/src/config/env.py` |
| 승인된 통합 후보 | LS증권 Open API, 키움 REST API, KRX Data Marketplace | 시장·파생 장중 수급, 종목별 장중 수급, 장 마감 확정 기준 보완 | `project-docs/decisions/ADR-001-capability-based-market-data-providers.md` |

Node 런타임과 Python 런타임은 저장소에 아직 고정되어 있지 않다. 1차 슬라이스는 Python 3.11, Node 26.5.0, pnpm 11.13.0에서 검증했으며 런타임 고정은 별도 승인 대상으로 남긴다.

## 재현 가능한 개발 환경

- 격리 방식: Python `.venv`, pnpm local dependency store
- lock·wrapper 파일: `pnpm-lock.yaml`, `backend/requirements.txt`
- 로컬 시작 절차 위치: `README.md`; 새 fixture 적재는 `pnpm seed:market-flow`, API와 frontend는 `pnpm dev:backend`, `pnpm dev:frontend`를 별도 실행한다.
- Git 제외 산출물: `.venv/`, `.next/`, `backend/data/*.db`, KIS token cache, env 파일

## 승인된 아키텍처

- 현재 아키텍처 설명: `project-docs/architecture/overview.md`
- 승인된 새 아키텍처: `project-docs/decisions/ADR-001-capability-based-market-data-providers.md`
- 주요 도메인: 시장 데이터 수집, 시장 판단, 뉴스 분석, API, frontend
- 현재 데이터 소유권: `market_data_market_flow_facts`가 새 시장 수급 fact를 소유하고, 나머지 기능과 provider run은 아직 `argus_v2` storage가 소유
- 현재 의존성 방향: fixture/provider → capability port → normalized fact → capability repository → query API → `/market`; 레거시 흐름은 별도 유지
- 트랜잭션 경계: SQLite connection 단위

새 아키텍처의 첫 `market_flow` 수직 기능은 mock-first로 구현되었다. 기존 `argus_v2` 경로와 공개 계약은 유지하며, live adapter와 레거시 삭제는 별도 단계와 승인 전까지 수행하지 않는다.

## 저장소 지도

| 책임 | 경로 | 비고 |
|---|---|---|
| backend 애플리케이션 | `backend/src/argus_v2/` | 현재 운영 코드 |
| 새 market data backend | `backend/src/market_data/` | `market_flow` domain, fixture adapter, repository, query API, CLI |
| frontend 애플리케이션 | `frontend/src/app/argus/`, `frontend/src/argus_v2/` | 현재 운영 화면과 계약 |
| 새 market terminal frontend | `frontend/src/app/market/`, `frontend/src/market_terminal/` | 3탭 shell과 시장 수급 dashboard |
| backend 테스트 | `backend/tests/` | pytest |
| frontend 테스트 | `frontend/src/**/*.test.tsx` | Vitest |
| 설정 | `backend/src/config/env.py`, `backend/.env.example`, `frontend/.env.example` | 실제 값은 Git 제외된 `backend/.env`, `frontend/.env.local`에만 주입 |
| migration | `backend/src/argus_v2/migrations/` | 적용된 migration은 덮어쓰지 않음 |
| 새 market data migration | `backend/src/market_data/migrations/` | additive migration, `market_data_*` namespace |
| 공동 문서 | `README.md`, `project-docs/` | 승인된 새 방향, 현재 기준선과 전환 계획 |

## 검증 명령

| 목적 | 실행 위치 | 명령 | 필수 조건 |
|---|---|---|---|
| frontend Lint | 저장소 루트 | `pnpm --filter frontend lint` | pnpm 의존성 설치 |
| frontend 테스트 | 저장소 루트 | `pnpm --filter frontend test` | pnpm 의존성 설치 |
| backend 테스트 | 저장소 루트 | `.venv/bin/pytest -q backend/tests` | Python 3.11 `.venv` 의존성 설치 |
| backend syntax | 저장소 루트 | `PYTHONPYCACHEPREFIX=/private/tmp/argus_pycache .venv/bin/python -m compileall backend/src backend/tests` | Python 3.11 `.venv` |
| 경계 검사 | 저장소 루트 | `pnpm check:boundaries` | shell, pnpm |
| 전체 빌드 | 저장소 루트 | `pnpm build` | frontend/backend 의존성 설치 |
| market-flow fixture 적재 | 저장소 루트 | `pnpm seed:market-flow` | 활성화된 Python `.venv` |
| KIS live smoke | `backend/` | `python3 -m src.argus_v2.cli smoke-kis` | KIS 시크릿과 네트워크 |

별도 formatter 명령과 독립적인 Python 정적 타입 검사 명령은 현재 확인되지 않았다.

## 프로젝트별 고위험 영역

- 증권사 API 시크릿과 access token 처리
- 공급자별 호출 제한, 장 세션, 재시도와 중복 수집
- 장중 추정치와 장 마감 확정치의 혼용
- 옵션체인과 KOSPI200 구성종목 수집으로 인한 쓰기 부하와 데이터 증가
- 기존 `/api/argus/v2/*` 소비자와 SQLite 데이터의 호환성
- 여러 공급자의 단위, 부호, 거래소 범위 차이

## 추가 승인 경계

- LS증권·키움 REST API를 운영 의존성으로 추가하는 결정
- 새 market data 테이블과 보존 기간
- 기존 `/argus` 화면과 `/api/argus/v2/*`의 전환·폐기 시점
- SQLite 유지 또는 다른 DB로 전환하는 결정

## 승인된 제품 결정

- 승인일: `2026-07-21`
- 상단 정보구조: `대시보드 | 종목 | 파생`
- 종목 universe: 기준일별 `KOSPI200` 구성종목 전체
- 종목 상세: 현재가 요약을 고정하고 본문을 `차트 | 수급`으로 구분
- 파생 상세: `KOSPI200 | 삼성전자 | SK하이닉스`로 구분하되 개별주식 파생은 live API 검증에 성공한 상품만 활성화
- 1차 시장 범위: 시세와 수급 모두 `KRX` 기준으로 통일
- 데이터 신뢰 기준: 증권사 장중 수급은 `estimate`, KRX 장 마감 거래실적은 `confirmed`로 별도 보존
- 공급자 정책: 증권사 값을 평균하지 않고 capability별 primary와 reference source를 분리

## 문서 지도

| 주제 | 현재 문서 |
|---|---|
| 승인된 새 제품 명세 | `project-docs/specifications/project-specification.md` |
| 현재 아키텍처 기준선 | `project-docs/architecture/overview.md` |
| 공급자 아키텍처 결정 | `project-docs/decisions/ADR-001-capability-based-market-data-providers.md` |
| 클린 리빌드 전략 결정 | `project-docs/decisions/ADR-002-clean-rebuild-with-selective-legacy-extraction.md` |
| 승인된 클린 리빌드 계획 | `project-docs/plans/2026-07-21-clean-rebuild.md` |
| 레거시 정리 계획 | `project-docs/plans/2026-07-21-legacy-cleanup.md` |
| market-flow API | `project-docs/api/market-data-v1.md` |
| market-flow 저장 계약 | `project-docs/database/market-flow.md` |
| market-flow 수집·조회 흐름 | `project-docs/flows/market-flow.md` |

## 미확정 사항과 알려진 위험

- 기존 Argus v2 뉴스·AI 화면을 유지, 동결 또는 후순위로 이동할지 미확정이다.
- 삼성전자·SK하이닉스 개별주식 선물·옵션의 실제 API 제공 범위와 상품코드를 live 계정으로 검증하지 않았다.
- 키움 종목별 장중 수급의 실제 갱신 간격과 장중 데이터 정정 특성을 live 계정으로 검증하지 않았다.
- LS 시장·파생 수급의 실제 갱신 간격과 운영 호출 제한을 live 계정으로 검증하지 않았다.
- 데이터 보존 기간과 SQLite 용량 한계를 측정하지 않았다.
- `market_flow`는 현재 `mock` fixture만 제공하며 `live` 조회는 데이터 없음으로 반환한다.
