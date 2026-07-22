# Market Flow 저장 계약

- 상태: `CURRENT`
- 최종 검토일: `2026-07-22`
- migration: `backend/src/market_data/migrations/market_data_001_market_flow.sql`

## 소유 테이블

`market_data_market_flow_facts`는 새 시장 수급 capability가 소유한다. 기존 `argus_v2_*` 테이블을 수정하거나 덮어쓰지 않는 additive schema다.

## 핵심 컬럼

| 분류 | 컬럼 | 규칙 |
|---|---|---|
| provenance | `source`, `source_record_id` | 원본 공급자와 공급자 record 식별자 |
| 실행 모드 | `data_mode` | `mock`, `live` |
| 시장 | `market_scope` | 현재 `KRX`만 허용 |
| 구간 | `segment` | `kospi_spot`, `kospi200_futures`, `kospi200_call`, `kospi200_put` |
| 품질 | `quality` | `estimate`, `confirmed` |
| 시간 | `trade_date`, `observed_at`, `collected_at` | 거래일과 공급자 관측·Argus 수집 시각 분리 |
| 단위 | `unit` | 현재 `KRW` |
| 수급 | `individual_net`, `foreign_net`, `institution_net` | 순매수 금액 정수, 매수 우위 양수·매도 우위 음수 |

## 멱등성과 최신 선택

- unique key: `(source, data_mode, source_record_id)`
- 같은 fixture minute를 다시 수집하면 기존 row를 유지하고 새 row를 만들지 않는다.
- 조회 index는 `data_mode, market_scope, segment, quality, observed_at DESC, id DESC` 순서다.
- repository는 mode 안에서 segment·quality별 최신 row 하나를 선택한다.
- ISO 8601 문자열 정렬이 timezone offset에 따라 달라지지 않도록 `observed_at`과 `collected_at`은 저장 시 UTC로 정규화한다.

## estimate와 confirmed

- 두 quality는 별도 fact이고 한쪽이 다른 쪽을 갱신하거나 승격하지 않는다.
- fixture에서 `FIXTURE_BROKER`는 장중 `estimate`, `FIXTURE_KRX`는 마감 `confirmed` 역할을 시뮬레이션한다.
- fixture source는 실제 증권사·KRX 응답이 아니며 항상 `data_mode=mock`이다.

## migration과 transaction

- 저장 경로에서 `backend/src/market_data/db.py`가 `schema_migrations`에 migration 파일명을 기록한다.
- 적용한 migration 파일은 수정하지 않고 후속 변경은 새 SQL migration으로 추가한다.
- batch 저장은 하나의 SQLite connection transaction 안에서 수행된다.
- 조회 경로는 기존 DB를 read-only로 열며 DB 또는 테이블이 없으면 migration 없이 빈 결과를 반환한다.
- 현재 DB 파일은 레거시와 동일한 `DB_PATH`를 사용할 수 있으나 테이블 namespace와 repository 소유권은 분리한다.

## 남은 정책

- 보존 기간과 archive 정책은 미결정이다.
- correction·invalidation 계약은 live provider 도입 전에 확정해야 한다.
- 여러 collector에 대한 새 경계의 lease/single-writer 보호는 아직 구현되지 않았다.
