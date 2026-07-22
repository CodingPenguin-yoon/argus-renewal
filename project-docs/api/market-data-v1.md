# Market Data API v1

- 상태: `CURRENT`
- 최종 검토일: `2026-07-22`
- 구현 위치: `backend/src/market_data/market_flow/api.py`

## GET `/api/market-data/v1/dashboard/market-flow`

저장된 KRX 시장 수급 fact를 대시보드용으로 조회한다. 이 요청 경로는 provider를 호출하거나 fixture를 생성하지 않는다.

### Query

| 이름 | 값 | 기본값 | 의미 |
|---|---|---|---|
| `data_mode` | `mock`, `live` | `MARKET_DATA_MODE` (`mock`) | fixture와 live fact를 혼합하지 않는 조회 경계 |

`live` adapter는 아직 구현되지 않았으므로 현재 `data_mode=live`는 정상 HTTP 응답 안에서 `status=missing`을 반환한다.

### 응답

최상위 필드:

| 필드 | 의미 |
|---|---|
| `as_of` | freshness 판정 기준이 된 timezone-aware 시각 |
| `data_mode` | 이번 조회의 `mock` 또는 `live` 모드 |
| `is_live` | `data_mode=live` 여부 |
| `market_scope` | 1차 범위인 `KRX` |
| `status` | 전체 coverage 상태 |
| `rows` | 고정된 네 시장 segment |

`rows` 순서는 `kospi_spot`, `kospi200_futures`, `kospi200_call`, `kospi200_put`이다. 각 row는 `estimate`와 `confirmed`를 별도 객체로 제공하며 누락 시 `null`이다.

fact 필수 provenance:

- `source`, `source_record_id`
- `data_mode`, `is_live`, `market_scope`
- `quality`: `estimate` 또는 `confirmed`
- `trade_date`, `observed_at`, `collected_at`
- `freshness`, `unit`
- `individual_net`, `foreign_net`, `institution_net`

금액 단위는 현재 `KRW`이고 값은 정수다.

### 상태 판정

- row의 두 fact가 모두 없으면 `missing`
- 둘 중 하나만 있으면 `partial`
- 둘 다 있고 하나 이상 오래됐으면 `stale`
- 둘 다 신선하면 `fresh`
- 전체가 모두 `missing`이면 dashboard도 `missing`
- 일부 row가 `missing` 또는 `partial`이면 dashboard는 `partial`
- 그 외 하나 이상 `stale`이면 dashboard는 `stale`

freshness 임계값은 `MARKET_FLOW_ESTIMATE_STALE_AFTER_SECONDS`와 `MARKET_FLOW_CONFIRMED_STALE_AFTER_SECONDS`로 설정한다.

### 실패 계약

- 잘못된 `data_mode`는 FastAPI validation error를 반환한다.
- 저장소의 예상하지 못한 오류는 공통 500 응답으로 변환된다.
- 데이터 없음은 오류가 아니라 `status=missing`과 null fact로 표현한다.
- frontend는 HTTP·Zod 오류를 mock fallback으로 숨기지 않고 API 오류 상태로 표시한다.

