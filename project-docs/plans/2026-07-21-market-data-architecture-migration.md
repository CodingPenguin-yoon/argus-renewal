# 구현 계획: Capability 기반 Market Data 아키텍처 전환

- 상태: `CANCELLED`
- 날짜: `2026-07-21`
- 관련 요구사항: `project-docs/specifications/project-specification.md`
- 관련 ADR: `project-docs/decisions/ADR-001-capability-based-market-data-providers.md`
- 승인자: 해당 없음

이 계획은 클린 리빌드 결정에 따라 `project-docs/plans/2026-07-21-clean-rebuild.md`로 대체되었다. 기존 `argus_v2`를 장기간 병행 전환하는 접근 대신 새 경계에서 수직 기능을 완성한 뒤 삭제 여부를 별도 승인받는다.

## 1. 위험도

- 분류: `HIGH`
- 판단 근거: 새 외부 시스템 2개, 아키텍처·의존성 방향 변경, 신규 시장 데이터 소유권, 비동기 collector와 멱등성, DB migration
- 실패 영향: 호출 제한·인증 실패, 잘못된 단위 또는 추정치 혼용, 중복 수집, SQLite 부하, 기존 화면 회귀
- 되돌리기 어려운 부분: 새 테이블에 운영 데이터가 쌓인 뒤의 계약 변경과 기존 API를 제거한 이후의 복구

## 2. 확인한 현재 상태

- 현재 동작: KIS 중심 provider가 시장·파생 데이터를 내부 record로 변환해 SQLite에 저장하고 `/api/argus/v2/*`와 `/argus`가 조회한다.
- 관련 진입점: `backend/src/argus_v2/collector.py`, `backend/src/argus_v2/providers/`, `backend/src/argus_v2/storage.py`, `backend/src/argus_v2/api/`
- 관련 테스트: `backend/tests/test_argus_v2_*`, frontend Vitest
- 기존 패턴: provider run, raw sample redaction, dataclass record, SQL migration, collector lease, provider health
- 확인되지 않은 항목:
  - 키움·LS live 계정 인증과 실제 호출 제한
  - KOSPI200 구성종목 장중 수급의 실제 갱신 간격
  - 삼성전자·SK하이닉스 개별주식 파생 상품 제공 범위
  - 목표 보존 기간에서 SQLite 용량과 writer contention

## 3. 목표와 범위

- 목표: 새 `market_data` 경계에서 capability별 공급자를 연결하고 시장 수급 → KOSPI200 구성종목 → 종목 상세 → 파생 상세 순서로 전환한다.
- 범위: provider port/adapter, 정규화 fact, collector, 신규 storage, 조회 API, 최소 frontend 화면, live 검증
- 비범위: 기존 Argus v2 즉시 삭제, DB 엔진 교체, 자동매매, 뉴스·AI 추가 확장
- 인수 조건:
  - 시장·파생 수급과 KOSPI200 구성종목 장중 수급이 저장 기반 API로 제공된다.
  - 모든 값이 source, observed_at, estimate/confirmed, freshness를 가진다.
  - 공급자 하나가 실패해도 다른 capability는 정상이다.
  - 기존 Argus v2 테스트와 API가 전환 승인 전까지 유지된다.
- 유지할 기존 계약: `/api/argus/v2/*`, `/argus`, 기존 `argus_v2_*` 테이블

## 4. 아키텍처와 데이터 영향

- 도메인·모듈: `market_data` 수집·정규화·저장·조회 경계 신설
- 책임과 의존성 방향: provider adapter가 내부 capability contract를 구현하고 상위 계층은 증권사 세부사항을 모른다.
- 데이터 소유권: 새 market data storage가 universe, market flow, instrument flow, quote, candle, derivative fact를 소유한다.
- 트랜잭션·정합성: provider batch 단위 transaction, fact uniqueness, estimate/EOD reconciliation
- API·DB·외부 시스템: KIS 유지, LS·키움 추가, 신규 `/api/market-data/v1/*`와 additive migration
- 보안·권한: 공급자별 시크릿 env, token cache 분리, raw sample redaction 확장

