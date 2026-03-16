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

### 지금은 비워도 되는 값
- `KIS_MARKET_BREADTH_*`
- `KIS_NIGHT_FUTURES_*`
- `KRX_DERIVATIVES_REFERENCE_*`
- `FRED_FILE_PATH`

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
  - 현재는 `DEXKOUS`, `DCOILWTICO`, `DGS10`, `FEDFUNDS`를 씁니다.

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

## 주의
- 현재 코드는 `KIS_ACCESS_TOKEN` 자동 발급/갱신을 하지 않습니다.
- KIS는 유효한 bearer token을 직접 넣어야 합니다.
- `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON`가 비어 있으면 국내 파생 API 모드가 비활성 처리됩니다.
- 실제 `backend/.env`에 섹션이 빠져 있으면 `.env.example`의 같은 블록을 복사해 추가하면 됩니다.
