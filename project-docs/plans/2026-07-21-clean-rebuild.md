# 구현 계획: 선별 추출 후 Argus 클린 리빌드

- 상태: `APPROVED`
- 날짜: `2026-07-21`
- 관련 요구사항: `project-docs/specifications/project-specification.md`
- 관련 ADR: `project-docs/decisions/ADR-001-capability-based-market-data-providers.md`, `project-docs/decisions/ADR-002-clean-rebuild-with-selective-legacy-extraction.md`
- 승인자: 사용자

## 1. 위험도

- 분류: `HIGH`
- 판단 근거: 기존 애플리케이션·API·migration·문서 제거, 새 도메인 경계와 데이터 소유권 도입, 새 외부 provider 추가
- 실패 영향: KIS 연동 지식과 fixture 손실, local DB 또는 시크릿 훼손, 복구 불가한 사용자 변경 삭제, 새 수집기의 중복·정합성 오류
- 되돌리기 어려운 부분: legacy 삭제와 기존 DB 계약 폐기

## 2. 확인한 현재 상태

- 현재 동작: FastAPI가 `/api/argus/v2/*`를 제공하고 Next.js `/argus`가 SQLite의 저장 snapshot을 조회한다.
- 현재 제품 중심: 파생·뉴스·rule-based judgement를 하나의 dashboard로 조립한다.
- 새 제품 중심: 시장 수급, KOSPI200 종목, 종목 차트·수급, KOSPI200·삼성전자·SK하이닉스 파생이다.
- 재사용 가치가 높은 경계: KIS auth와 HTTP mapping, KOSPI200 선물·옵션 parsing, redaction, provider 실패 시나리오, collector lease 시나리오
- 직접 재사용 가치가 낮은 경계: monolithic storage/dashboard, 뉴스·AI context, judgement engine, 기존 frontend dashboard와 route tree
- 현재 worktree: 기존 `.codex`, `.ralph`, `.serena` 파일 삭제와 `AGENTS.md` 수정, 신규 하네스·`project-docs/`가 섞여 있다. 이 Plan은 해당 사용자 변경을 정리하거나 되돌리지 않는다.
- 검증 상태:
  - backend 테스트: `pytest` 실행 파일이 없어 미실행
  - frontend 테스트: 의존성 부재와 registry DNS 제한으로 미실행
  - boundary 검사: 현재 script가 실제 검사를 하지 않으며 pnpm 실행도 의존성 부재로 완료하지 못함
- 확인되지 않은 항목:
  - 현재 SQLite DB에 보존해야 할 실사용 데이터가 있는지
  - `/api/argus/v2/*` 또는 `/argus`의 외부 소비자가 있는지
  - local `.env`와 token cache의 보존·폐기 범위
  - 기존 KIS fixture가 현재 live 응답과 계속 일치하는지

## 3. 목표와 범위

- 목표: legacy import가 없는 새 시장 데이터 터미널을 구축하고 필요한 외부 API 지식만 검증 가능한 형태로 이관한 뒤 기존 제품 코드를 제거한다.
- 범위: legacy 자산 분류, characterization fixture, 새 backend/frontend skeleton, 첫 시장 수급 수직 기능, legacy 삭제, 새 문서와 실행 경로
- 비범위: 승인 없는 DB engine 교체, 자동매매, 실계정 데이터 삭제, Git commit·push, 하네스 관리 영역 삭제
- 인수 조건:
  - 새 코드에서 `argus_v2` import가 없다.
  - KIS 인증과 핵심 옵션·선물 fixture가 새 provider 계약 테스트를 통과한다.
  - 첫 `market_flow` 수직 기능이 provider fixture 또는 live API → normalize → store → query API → dashboard까지 동작한다.
  - 상단 `대시보드 | 종목 | 파생`과 종목 상세 `차트 | 수급`이 독립 URL과 상태를 가진다.
  - API 요청 경로는 증권사 API를 동기 호출하지 않고 저장된 fact만 조회한다.
  - 삭제 대상이 새 코드·테스트·script·문서에서 참조되지 않는다.
  - 필요한 local data와 시크릿의 백업 또는 폐기 결정이 기록된다.
- 유지할 계약: 하네스와 `project-docs/`; 외부 소비자가 확인되면 해당 공개 계약은 삭제 전 별도 전환한다.

## 4. 아키텍처와 데이터 영향

