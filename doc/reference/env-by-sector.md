# Env By Sector

## 목적
- 실제로 값을 넣는 파일은 `backend/.env`입니다.
- 기준 템플릿은 루트의 `.env.example`입니다.
- 이 문서는 `어떤 섹터에 어떤 env가 있고`, `지금 당장 무엇만 채우면 되는지`를 빠르게 보려는 용도입니다.

## 지금 바로 채울 값

### KIS 파생 1차 live
- 공통 인증
  - `KIS_BASE_URL`
  - `KIS_APP_KEY`
  - `KIS_APP_SECRET`
  - `KIS_ACCESS_TOKEN`
- 국내 파생
  - `KIS_DOMESTIC_DERIVATIVES_PROVIDER=api`
  - `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON={"FID_INPUT_ISCD":"AUTO_KOSPI200_FRONT"}`

### FRED 거시 reference
- `FRED_PROVIDER=api`
- `FRED_API_KEY`

### Massive 거시 reference 예약 블록
- 아직 runtime에 연결되지 않았습니다. 지금 바로 채울 값은 아닙니다.
- 나중에 Massive adapter를 붙일 때 채울 예정인 최소 블록은 아래입니다.
  - `MASSIVE_PROVIDER`
  - `MASSIVE_BASE_URL`
  - `MASSIVE_API_KEY`
  - `MASSIVE_FOREX_CONVERSION_PATH`
  - `MASSIVE_FOREX_SNAPSHOT_PATH`
  - `MASSIVE_FOREX_TICKER`
  - `MASSIVE_FOREX_FROM_SYMBOL`
  - `MASSIVE_FOREX_TO_SYMBOL`
  - `MASSIVE_WTI_FUTURES_ENABLED`
  - `MASSIVE_WTI_FUTURES_SYMBOL`
  - `MASSIVE_TIMEOUT_SECONDS`
  - `MASSIVE_MAX_RETRIES`
  - `MASSIVE_BACKOFF_SECONDS`
- Massive Basic은 historical/reference-oriented 접근으로 보는 편이 안전합니다.
- env 값을 넣어도 runtime wiring이 없어서 지금은 활성화되지 않습니다.
- 공식 문서 기준 WTI/futures는 beta/coming soon 성격이어서 이 블록도 예약 상태로만 둡니다.

### 지금은 비워도 되는 값
- `KIS_MARKET_BREADTH_*`
- `KIS_NIGHT_FUTURES_*`
- `KRX_DERIVATIVES_REFERENCE_*`
- `FRED_FILE_PATH`
- `MASSIVE_*`

## 섹터별 정리

### 공통
- `BACKEND_BASE_URL`
  - 프런트가 백엔드를 호출할 주소입니다.
- `FRONTEND_ORIGIN`
  - 백엔드가 프런트 origin을 인지할 때 씁니다.
- `DB_PATH`
  - SQLite 경로입니다.
- `KRX_ADMIN_API_KEY`
  - 관리자 API 보호가 필요할 때만 씁니다.

### 뉴스 수집
- `DART_*`
  - 공시/회사 마스터 연동입니다.
- `MK_RSS_*`
  - 매경 RSS 수집입니다.
- `NAVER_NEWS_*`
  - 뉴스 검색 수집입니다.
- `NAVER_DATALAB_*`
  - 관심도/검색량 계열 보조 지표입니다.

### 뉴스 AI
- `NEWS_PRODUCT_BATCH_TRIAGE_*`
  - 1차 뉴스 묶음 판단입니다.
- `NEWS_PRODUCT_EDITORIAL_AI_*`
  - 2차 표면 편집/비교 AI입니다.

### 이벤트 정규화 AI
- `EVENT_PIPELINE_*`
  - raw document를 event로 정규화할 때 씁니다.

### 시장 신호 / 파생
- 공통 collector
  - `MARKET_BRIEFING_*`
- KIS breadth
  - `KIS_MARKET_BREADTH_*`
- KIS domestic derivatives
  - `KIS_DOMESTIC_DERIVATIVES_*`
- KIS night futures
  - `KIS_NIGHT_FUTURES_*`
- KRX reference
  - `KRX_DERIVATIVES_REFERENCE_*`

### 글로벌 이벤트
- `GLOBAL_EVENTS_SYNC_*`
  - 공식 캘린더/발표 일정 수집입니다.
- `GLOBAL_EVENTS_VENDOR_*`
  - 외부 vendor adapter입니다.
- `GLOBAL_EVENTS_LLM_*`
  - 이벤트 영향 해석용 AI입니다.

### 거시 금리 reference
- `FRED_*`
  - 현재 runtime macro reference source입니다.
  - 현재는 `DEXKOUS`, `DCOILWTICO`, `DGS10`, `FEDFUNDS`를 씁니다.
  - daily/monthly reference 용도이며, 실시간 trading feed는 아닙니다.
- `MASSIVE_*`
  - 현재는 예약 블록만 있습니다.
  - 실제 runtime은 아직 `FRED_*`만 macro reference source로 사용합니다.
  - env 존재만으로는 활성화되지 않습니다.
  - 향후 Massive adapter가 생기면 historical/reference 후보로 다시 검토합니다.

### 회사 리포트
- `COMPANY_REPORT_*`
  - 유니버스와 보고서 생성 파이프라인입니다.

## 현재 1차 운영 권장안

### 뉴스
- 켜둘 값
  - `MK_RSS_ENABLED=true`
  - `NAVER_NEWS_ENABLED=true`
- 필요 시 추가
  - `NAVER_DATALAB_ENABLED=true`

### KIS 파생
- 필수
  - `KIS_APP_KEY`
  - `KIS_APP_SECRET`
  - `KIS_ACCESS_TOKEN`
  - `KIS_DOMESTIC_DERIVATIVES_PROVIDER=api`
  - `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON={"FID_INPUT_ISCD":"AUTO_KOSPI200_FRONT"}`
- 선택
  - `KIS_MARKET_BREADTH_PROVIDER`
  - `KIS_NIGHT_FUTURES_PROVIDER`

### FRED
- 필수
  - `FRED_PROVIDER=api`
  - `FRED_API_KEY`

### Massive
- 아직 채우지 않습니다.
- `.env.example`에 있는 `MASSIVE_*`는 adapter 구현 전에 자리만 잡아둔 예약 블록입니다.
- Massive Basic을 써도 real-time quote/conversion/snapshot entitlement를 전제하지 않습니다.

## 주의
- 현재 코드는 `KIS_ACCESS_TOKEN` 자동 발급/갱신을 하지 않습니다.
- KIS는 유효한 bearer token을 직접 넣어야 합니다.
- `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON`가 비어 있으면 국내 파생 API 모드가 비활성 처리됩니다.
- `MASSIVE_*`는 현재 코드가 읽지 않습니다. 값을 넣어도 아직 runtime에는 영향이 없습니다.
- Massive Basic은 historical/reference-oriented로 표현하는 편이 안전하고, conversion entitlement도 Basic에서 보장된다고 쓰지 않습니다.
- Massive 공식 문서 기준 WTI/futures는 beta/coming soon이라 `MASSIVE_WTI_FUTURES_*`는 실제 adapter 구현 전까지 비워두는 편이 안전합니다.
- 의미 있는 활성화 확인은 env 값이 아니라 route output, source label, UI provenance로 봅니다.
- 실제 `backend/.env`에 섹션이 빠져 있으면 `.env.example`의 같은 블록을 복사해 추가하면 됩니다.
