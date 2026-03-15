# Backend Ingestion And Automation

현재 코드 기준으로 뉴스 리빌드의 "수집과 자동화" 경로를 공부하기 위한 문서입니다.

## 이 문서의 범위
- `backend/src/krx/source_ingestion/cli.py`
- `backend/src/krx/source_ingestion/schedule.py`
- `backend/src/krx/source_ingestion/service.py`
- `backend/src/krx/source_ingestion/event_service.py`
- `backend/src/krx/source_ingestion/providers/*.py`
- `backend/src/config/env.py`

## 왜 이 레이어가 먼저 필요한가
- 뉴스 탭 화면은 결국 DB를 읽습니다.
- 따라서 먼저 "DB에 어떤 원문이 어떻게 들어오는지"를 이해해야 이후 triage/materialization이 이해됩니다.

## 1. 진입점: `cli.py`

### 이 파일의 역할
- 운영 배치의 진입 파일입니다.
- 사람이 직접 실행하는 명령도 여기 있고, `cron`이 호출하는 명령도 여기 있습니다.
- 뉴스 리빌드에서 가장 중요한 명령은 `run-news-automation` 입니다.

### 중요한 함수
- `_sync_scheduled()`
  - 설정에 따라 공시/뉴스 provider를 돌립니다.
- `_normalize_events()`
  - event pipeline을 수동 또는 automation에서 실행합니다.
- `_refresh_news_product_materialization()`
  - 뉴스 탭 materialization을 재생성합니다.
- `_run_news_automation()`
  - cadence 계산 후 due tick이면 `sync -> normalize -> refresh`를 수행합니다.

### 공부 포인트
- 이 파일은 "직접 뉴스 로직을 계산"하지 않습니다.
- 어디까지나 여러 서비스 호출 순서를 결정하는 orchestration 파일입니다.

## 2. cadence 계산: `schedule.py`

### 이 파일의 역할
- "지금 실행해야 하는 시각인지"를 계산합니다.
- 장중/장후/비장중을 구분합니다.

### 중요한 값
- `MARKET_OPEN_PHASE`
- `POST_CLOSE_PHASE`
- `OFF_HOURS_PHASE`

### 핵심 함수
- `resolve_news_automation_cadence(...)`

### 계산 결과
- `phase`
- `cadence_minutes`
- `should_run`
- `next_due_at`

### 지금 기준 cadence
- 장중: 1분
- 장 종료 직후: 5분
- 비장중: 10분
- 휴장일 override:
  - `RAW_INGESTION_AUTOMATION_HOLIDAY_DATES`

## 3. raw ingestion 본체: `service.py`

### 이 파일의 역할
- 외부 provider에서 문서를 받아 `raw_documents`에 적재합니다.
- dedup, provider registry, publisher registry, source cursor를 관리합니다.

### 핵심 클래스
- `RawDocumentIngestionService`

### 생성 시 주입되는 provider
- `DartDisclosureProvider`
- `MkRssNewsProvider`
- `NaverNewsProvider`
- optional `BigKindsNewsProvider`

### 중요한 메서드 축
- provider descriptor 생성
  - 어떤 provider가 어떤 source kind를 지원하는지 정의
- fetch
  - provider별 요청을 날려 `RawDocumentCandidate` 목록을 받음
- upsert
  - candidate를 `raw_documents`와 관련 테이블에 저장

### 이 파일이 쓰는 핵심 테이블
- `provider_registry`
- `publisher_registry`
- `raw_document_fetch_runs`
- `raw_document_sources`
- `raw_documents`
- `raw_document_dedup_keys`

## 4. provider adapter

### `providers/dart_provider.py`
- DART 공시를 가져옵니다.
- 공식 공시 소스입니다.
- `document_type=DISCLOSURE` 중심입니다.

### `providers/mk_rss_provider.py`
- 매일경제 RSS에서 curated news를 가져옵니다.
- discovery가 아니라 상대적으로 더 안정적인 근거 source에 가깝습니다.

