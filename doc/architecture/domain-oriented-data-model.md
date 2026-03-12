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
  - `source_documents`
  - `normalized_events`
  - `event_evidence`
  - `event_tags`
  - `news_cards`
  - `source_coverage`
  - `market_briefings`
  - `company_reports`

## 어떤 경우에 새 테이블을 만들까

새 provider가 들어온다는 이유만으로 새 테이블을 만들지 않습니다.

아래 둘 중 하나일 때만 새 도메인 테이블을 검토합니다.

- 입력 구조와 조회 방식이 기존 도메인과 거의 안 겹칠 때
- 보관 정책, 인덱스 전략, 갱신 주기가 기존 도메인과 완전히 다를 때

예시:
- `매일경제 RSS`, `NAVER_NEWS`, `BIGKINDS`:
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
- dedup과 이벤트화는 기존 파이프라인을 재사용한다.

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
- `raw_documents`, `events`, `source_documents`, `event_evidence`에 `publisher_key` 축을 추가했다.
- `raw_documents`와 `source_documents`에는 `observed_at`, `published_at_source` 축을 추가했다.
- 즉 이제 같은 언론사가 여러 provider를 통해 들어와도 `provider`와 `publisher`를 분리해서 추적할 수 있다.
- 뉴스는 원문 발행 시각이 없어도 `observed_at`으로 시간 축이 끊기지 않게 했다.

## 다음 단계 우선순위

1. RSS/무인증 뉴스 provider를 `Document Intelligence` 도메인에 추가
2. `publisher_key` 기준 coverage/품질 지표를 붙일지 결정
3. 시장 데이터 계열도 장기적으로 provider registry와 유사한 실행 규칙으로 맞추기
4. `company_source_mappings`의 `DART|KIS` 고정은 별도 도메인 작업으로 분리