- 도메인·모듈: `backend/src/market_data/`, `frontend/src/market_terminal/`를 새 기준으로 사용한다.
- 책임과 의존성 방향: provider HTTP → provider adapter → capability port → normalized fact → storage/query → API → frontend
- 데이터 소유권: 새 market data storage가 universe, quote, candle, investor flow, derivatives fact와 provider run을 소유한다.
- 트랜잭션·정합성: provider batch 단위 transaction, fact unique key, estimate/confirmed 분리, collector lease 또는 동등한 single-writer 보호
- API·DB·외부 시스템: 새 `/api/market-data/v1/*`; KIS·키움·LS adapter; additive 새 schema를 먼저 만든 뒤 legacy schema 제거 여부를 판단한다.
- 보안·권한: 시크릿은 env로만 주입하고 token cache와 raw payload redaction을 provider별로 검증한다.

### 목표 코드 구조

backend는 capability 중심으로 구성하고 증권사 공통 인증·HTTP client만 provider 하위에 둔다.

```text
backend/src/market_data/
├── shared/                 # provenance, 공통 오류, redaction만 허용
├── market_flow/            # 첫 수직 기능
│   ├── domain.py
│   ├── ports.py
│   ├── collect.py
│   ├── queries.py
│   ├── repository.py
│   ├── api.py
│   └── adapters/
│       └── ls.py
├── stocks/                 # 해당 단계에서 생성
├── derivatives/            # 해당 단계에서 생성
└── providers/
    ├── kis/
    ├── kiwoom/
    └── ls/
```

frontend는 화면 영역별로 계약, 조회, component, test를 함께 둔다.

```text
frontend/src/market_terminal/
├── shell/
├── dashboard/
├── stocks/
├── derivatives/
└── shared/
```

첫 단계에서는 `stocks/`, `derivatives/` 같은 빈 폴더를 미리 만들지 않는다. 재사용자가 두 곳 이상 생기기 전에는 기능 코드를 `shared/`로 이동하지 않는다.

### 경계 규칙

- domain은 FastAPI, SQLite, 증권사 HTTP field를 import하지 않는다.
- API와 frontend는 raw provider payload를 사용하지 않는다.
- provider HTTP client와 payload mapper를 분리한다.
- route와 `page.tsx`는 조립만 담당한다.
- capability별 repository를 두고 하나의 거대한 `storage.py`를 만들지 않는다.
- 새 source에서 `argus_v2` import를 금지하는 실제 boundary 검사를 둔다.
- 파일 300~400줄 초과는 분리 검토 신호로 사용하되 줄 수만 맞추는 억지 분리는 하지 않는다.

## 5. 선택지와 결정

| 순위 | 선택지 | 적합한 이유 | 단점·비용 | 추천 여부 |
|---:|---|---|---|---|
| 1 | 선별 추출 후 클린 리빌드 | 제품 경계를 새로 잡으면서 KIS 지식과 fixture 보존 | 삭제 전 추출 단계 필요 | 추천 |
| 2 | 장기간 병행 전환 | 운영 소비자가 있을 때 rollback이 쉬움 | legacy 유지 비용 | 조건부 |
| 3 | 즉시 전부 삭제 | active tree가 빠르게 단순해짐 | 지식·테스트·사용자 변경 손실 | 비추천 |

- 사용자 결정: 선별 추출 후 클린 리빌드와 Capability Port + Provider Adapter 구조를 선택한다. 1차 시장 범위는 `KRX`, 장중 증권사 수급은 `estimate`, KRX 장 마감 거래실적은 `confirmed`로 분리한다.
- 승인일: `2026-07-21`

### 승인된 1차 구현 범위

1차 구현은 전체 종목·파생 기능을 한 번에 만들지 않고 `market_flow` 하나를 끝까지 연결한다.

- 포함: provenance와 품질 모델, capability port, provider fixture/adapter, additive SQLite schema, 멱등 저장, 저장 기반 조회 API, 대시보드 최소 패널, KRX 확정값 reconciliation 계약
- 시장 범위: `KRX`
- 장중 데이터: 증권사 수급을 `estimate`로 저장
- 장 마감 데이터: KRX 기준 데이터를 별도 `confirmed` fact로 저장
- 실패 표시: 해당 capability만 `stale` 또는 `missing`으로 표시
- 비포함: KOSPI200 200종목 수집, 종목 상세, 옵션체인 이관, NXT·SOR, 레거시 삭제
- 완료 조건: fixture 기준으로 `estimate`와 `confirmed`가 함께 보존·조회되고, 동일 fact 재수집이 중복을 만들지 않으며, API 요청 경로가 provider를 직접 호출하지 않는다.

## 6. 구현 단계