### `providers/naver_news_provider.py`
- 네이버 뉴스 검색으로 discovery 성격의 뉴스를 가져옵니다.
- 탐지/보강용에 가깝고, 메인 canonical evidence와는 역할이 다릅니다.

### provider들이 공통으로 맞추는 출력
- `RawDocumentCandidate`
- 즉 외부 응답 형태는 달라도 내부 저장 직전에는 같은 형식으로 맞춥니다.

## 5. event normalization 경계: `event_service.py`

### 왜 뉴스 탭 문서에서 이 파일을 같이 보나
- 이름이 비슷해서 많은 사람이 뉴스 탭 핵심 서비스로 오해합니다.
- 실제로는 `/api/krx/news/events/*`용 event pipeline입니다.

### 핵심 클래스
- `EventNormalizationService`

### 핵심 메서드
- `normalize_pending_documents()`
- `list_recent_events()`
- `list_company_events()`

### 이 파일의 역할
- `raw_documents` 중 아직 event extraction이 없는 문서를 집음
- 필요하면 LLM 또는 fallback rule로 event를 추출
- `events`, `event_company_edges`, `event_extractions`, `event_review_queue`를 갱신

### 중요한 점
- 뉴스 탭 main surface는 이 테이블들을 직접 source-of-truth로 읽지 않습니다.
- automation에서는 이 경로를 기본 deterministic으로 유지해, 뉴스 자동화가 문서별 LLM fan-out을 만들지 않게 해둔 상태입니다.

## 6. 관련 env: `env.py`

### automation 관련
- `RAW_INGESTION_AUTOMATION_TIMEZONE`
- `RAW_INGESTION_AUTOMATION_WEEKDAYS`
- `RAW_INGESTION_AUTOMATION_MARKET_OPEN_TIME`
- `RAW_INGESTION_AUTOMATION_MARKET_CLOSE_TIME`
- `RAW_INGESTION_AUTOMATION_POST_CLOSE_END_TIME`
- `RAW_INGESTION_AUTOMATION_MARKET_OPEN_INTERVAL_MINUTES`
- `RAW_INGESTION_AUTOMATION_POST_CLOSE_INTERVAL_MINUTES`
- `RAW_INGESTION_AUTOMATION_OFF_HOURS_INTERVAL_MINUTES`
- `RAW_INGESTION_AUTOMATION_HOLIDAY_DATES`
- `RAW_INGESTION_AUTOMATION_NORMALIZE_INCLUDE_LLM`
- `RAW_INGESTION_AUTOMATION_REFRESH_MODE`

### provider 관련
- `DART_*`
- `MK_RSS_*`
- `NAVER_NEWS_*`
- `NAVER_DATALAB_*`

### event pipeline 관련
- `EVENT_PIPELINE_*`
- `EVENT_PIPELINE_LLM_*`

## 7. 실제 실행 순서 예시
1. cron이 `run-news-automation`을 호출
2. `schedule.py`가 지금 due tick인지 계산
3. due가 아니면 종료
4. due면 `sync-scheduled`
5. provider adapter가 문서를 가져와 `raw_documents` 적재
6. event freshness 유지를 위해 `normalize-events`
7. 마지막에 뉴스 탭 materialization refresh

## 자주 헷갈리는 점
- `cli.py`는 계산기보다 지휘자에 가깝습니다.
- `service.py`는 입력 적재 담당이고, 뉴스 카드 랭킹은 하지 않습니다.
- `event_service.py`는 뉴스 탭 메인 표면이 아니라 event API를 위한 경로입니다.

## 먼저 읽으면 좋은 코드
- `backend/src/krx/source_ingestion/cli.py`의 `_run_news_automation`
- `backend/src/krx/source_ingestion/schedule.py`의 `resolve_news_automation_cadence`
- `backend/src/krx/source_ingestion/service.py`의 `RawDocumentIngestionService`

## 다음 문서
- `03_backend_materialization.md`
- `06_database_tables.md`
