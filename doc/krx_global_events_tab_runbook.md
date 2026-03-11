# KRX 글로벌 이벤트 탭 Runbook

## 목적
- `/krx/global-events` 탭을 해외 매크로 일정의 raw feed가 아니라 한국 증시용 catalyst view로 운영합니다.
- 공식 캘린더와 공식 데이터 소스를 기본으로 쓰고, forecast/importance/대형 기술주 실적은 선택 vendor가 있을 때만 확장합니다.
- 예상치나 실제값이 없으면 숫자를 채워 넣지 않고 `미제공`, `발표 전`, `시간 미정`으로 명시합니다.

## 소스 맵

### 이벤트 타입별 우선 소스
- `FOMC`
  - 일정: `Federal Reserve FOMC Calendar`
  - 실제값: 기본 미제공
  - forecast / importance: optional vendor
- `CPI`
  - 일정: `BLS Release Calendar`
  - 실제값: `BLS Public Data API`
  - forecast / importance: optional vendor
- `PCE`
  - 일정: `BEA Release Schedule`
  - 실제값: `BEA PCE Price Index` 공식 페이지
  - forecast / importance: optional vendor
- `PAYROLLS`
  - 일정: `BLS Release Calendar`
  - 실제값: `BLS Public Data API`
  - forecast / importance: optional vendor
- `ECB`
  - 일정: `ECB Governing Council Calendar`
  - 실제값: 기본 미제공
  - forecast / importance: optional vendor
- `BOJ`
  - 일정: `BOJ Monetary Policy Meeting Schedule`
  - 실제값: 기본 미제공
  - forecast / importance: optional vendor
- `EARNINGS`
  - 일정 / forecast / importance / actual: optional vendor

## 필수 vs 선택 provider

### 필수 공식 소스
- `GLOBAL_EVENTS_FED_CALENDAR_URL`
- `GLOBAL_EVENTS_BLS_CALENDAR_URL`
- `GLOBAL_EVENTS_BLS_API_URL`
- `GLOBAL_EVENTS_BEA_SCHEDULE_URL`
- `GLOBAL_EVENTS_BEA_PCE_URL`
- `GLOBAL_EVENTS_ECB_CALENDAR_URL`
- `GLOBAL_EVENTS_BOJ_CALENDAR_URL`

### 선택 확장 소스
- `GLOBAL_EVENTS_VENDOR_PROVIDER`
- `GLOBAL_EVENTS_VENDOR_FILE_PATH`
- `GLOBAL_EVENTS_VENDOR_BASE_URL`
- `GLOBAL_EVENTS_VENDOR_SCHEDULE_PATH`
- `GLOBAL_EVENTS_VENDOR_API_KEY`
- `GLOBAL_EVENTS_VENDOR_REQUIRED`

### 선택 LLM
- `GLOBAL_EVENTS_LLM_ENABLED`
- `GLOBAL_EVENTS_LLM_PROVIDER`
- `GLOBAL_EVENTS_LLM_BASE_URL`
- `GLOBAL_EVENTS_LLM_API_KEY`
- `GLOBAL_EVENTS_LLM_MODEL`

## 저장 모델

### `global_event_schedule`
- source schedule에서 가져온 일정 레코드
- 핵심 필드
  - `event_time_kst`
  - `title`
  - `category`
  - `source_name`
  - `status`
  - `previous_event_time_kst`
  - `provenance_json`

### `global_event_releases`
- release 시점 데이터
- 핵심 필드
  - `previous_*`
  - `forecast_*`
  - `actual_*`
  - `surprise_*`
  - `release_state`
  - `provenance_json`

### `global_event_impacts`
- 한국 증시용 해석 카드
- 생성 방식
  - `rule_based`
  - `llm`

### `global_event_source_coverage`
- 일정/실제값/vendor별 동기화 상태
- 필수 여부(`is_required`)와 partial/missing 상태를 함께 저장

## release-state lifecycle
- `scheduled`
  - release row가 아직 없거나 이전값만 있는 상태
- `forecast_pending`
  - forecast는 들어왔지만 actual은 아직 없는 상태
- `actual_pending`
  - release 시각이 지났거나 임박했지만 actual이 아직 없는 상태
- `released`
  - actual이 들어온 상태
- `revised`
  - actual 또는 일정 시간이 수정된 상태

## 일정 변경 / 백필 / 수동 refresh

### CLI sync
```bash
cd backend
python3 -m src.krx.source_ingestion.cli sync-global-events \
  --start-date 2026-03-01 \
  --end-date 2026-03-31
```

### 관리자 API
```bash
curl -X POST "http://localhost:4000/api/krx/admin/global-events/sync?start_date=2026-03-01&end_date=2026-03-31"
```

### 변경된 schedule 재반영 원칙
- repeating release dates를 코드에 고정하지 않습니다.
- 같은 `event_key`가 다시 들어오면 upsert합니다.
- 시간이 바뀌면 `status='revised'`, `previous_event_time_kst`를 남깁니다.
- 같은 source window에서 더 이상 보이지 않는 future 일정은 `status='cancelled'`로 내립니다.

## 공개 API
- `GET /api/global-events/upcoming?window=24h`
- `GET /api/global-events/week`
- `GET /api/global-events/highlight`
- `GET /api/global-events/coverage`

## 관리자 API
- `POST /api/krx/admin/global-events/sync`

## 프론트 렌더링 원칙
- 왼쪽: 시간순 이벤트 리스트
- 오른쪽: 영향 해석 카드
- 모든 이벤트는 다음 필드를 우선 노출
  - `KST 시각`
  - `이벤트명`
  - `previous`
  - `forecast`
  - `actual`
  - `importance`
  - `why_it_matters_ko`
- 누락값은 `0`으로 대체하지 않습니다.

## 로컬 실행
```bash
pnpm dev:backend
pnpm dev:frontend

cd backend
python3 -m src.krx.source_ingestion.cli sync-global-events
```

브라우저:
- `http://localhost:3000/krx/global-events`

## 알려진 제한사항
- 기본 경로에서는 FOMC/ECB/BOJ의 actual 값이 비어 있을 수 있습니다.
- 대형 기술주 실적은 vendor가 없으면 일정이 비어 있습니다.
- BOJ/FOMC처럼 공식 캘린더가 정확한 시간을 주지 않는 경우 `시간 미정`으로 노출될 수 있습니다.
