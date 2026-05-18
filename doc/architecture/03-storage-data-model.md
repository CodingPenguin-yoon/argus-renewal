# 스토리지와 데이터 모델

## 역할

스토리지는 외부 provider가 가져온 데이터를 Argus 내부 기준으로 저장하고, dashboard builder가 최신 데이터를 안정적으로 읽을 수 있게 해줍니다.

현재 로컬 개발 DB는 SQLite입니다.

기본 원칙:

- provider 실행 이력을 남깁니다.
- 원본 샘플을 민감값 제거 후 저장합니다.
- 화면에 바로 필요한 형태가 아니라 domain snapshot 형태로 저장합니다.
- frontend는 DB를 직접 알지 않습니다.

## 주요 파일

```text
backend/src/argus_v2/db.py
backend/src/argus_v2/storage.py
backend/src/argus_v2/migrations/argus_v2_001_storage.sql
backend/src/argus_v2/migrations/argus_v2_002_reaction_triggers.sql
backend/src/argus_v2/migrations/argus_v2_003_spot_flow.sql
```

## DB 연결과 migration

`get_connection(settings.db_path)`가 SQLite connection을 만들고 migration을 적용합니다.

환경 변수:

```text
DB_PATH=data/argus.db
```

backend 실행 위치가 `backend/`이므로 실제 기본 경로는 보통 `backend/data/argus.db`입니다.

## 핵심 테이블

### `argus_v2_provider_runs`

provider 실행 단위입니다.

저장하는 것:

- provider key
- provider label
- endpoint
- status
- started_at
- finished_at
- observed_count
- expected_count
- missing fields
- error
- metadata

이 테이블은 “데이터가 왜 안 보이는가”를 확인할 때 가장 먼저 봅니다.

status 의미:

- `success`: 기대한 만큼 수신
- `partial`: 일부만 수신
- `failed`: 실행 실패
- `skipped`: 설정상 비활성 또는 필수 값 누락
- `running`: 실행 중

### `argus_v2_provider_samples`

외부 응답 raw sample입니다.

저장 전 민감값은 redaction합니다.

redaction 대상 예:

- `access_token`
- `app_key`
- `app_secret`
- `client_secret`
- `authorization`
- `token`

이 테이블의 목적:

- 외부 API 응답 형태 추적
- normalize 실패 디버깅
- AI 판단 payload 확인
- provider 품질 보정

### `argus_v2_derivatives_snapshots`

KIS 국내파생 기본 snapshot입니다.

대표 필드:

- trade_date
- snapshot_time
- session_type
- source_name
- instrument_code
- instrument_name
- price
- price_change
- change_rate
- volume
- open_interest
- put_call_ratio
- implied_volatility
- additional_metrics_json

`additional_metrics_json`에는 basis, market basis, open interest change rate 같은 보조 값이 들어갈 수 있습니다.

### `argus_v2_option_chain_snapshots`

옵션체인 snapshot 헤더입니다.

대표 필드:

- trade_date
- snapshot_time
- market_scope
- underlying_code
- underlying_name
- underlying_price
- expiry_date
- contract_month
- atm_strike
- expected_level_count
- observed_level_count
- freshness_state

### `argus_v2_option_chain_levels`

옵션체인의 행사가별 level입니다.

대표 필드:

- strike_price
- moneyness
- call_last_price
- call_change_rate
- call_volume
- call_open_interest
- call_open_interest_change
- put_last_price
- put_change_rate
- put_volume
- put_open_interest
- put_open_interest_change
- total_open_interest
- net_call_put_oi
- call_put_oi_ratio
- pressure_side

dashboard builder는 최신 snapshot과 직전 snapshot을 비교해 옵션 OI 변화 방향을 계산합니다.

### `argus_v2_market_reaction_snapshots`

현물 반응 snapshot입니다.

대표 필드:

- trade_date
- snapshot_time
- source_name
- kospi_change_rate
- kosdaq_change_rate
- kospi200_futures_change_rate
- advancing_count
- declining_count
- spot_foreign_net_buy
- spot_institution_net_buy
- spot_individual_net_buy
- summary
- freshness_state

현물 수급은 선물 수급이 아닙니다. 따라서 `spot_*` 필드로 분리되어 있습니다.

### `argus_v2_market_reaction_sectors`

현물 반응 snapshot에 연결되는 섹터 강약입니다.

대표 필드:

- snapshot_id
- role: `strong` 또는 `weak`
- name
- change_rate
- reason
- tone
- source_name
- observed_at

### `argus_v2_news_triggers`

AI 판단을 거쳐 시장 판단에 쓰는 뉴스/매크로 trigger입니다.

대표 필드:

- external_id
- title
- summary
- impact
- source_name
- published_at
- connection_strength
- freshness_state
- source_url

AI enrichment payload는 raw sample에 들어갑니다. dashboard builder가 raw sample에서 `_argus_ai`, `ai_enrichment`, `argus_ai_enrichment`를 찾아 `ai_reason`, `ai_confidence`, `affected_factors`로 만듭니다.

## 저장 흐름

provider 수집은 보통 `BriefingProviderBatch`를 반환합니다.

```text
BriefingProviderBatch
  records
  metadata
  disabled_reason
  retry_count
```

storage는 batch를 받아 아래 순서로 처리합니다.

```text
start_provider_run()
for each record:
  raw_payload가 있으면 save_provider_sample()
  record 종류 판별
  derivatives snapshot 저장
  option chain snapshot 저장
  market reaction snapshot 저장
  news trigger 저장
finish_provider_run()
```

record 종류 판별은 duck typing에 가깝습니다.

- `instrument_code`와 `snapshot_time`이 있으면 derivatives snapshot
- `levels`와 `expiry_date`가 있으면 option chain snapshot
- 현물 반응 관련 필드가 있으면 market reaction snapshot
- `title`과 `impact`가 있으면 news trigger

## 조회 흐름

dashboard builder는 최신 snapshot을 읽습니다.

주요 조회:

- `get_latest_derivatives_snapshot()`
- `get_latest_option_chain_snapshot()`
- `get_previous_option_chain_snapshot()`
- `get_latest_market_reaction_snapshot()`
- `get_latest_news_triggers()`
- `get_latest_provider_runs()`

`get_latest_news_triggers()`는 단순 최신순만 보지 않습니다. raw sample의 AI relevance score를 읽어 relevance가 높은 항목을 우선합니다.

## 데이터 freshness

각 snapshot에는 freshness 상태가 붙습니다.

- `fresh`
- `partial`
- `stale`
- `missing`

dashboard builder는 freshness를 화면 계약으로 전달하고, judgement engine은 freshness가 낮으면 confidence를 낮춥니다.

## 민감값 처리

raw sample 저장 전 `_redact_sensitive()`가 동작합니다.

민감값을 저장하지 않는 이유:

- DB 파일이 로컬에 남기 때문
- 디버깅을 위해 raw sample은 필요하지만 credential은 필요하지 않기 때문
- 나중에 로그나 샘플을 공유할 수 있게 하기 위해

## 스토리지 확장 원칙

새 데이터 source를 추가할 때는 아래 순서를 지킵니다.

1. provider record dataclass 추가 또는 기존 record 재사용
2. raw sample 저장
3. 별도 snapshot 테이블이 필요한지 판단
4. dashboard 계약에 바로 노출할지 판단
5. provider health에 반영
6. 테스트 fixture 추가

SQLite는 현재 로컬 MVP 기준입니다. 운영 규모가 커지면 PostgreSQL로 옮길 수 있도록 storage 책임은 `ArgusV2Storage`에 모아둡니다.
