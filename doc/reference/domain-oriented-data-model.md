# Domain-Oriented Data Model

Argus를 계속 확장할 때는 `출처별 테이블`보다 `도메인별 테이블` 구조를 유지하는 편이 안전합니다.

핵심 축은 세 가지입니다.

- `domain`: 데이터가 어떤 문제를 푸는가
- `provider`: 어떤 통로로 데이터를 가져왔는가
- `publisher`: 실제 기사나 공시를 발행한 원출처가 누구인가

예시:
- 네이버 뉴스에서 매일경제 기사를 가져오면
- `domain = DOCUMENT_INTELLIGENCE`
- `provider = NAVER_NEWS`
- `publisher = 매일경제`

즉 `provider`와 `publisher`는 같은 값이 아닐 수 있습니다.

## 추천 원칙
1. 테이블은 `domain` 기준으로 나눈다.
2. `provider`는 registry와 컬럼으로 관리한다.
3. `publisher`는 registry와 컬럼으로 관리한다.
4. 새 소스가 들어와도 가능한 한 기존 도메인 테이블을 재사용한다.
5. 완전히 다른 데이터 성격일 때만 새 도메인 테이블을 만든다.

## 현재 기준 도메인 맵

### 1) Company Master
- 목적: 회사/종목 기준 엔티티와 외부 식별자 매핑 관리
- 대표 테이블:
  - `companies`
  - `company_source_mappings`
  - `company_manual_overrides`
  - `sync_runs`

### 2) Document Intelligence
- 목적: 뉴스/공시 같은 문서형 raw 입력을 모으고 dedup까지 관리
- 대표 테이블:
  - `raw_document_fetch_runs`
  - `raw_document_sources`
  - `raw_documents`
  - `raw_document_dedup_keys`
  - `provider_registry`
  - `publisher_registry`

### 3) Event Intelligence
- 목적: raw 문서에서 시장 이벤트와 회사 영향도를 추출
- 대표 테이블:
  - `events`
  - `event_company_edges`
  - `event_extractions`
  - `event_review_queue`

### 4) Market Data Signals
- 목적: 수급/파생/트렌드/시계열 지표 적재
- 대표 테이블:
  - `market_daily_factors`
  - `market_intraday_snapshots`
  - `derivatives_daily_metrics`
  - `provider_health_checks`

### 5) Global Macro Calendar
- 목적: 해외 이벤트 일정, 발표치, 해석 영향 저장
- 대표 테이블:
  - `global_event_schedule`
  - `global_event_releases`
  - `global_event_impacts`
  - `global_event_source_coverage`

### 6) Product Surfaces
- 목적: 프런트 화면에 바로 쓰는 카드/클러스터/커버리지 결과물 생성
- 대표 테이블:
  - `news_batch_triage`
  - `market_surface_candidates`
  - `market_surface_state`
  - `market_surface_history`
  - `market_briefings`
  - `company_reports`

## Product Surfaces에서 뉴스 탭이 쓰는 경로
- 입력:
  - `raw_documents`
  - optional `event_extractions`
  - Naver Datalab score
- 1차 판단:
  - `news_batch_triage`
  - 기본은 deterministic
  - `NEWS_PRODUCT_BATCH_TRIAGE_*`를 켜면 짧은 뉴스 묶음을 1회 batch AI로 업그레이드
- 후보 생성:
  - `market_surface_candidates`
  - 뉴스와 핵심 공시를 같은 표면 후보 형식으로 정렬
- 2차 비교:
  - current surface와 top 후보를 compare하는 editorial pass
  - 결과는 candidate payload와 state metadata에 반영
- 최종 상태:
  - `market_surface_state`
  - `market_surface_history`

## 어떤 경우에 새 테이블을 만들까
새 provider가 들어온다는 이유만으로 새 테이블을 만들지 않습니다.

아래 둘 중 하나일 때만 새 도메인 테이블을 검토합니다.
- 입력 구조와 조회 방식이 기존 도메인과 거의 안 겹칠 때
- 보관 정책, 인덱스 전략, 갱신 주기가 기존 도메인과 완전히 다를 때

예시:
- `MK_RSS`, `NAVER_NEWS`, `BIGKINDS`:
  - 같은 `Document Intelligence` 도메인에 넣는 것이 맞음
- `NAVER_DATALAB`:
  - 문서가 아니라 추세 수치이므로 `Market Data Signals` 계열이 맞음
- 글로벌 경제지표 벤더:
  - 일정/발표/영향 모델이면 `Global Macro Calendar` 계열이 맞음

## 지금 추천하는 확장 규칙

### 뉴스/공시 provider를 추가할 때
- 새 테이블을 만들지 않는다.
- `raw_documents`에 넣는다.
- `provider_registry`에 provider 의미를 등록한다.
- `publisher_registry`에 실제 발행 매체를 등록한다.
- 뉴스 탭 표면은 `news_batch_triage -> market_surface_candidates -> market_surface_state` 경로를 재사용한다.

### 숫자/시계열 provider를 추가할 때
- `raw_documents`에 억지로 넣지 않는다.
- 시장 데이터 도메인 테이블로 바로 넣는다.
- 필요하면 provider health/run 테이블만 공통으로 쓴다.

### 새 제품 화면을 추가할 때
- raw 테이블을 늘리기보다 `Product Surfaces` 쪽 materialization을 추가한다.
- 기존 도메인 데이터를 조합해서 화면 전용 결과물을 만든다.

## 이번 단계에서 반영한 내용
- `provider_registry`는 유지한다.
- `publisher_registry`를 추가했다.
- `raw_documents`, `events`에 `publisher_key` 축을 추가했다.
- 뉴스 탭 표면은 `news_batch_triage`를 source-of-truth로 읽는다.
- 2차 AI는 `current surface vs top candidates` compare pass로 축소됐다.

## 다음 단계 우선순위
1. story continuity를 `cluster_key` 외의 더 안정적인 키로 보강
2. 휴장일 캘린더 자동 동기화 여부 결정
3. provider 추가 시 descriptor/config 외부화 범위를 더 넓힐지 결정
