# Database Tables

현재 코드 기준으로 뉴스 리빌드에서 중요한 DB 테이블과 migration을 공부하기 위한 문서입니다.

## 이 문서의 목적
- "어떤 테이블이 언제 생겼고 누가 읽고 쓰는지"를 빠르게 이해하게 합니다.
- raw ingestion, event pipeline, market surface materialization을 구분해서 봅니다.

## 먼저 기억할 분류
- 입력 계층
  - `raw_documents` 중심
- event 정규화 계층
  - `events`, `event_extractions` 중심
- 뉴스 탭 표면 계층
  - `news_batch_triage`, `market_surface_*`

## 주요 migration

### `010_provider_registry.sql`
- provider registry 도입
- `raw_document_fetch_runs`
- `raw_document_sources`
- `raw_documents`
- `raw_document_dedup_keys`
- event/legacy 테이블 재정비

### `011_publisher_registry.sql`
- `publisher_registry`
- `raw_documents.publisher_key`
- `events.publisher_key`

### `012_document_observed_time.sql`
- `raw_documents.observed_at`
- `raw_documents.published_at_source`
- effective time index

### `003_event_pipeline.sql`
- `events`
- `event_company_edges`
- `event_extractions`
- `event_review_queue`

### `016_market_surface_materialization.sql`
- `news_batch_triage`
- `market_surface_candidates`
- `market_surface_state`
- `market_surface_history`

## 1. 입력 계층

### `provider_registry`
- provider 의미를 저장합니다.
- 예:
  - `provider_family`
  - `source_type`
  - `storage_policy`
  - `trust_score`
  - `priority`

### `publisher_registry`
- 실제 발행 매체를 관리합니다.
- provider와 publisher를 분리해 품질/coverage 분석 기준을 만듭니다.

### `raw_document_fetch_runs`
- 배치 실행 이력
- 어떤 provider를 언제 어떻게 돌렸는지 기록

### `raw_document_sources`
- provider별 source cursor와 source metadata
- company/theme/system source 구분

### `raw_documents`
- 가장 중요한 입력 테이블
- 문서 원문 메타데이터를 저장

### 중요한 컬럼
- `provider`
- `provider_document_id`
- `document_type`
- `title`
- `summary`
- `publisher`
- `publisher_key`
- `source_url`
- `canonical_url`
- `published_at`
- `observed_at`
- `published_at_source`
- `company_id`
- `query_text`
- `is_duplicate`
- `duplicate_of_document_id`
- `provider_metadata_json`
- `raw_payload_json`

### `raw_document_dedup_keys`
- dedup lookup용 테이블
- provider id 기반 또는 url/title 기반 dedup key를 저장

## 2. event pipeline 계층

### `events`
- 문서에서 추출된 이벤트 본체

### 중요한 컬럼
- `dedup_key`
- `primary_document_id`
- `event_type`
- `sentiment`
- `source_type`
- `source_provider`
- `publisher_key`
- `occurred_at`
- `trust_score`
- `confidence`
- `status`
- `metadata_json`

### `event_company_edges`
- 이벤트와 회사의 관계
- direct / indirect / theme tier를 표현

### `event_extractions`
- 문서별 추출 결과
- 문서 한 건당 event extraction 상태를 저장

### 중요한 컬럼
- `raw_document_id`
- `event_id`
- `extraction_method`
- `llm_provider`
- `llm_model`
- `parse_status`
- `output_json`
- `error_message`
- `confidence`

### `event_review_queue`
- 사람이 검토해야 하는 이벤트 queue

## 3. 뉴스 탭 표면 계층

### `news_batch_triage`
- 뉴스 탭 1차 source-of-truth
- 문서별 시장 관련성 판단을 저장

### 중요한 컬럼
- `raw_document_id`
- `batch_key`
- `cluster_key`
- `provider`
- `document_type`
- `market_scope`
- `primary_region`
- `market_importance_prelim`
- `impact_direction`
- `reason_short`
- `affected_companies_json`
- `related_sectors_json`
- `keyword_tags_json`
- `triage_metadata_json`

### `triage_metadata_json`에 주로 담기는 것
- `event_type`
- `event_subtype`
- `impact_horizon`
- `source_type`
- `canonical_anchor`
- `triage_method`
- `triage_provider`
- `triage_model`
- `triage_confidence`
- `triage_raw_output`

### `market_surface_candidates`
- 화면 후보 카드 read model

### 중요한 컬럼
- `candidate_key`
- `card_key`
- `surface_key`
- `cluster_key`
- `source_kind`
- `source_document_ids_json`
- `title`
- `one_line_summary`
- `why_it_matters`
- `market_impact`
- `market_scope`
- `primary_region`
- `trust_score`
- `materiality_score`
- `novelty_score`
- `attention_score`
- `cross_source_score`
- `editorial_score`
- `ranking_score`
- `evidence_count`
- `payload_json`

### `payload_json`에 들어가는 성격
- evidence
- provenance
- story_state
- importance_label
- editorial_reason
- ai_confidence
- 정렬에 쓰인 추가 맥락

### `market_surface_state`
- surface별 현재 대표 카드 상태
- `surface_key`는 유니크

### 주요 값
- `surface_key`
- `active_candidate_key`
- `state_json`

### `state_json`의 의미
- "지금 화면에서 무엇이 대표인지"를 빠르게 읽기 위한 요약 스냅샷
- lead title, ranking, AI provenance까지 포함

### `market_surface_history`
- surface 상태 변경 이력

### 중요한 컬럼
- `surface_key`
- `candidate_key`
- `change_type`
- `snapshot_json`
- `created_at`

### 현재 `change_type` 예시
- `refresh`
  - 대표 카드가 바뀌었을 때
- `metadata_update`
  - 같은 대표 카드지만 설명/중요도/AI provenance가 바뀌었을 때

## 4. 테이블 관계를 간단히 보면
```text
raw_document_fetch_runs
-> raw_document_sources
-> raw_documents
-> news_batch_triage
-> market_surface_candidates
-> market_surface_state
-> market_surface_history

raw_documents
-> event_extractions
-> events
-> event_company_edges
-> event_review_queue
```

## 5. 누가 읽고 누가 쓰나

### `raw_documents`
- 쓰기:
  - `RawDocumentIngestionService`
- 읽기:
  - `NewsProductService`
  - `EventNormalizationService`

### `news_batch_triage`
- 쓰기:
  - `NewsProductService`
- 읽기:
  - `NewsProductService`

### `market_surface_candidates/state/history`
- 쓰기:
  - `NewsProductService`
- 읽기:
  - `NewsProductService`
  - `/api/news/*`

### `events/event_extractions`
- 쓰기:
  - `EventNormalizationService`
- 읽기:
  - `/api/krx/news/events/*`

## 6. 공부할 때 자주 하는 실수
- `events`가 뉴스 탭 메인 표면의 source-of-truth라고 착각함
- `raw_documents`를 곧바로 프런트 카드 데이터로 생각함
- `payload_json`, `triage_metadata_json`, `state_json`이 각각 다른 목적이라는 점을 놓침

## 7. 추천 학습 순서
1. `raw_documents`
2. `news_batch_triage`
3. `market_surface_candidates`
4. `market_surface_state`
5. `event_extractions`
6. `events`

## 다음 문서
- `03_backend_materialization.md`
- `07_file_by_file_reference.md`