| 단계 | 결과 | 변경 책임·예상 파일 | 검증 | 복구 지점 |
|---:|---|---|---|---|
| 0 | 보호 범위와 실행 환경 확정 | worktree, DB·env·token cache, 외부 소비자, Python·Node version과 dependency 설치 상태 확인 | 보호 manifest와 실제 검증 명령 대조 | 변경 없음 |
| 1 | 첫 수직 기능 characterization kit | KIS auth, 현재 시장 투자자 수급, redaction, provider run과 lease 시나리오를 새 테스트 자산으로 추출 | fixture secret scan, 기존 기대값 기록 | 기존 코드 유지 |
| 2 | provider 가능성 검증 | KIS·LS·키움 read-only smoke 또는 공식 sample로 capability별 응답과 호출 제한 기록 | redacted payload, 단위·시장 범위·갱신 시각 확인 | 제품 코드 변경 없이 중단 가능 |
| 3 | 최소 skeleton과 경계 | `market_data`, `market_terminal`, 새 router, 3탭 shell, 실제 boundary 검사 | health, legacy import 금지, lint·test·build | 새 폴더만 제거 가능 |
| 4 | 첫 `market_flow` 수직 기능 | 증권사 장중 adapter, KRX 확정 reference adapter 계약, `MarketFlowFact`, SQLite repository, `/api/market-data/v1/dashboard/market-flow`, dashboard panel | `KRX` 범위, estimate/confirmed 동시 보존, reconciliation, idempotency, stale/missing, API/UI contract | 새 collector·route 비활성화 |
| 5 | KOSPI200 종목 기능 | universe, KIS quote·chart, 키움 장중 수급, EOD 확정 수급, 종목 목록과 상세 `차트 | 수급` | 구성종목 완전성, 부분 실패, estimate/confirmed, 화면 상태 보존 | 종목 capability 비활성화 |
| 6 | 파생 기능 | KIS 선물·옵션 characterization 자산 추출, KOSPI200 선물·옵션체인, 조건부 삼성전자·SK하이닉스 파생 | 기존 KIS fixture 대조, 만기·행사가·OI·empty 처리 | 파생 capability 비활성화 |
| 7 | cutover 준비 | entrypoint, package script, env, README와 run guide를 새 경로로 전환 | 전체 참조 검색, 전체 test/lint/build, 장중 smoke | legacy entrypoint 유지 또는 복귀 |
| 8 | legacy 코드 삭제 | 별도 승인된 `argus_v2`, 기존 `/argus`, 과거 migration 제거 | 삭제 manifest, 전체 검증, 잔여 참조 없음 | 승인된 Git 복구 지점 또는 snapshot |
| 9 | 독립 리뷰와 문서 동기화 | quality review 후 profile, specification, architecture, ADR, API, DB 갱신 | 문서 경로·명령·계약과 실제 코드 대조 | 문서 diff 복구 |

단계 8은 별도 파괴적 작업 승인 없이는 실행하지 않는다.

### 현재 진행 상태 (`2026-07-22`)

- 단계 3 완료: 새 `market_data`, `market_terminal`, `/api/market-data/v1`, `/market` 3탭 shell과 실제 boundary 검사를 구현했다.
- 단계 4의 mock-first 범위 완료: fixture adapter, normalized fact, additive SQLite schema, 멱등 repository, 저장 기반 API와 dashboard panel을 연결했다.
- 단계 1·2의 live characterization과 공급자 가능성 검증은 API key 준비 전까지 보류한다.
- 단계 5 이후와 레거시 삭제는 착수하지 않았다.

## 7. 성공·실패·데이터 흐름

- 성공 흐름: provider scheduler → capability adapter → normalized fact → idempotent storage → query API → 3탭 frontend
- 실패 흐름: provider별 실패 run 기록 → 해당 capability만 stale/missing → 다른 화면 데이터는 계속 제공
- 데이터 변환: raw provider payload는 redacted fixture로 검증하고 외부 계약에는 normalized fact만 노출
- 재시도·멱등성·보상: provider별 retry/backoff, source·instrument·observed_at·quality unique key, 잘못된 fact는 correction 또는 invalidation으로 처리

## 8. 테스트와 검증 계획

### 이관할 기존 테스트 자산

- KIS token 발급, cache 재사용, 인증정보 누락
- KIS header·TR ID·query, 근월물 code와 옵션 만기 탐색
- 선물·옵션 payload의 가격·거래량·OI·IV·거래대금 정규화
- raw sample의 app secret, authorization, access token redaction
- provider run의 success·partial·failed·skipped 상태
- collector lease 충돌과 정상 해제
- 옵션체인의 ATM·행사가·빈 상태 frontend fixture