## 5. 선택지와 결정

| 순위 | 선택지 | 적합한 이유 | 단점·비용 | 추천 여부 |
|---:|---|---|---|---|
| 1 | Capability Port + Provider Adapter | 여러 공급자의 강점을 조합하고 실패를 격리 | 운영·정규화 복잡도 증가 | 추천 |
| 2 | KIS 단일 공급자 | 가장 단순 | 핵심 수급 요구 미충족 | 비추천 |
| 3 | 화면에서 증권사 API 직접 조합 | 실험은 빠름 | 결합도·중복·장애 전파 | 비추천 |

- 사용자 결정: 장기간 병행 전환 대신 `project-docs/plans/2026-07-21-clean-rebuild.md`의 선별 추출 후 클린 리빌드를 선택해 이 계획을 취소한다.
- 승인일: `2026-07-21`

별도로 승인된 제품 결정은 다음과 같다.

- 제품 결정일: `2026-07-21`
- 상단 정보구조: `대시보드 | 종목 | 파생`
- 종목 universe: 기준일별 KOSPI200 구성종목 전체
- 종목 상세: 현재가 요약 + `차트 | 수급`
- 파생 상세: `KOSPI200 | 삼성전자 | SK하이닉스`, 단 개별주식 파생은 live API 검증 성공 시 활성화

## 6. 구현 단계

| 단계 | 결과 | 변경 책임·예상 파일 | 검증 | 복구 지점 |
|---:|---|---|---|---|
| 0 | live 가능성 검증 | 공급자별 read-only smoke와 redacted fixture | KOSPI, 삼성전자, SK하이닉스 샘플과 호출 간격 기록 | 코드·DB 변경 없이 종료 |
| 1 | 최소 capability core | `backend/src/market_data/domain`, `application`, provider protocol과 테스트 | fixture contract, boundary 검사 | 새 폴더 제거 가능 |
| 2 | 시장 수급 수직 기능 | LS `t1602` adapter, market flow fact/storage/API, 최소 시장 화면 | KOSPI·선물·콜·풋 필드, stale·장외·오류 테스트 | feature flag off, 기존 화면 유지 |
| 3 | KOSPI200 종목 수직 기능 | universe, KIS quote, 키움 `ka10064`, stock list API/UI | 기준일별 구성종목 완전성, 실제 호출 제한, 중복·부분 실패 테스트 | 종목 collector/API flag off |
| 4 | 종목 상세와 EOD 확정 | candle, 수급 시계열, KIS/키움 EOD adapter, reconciliation | estimate와 confirmed 동시 보존, 날짜·단위 테스트 | 상세 route flag off |
| 5 | KOSPI200 파생 상세 이관 | KIS 선물·옵션 adapter를 새 contract로 감싸고 옵션체인 조회 전환 | 기존 옵션 fixture·API 대조 | 기존 `argus_v2` 파생 화면으로 복귀 |
| 6 | 개별주식 파생 조건부 추가 | 삼성전자·SK하이닉스 상품 검증 성공 시 adapter/UI 추가 | 상품코드·만기·유동성·empty 처리 | capability disabled 유지 |
| 7 | frontend cutover | `대시보드 | 종목 | 파생` 화면이 새 `/api/market-data/v1/*`를 소비 | API/Zod 계약, 탭별 URL·상태 보존, lint, test, build, 장중 수동 확인 | 기존 `/argus` 유지 또는 route flag 복귀 |
| 8 | 레거시 정리 판단 | 소비자·데이터 전환 확인 후 제거 범위 별도 승인 | 전체 검색, 회귀 테스트, DB 백업 | 제거 전 tag/백업과 별도 Plan |

한 단계에서 실패하면 다음 단계로 진행하지 않는다. 단계 8은 이 Plan의 자동 실행 범위가 아니며 별도 승인 대상이다.

## 7. 성공·실패·데이터 흐름

- 성공 흐름: scheduler → capability collector → provider adapter → normalized fact → idempotent storage → query API → frontend
- 실패 흐름: provider error → provider run 실패 기록 → 해당 capability stale/missing → 다른 capability 정상 제공
- 데이터 변환: 공급자 필드 → 명시적 unit·currency·market_scope → 내부 fact
- 재시도: 공급자별 제한된 retry와 backoff, rate limit 시 다음 schedule로 이월
- 멱등성: provider·capability·instrument·observed_at·quality 기반 중복 방지
- 보상: 잘못 저장한 fact를 덮어쓰지 않고 무효화 또는 교정 fact를 추가하는 정책을 구현 단계에서 확정

## 8. 테스트와 검증 계획

- 단위 테스트:
  - 공급자 fixture 정규화
  - 단위·부호·시장 범위 변환
  - estimate/confirmed와 freshness 판정
- 통합·계약 테스트:
  - migration과 idempotent insert
  - provider batch 성공·부분 실패·전체 실패
  - API Pydantic와 frontend Zod 계약
- 경계·실패 테스트:
  - 인증 실패, 429, timeout, 부분 응답, 장외, stale
  - KOSPI200 구성종목 일부 누락
  - collector 중복 실행
- Formatter·Lint·타입:
  - `pnpm --filter frontend lint`
  - `PYTHONPYCACHEPREFIX=/private/tmp/argus_pycache python3 -m compileall backend/src`
  - `pnpm check:boundaries`
- 테스트·빌드:
  - `pytest -q backend/tests`
  - `pnpm --filter frontend test`
  - `pnpm --filter frontend build`
- 수동 확인:
  - 장중 KOSPI 수급, 삼성전자·SK하이닉스 수급과 증권사 화면 대조
  - 장 마감 확정치 reconciliation

## 9. 문서 영향

- Project Specification: 승인 후 `APPROVED`, 실제 범위에 맞춰 갱신
- Architecture·ADR: 사용자 승인 후 ADR을 `ACCEPTED`
- Domain·Flow: 첫 수직 기능 구현 시 market data domain과 collector flow 작성
- API·Database: 신규 공개 API와 additive migration이 생기는 단계에서 작성
- 기존 `doc/`: 실제 cutover 전까지 현재 상태 문서로 유지하고 구현 결과에 맞춰 동기화

## 10. 복구와 위험 완화

- 주요 위험: 데이터 의미 혼용, 호출 제한, 공급자 장애, SQLite 부하, 기존 계약 회귀
- 예방·관찰:
  - provenance와 quality 필수화
  - provider health와 호출량 기록
  - feature flag와 병행 API
  - raw sample redaction과 fixture 보존
- rollback:
  - 신규 collector와 route feature flag 비활성
  - 기존 `/api/argus/v2/*`와 기존 테이블 사용
  - additive migration은 남겨두되 소비 중단
- roll-forward:
  - 교정 adapter 또는 새 migration 추가
  - 확정 데이터로 장중 추정치를 대체하지 않고 별도 fact 추가
- 중단 기준:
  - 약관 또는 호출 제한으로 KOSPI200 구성종목 수집이 허용되지 않음
  - 수급 데이터의 시각·단위·시장 범위를 검증할 수 없음
  - 시크릿이 로그·DB에 노출
  - 기존 API 또는 화면에 회귀 발생

## 11. 구현 후 대조

- 계획과 달라진 부분: 구현 전
- 달라진 이유: 구현 전
- 최종 검증 결과: 구현 전
- 갱신한 현재 상태 문서: 구현 전
- 남은 위험: live 계정 검증, 보존 기간, 개별주식 파생 지원 여부