기존 test module을 그대로 유지하지 않고 새 port, mapper, repository, API 계약에 맞춰 다시 작성한다. 기존 코드와 새 mapper를 같은 fixture로 대조한 뒤 해당 legacy test를 제거한다.

### 폐기할 기존 테스트 자산

- rule-based judgement 전체
- 뉴스·AI·RSS·Naver·DART 기능 테스트
- 기존 `/api/argus/v2/*`와 `/argus` route 이름에 고정된 테스트
- 빈 DB에서 mock dashboard를 정상 데이터처럼 반환하는 fallback 테스트

### 새로 추가할 테스트

- 단위 테스트: token cache, field mapping, 단위·부호, provenance, freshness, estimate/confirmed
- 통합·계약 테스트: provider batch, migration, idempotent insert, API Pydantic와 frontend Zod
- 경계·실패 테스트: auth 실패, 429, timeout, 부분 payload, stale, duplicate collector, redaction
- KOSPI200 테스트: 구성종목 일부 누락, 200개 중 부분 실패, 장중 추정과 EOD 확정 동시 보존
- 아키텍처 테스트: legacy import 금지, API의 provider 직접 호출 금지, frontend의 provider field 의존 금지
- Formatter·Lint·타입: 실제 의존성 설치 후 frontend lint, backend compile, 실제 import boundary 검사
- 빌드·수동 확인: backend pytest, frontend Vitest/build, 장중 provider smoke와 증권사 화면 대조

각 단계의 관련 검사에 실패하면 다음 단계로 넘어가지 않는다. 실행하지 못한 검사는 성공으로 기록하지 않는다.

## 9. 문서 영향

- Project Specification: legacy 병행 요구를 승인된 reset 전략에 맞게 갱신
- Architecture·ADR: ADR-002 승인 상태와 새 실제 경계를 기록
- Domain·Flow: 첫 수직 기능에서 capability, fact, collector 흐름 작성
- API·Database: 새 공개 계약과 새 schema가 구현될 때 작성
- 과거 `doc/`: `2026-07-22` 1차 정리에서 제거 완료

## 10. 복구와 위험 완화

- 주요 위험: dirty worktree 손실, local data 삭제, KIS 계약 지식 손실, 테스트 불가능한 새 skeleton
- 예방·관찰 방법: 단계 0 manifest, redacted fixture, legacy import 금지, 실제 boundary script, 각 단계 검증
- rollback: legacy 삭제 전에는 기존 코드 유지; 삭제 시에는 사용자가 승인한 Git snapshot 또는 별도 복구 지점을 필수로 사용
- roll-forward: 누락된 provider 규칙은 fixture를 추가하고 새 adapter만 수정
- 중단 기준:
  - 보존 여부를 모르는 DB·env·token cache가 발견됨
  - 현재 변경을 복구할 Git 지점이 없음
  - 기존 API의 외부 소비자가 확인됐지만 전환 계약이 없음
  - 새 provider fixture가 live 응답 의미를 검증하지 못함
  - 시크릿이 fixture·로그·문서에 포함됨

## 11. 구현 후 대조

- 계획과 달라진 부분:
  - 구제품 문서는 새 수직 기능 완성 전인 1차 정리 단계에서 먼저 제거했다. 레거시 코드·테스트·migration은 유지한다.
  - live provider characterization보다 mock-first `market_flow` 수직 기능을 먼저 완성했다.
  - 최초 frontend 목표 구조의 빈 `stocks/`, `derivatives/` 기능 폴더 대신 실제 route placeholder만 만들었다.
- 달라진 이유:
  - API key 없이도 domain·storage·API·UI 경계를 먼저 검증하고 live adapter를 port 뒤에 추가하기로 사용자와 합의했다.
  - 새 구현의 문서 기준을 `project-docs/`로 단일화했다.
- 1차 검증 결과:
  - backend `58 passed`
  - frontend `10 passed`
  - frontend lint 성공
  - Next.js production build 성공
  - Python compile, `git diff --check`, boundary 검사 성공
  - fixture CLI가 별도 SQLite에 8 facts 저장
  - 로컬 `/market` desktop·mobile 렌더, 가로 overflow 없음, 3탭 이동, API 200 확인
- 갱신한 현재 상태 문서: `README.md`, Project Profile, Specification, Architecture, Market Data API, Market Flow Database, Market Flow 실행 흐름
- 남은 위험: live 공급자 응답·호출 제한·영업일 검증, provider run·retry·lease 이관, 보존 기간, 실사용 데이터·외부 소비자 확인
