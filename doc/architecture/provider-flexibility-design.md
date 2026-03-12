# Provider Flexibility Design

## 목표
- 뉴스/공시 출처를 나중에 계속 추가하거나 교체할 수 있게 만든다.
- 새 출처를 붙일 때 DB 스키마의 `CHECK(provider IN (...))`를 다시 뜯지 않게 만든다.
- 외부 응답 포맷은 출처마다 달라도 되고, 백엔드 내부 경계에서만 공통 형식으로 맞춘다.

## 핵심 원칙
- 외부 규격: provider마다 제각각이어도 괜찮다.
- 내부 규격: `RawDocumentCandidate`에서 공통 필드를 맞춘다.
- 원본 보존: `raw_payload_json`, `provider_metadata_json`은 그대로 저장한다.
- 의미 분리: provider 이름 자체가 의미를 갖지 않게 하고, provider의 성격은 `provider_registry`에서 읽는다.
- 축 분리: `provider`와 실제 기사 발행 매체인 `publisher`는 다른 값일 수 있으므로 함께 관리한다.

## 적용 범위
- 이번 변경 범위는 뉴스/공시 ingestion, event normalization, news product materialization이다.
- `company_master`의 `source_system = DART|KIS`는 회사 마스터 도메인이라 이번 범위에서 제외한다.

## 새 구조

### 1) 외부 adapter 계층
- 각 provider 클래스는 외부 응답을 읽고 `RawDocumentCandidate`로 변환한다.
- 예시:
  - DART -> 공시 메타데이터
  - BigKinds -> curated news
  - Naver News -> discovery news

### 2) 공통 내부 ingestion 계층
- 공통 테이블:
  - `raw_document_fetch_runs`
  - `raw_document_sources`
  - `raw_documents`
  - `raw_document_dedup_keys`
- 여기서는 provider 문자열을 자유 텍스트로 저장한다.

### 3) provider metadata 계층
- `provider_registry`
- 역할:
  - display name
  - provider family
  - source type
  - document kind
  - storage policy
  - trust score
  - priority

### 3-1) publisher metadata 계층
- `publisher_registry`
- 역할:
  - publisher key
  - display name
  - canonical name
- 목적:
  - 같은 언론사가 여러 provider를 통해 들어와도 같은 축으로 묶는다.
  - `provider`와 `publisher`를 분리해서 품질/coverage 분석 기준을 만든다.

### 4) 정규화/상품화 계층
- `events`
- `source_documents`
- `normalized_events`
- `event_evidence`
- `news_cards`
- `source_coverage`

## provider family
- `DISCLOSURE`
- `CURATED_NEWS`
- `DISCOVERY_NEWS`
- `TREND_SIGNAL`
- `MARKET_DATA`
- `REFERENCE_DATA`

현재 기본 seed:
- `DART`
- `BIGKINDS`
- `NAVER_NEWS`
- `NAVER_DATALAB`

## 왜 이 구조가 맞는가
- provider 이름은 바뀔 수 있지만, `DISCLOSURE`, `CURATED_NEWS`, `DISCOVERY_NEWS` 같은 의미 분류는 비교적 안정적이다.
- 이벤트 신뢰도, 저장 정책, coverage 우선순위는 provider 이름보다 의미 분류에 가깝다.
- 따라서 “출처 이름”과 “출처 성격”을 분리해야 새 출처 추가가 쉬워진다.

## 새 provider 추가 절차
1. provider adapter 추가
2. 외부 응답을 `RawDocumentCandidate`로 변환
3. provider key를 정한다
4. `provider_registry`에 의미를 등록한다
5. 필요한 sync entrypoint를 서비스/CLI에 연결한다

DB 스키마 변경은 원칙적으로 필요 없다.

## 데이터 규격 통일 여부
- 원본 응답은 통일할 필요 없다.
- 내부 경계에서만 통일하면 된다.
- 이 프로젝트에서 내부 공통 포맷은 `RawDocumentCandidate`다.

## 이번 구현에서 같이 보완한 점
- provider 이름 하드코딩을 줄이고 registry/fallback 기반으로 읽게 바꾼다.
- 뉴스 materialization에서 provider별 의미를 registry에서 읽게 한다.
- 최근 문서/이벤트 조회는 expression index를 추가해 스캔 비용을 낮춘다.

## 남는 제약
- 새로운 provider를 실제로 fetch하려면 adapter 코드는 여전히 필요하다.
- `company_master` 도메인의 `source_system`은 별도 설계 대상이다.
- trend provider를 여러 개 동시에 운영하는 구조는 이번 단계에서 부분 지원이다.

## 전환 로드맵

### 1단계: 저장 경계 안정화
- 목표: 새 provider를 넣어도 DB 마이그레이션 없이 `raw_documents -> events -> news_cards` 경로가 동작하게 유지한다.
- 상태: 적용됨
- 기준:
  - provider 이름은 자유 텍스트 저장
  - provider 의미는 `provider_registry`에서 읽음
  - registry에 없으면 `document_type` 기준 fallback 적용

### 2단계: 수집 orchestration 일반화
- 목표: `RawDocumentIngestionService`가 `DART`, `BIGKINDS`, `NAVER_NEWS` 분기문 대신 provider descriptor 목록을 순회하도록 바꾼다.
- 상태: 부분 적용
- 현재 상태:
  - `RawDocumentIngestionService` 내부에는 descriptor/runner 계층이 들어갔다.
  - 뉴스 provider는 descriptor 추가만으로 theme/company sync 대상에 합류할 수 있다.
  - 공시는 generic `sync_disclosures_window(provider=...)` 진입점이 생겼다.
  - CLI에는 `list-ingestion-providers`, `sync-disclosures`, `sync-news` 같은 generic 명령이 추가됐다.
  - schedule env도 provider CSV 필터를 읽을 수 있게 됐다.
  - 다만 factory는 아직 구체 provider 인스턴스 조합에 더 가깝다.
- 변경 방향:
  - `ProviderRunner` 또는 `IngestionProviderDescriptor` 개념 도입
  - descriptor가 담당:
    - provider key
    - source kind 지원 범위
    - 증분/백필 지원 여부
    - query 템플릿 규칙
    - provider instance 생성
  - service는 descriptor 목록만 순회하고 결과를 공통 upsert로 넘긴다.

### 3단계: provider 설정 외부화
- 목표: 새 provider 추가 시 코드 변경 범위를 adapter + config 등록 수준으로 줄인다.
- 현재 문제:
  - env 변수와 factory wiring이 provider별로 직접 박혀 있다.
  - custom provider를 완전 무코드로 조립하는 단계까지는 아직 안 갔다.
- 현재 상태:
  - factory는 `RAW_INGESTION_DESCRIPTOR_FACTORY_PATHS`로 extra descriptor factory를 읽을 수 있다.
  - 즉, factory 본문 수정 없이 custom descriptor를 settings 기반으로 service에 주입할 수 있다.
- 변경 방향:
  - `.env` 또는 settings에서 provider 목록을 JSON/TOML로 받는다.
  - provider별 인증/엔드포인트/쿼리 템플릿을 descriptor config로 이동한다.
  - CLI는 `sync-provider --provider CUSTOM_RSS` 같은 일반 명령을 우선 제공한다.

### 4단계: capability 기반 분리
- 목표: provider 이름이 아니라 capability로 동작을 고른다.
- 현재 문제:
  - `news`, `disclosure`, `trend`가 코드상 provider 이름과 느슨하게 섞여 있다.
- 변경 방향:
  - capability 예시:
    - `fetch_documents`
    - `fetch_trends`
    - `supports_company_targets`
    - `supports_theme_targets`
    - `supports_backfill`
  - coverage와 스케줄링도 capability 기준으로 묶는다.

### 5단계: 회사 마스터 도메인 분리 확장
- 목표: `company_master`의 `source_system = DART|KIS` 고정도 장기적으로 분리한다.
- 현재 문제:
  - 회사 식별자 매핑은 아직 두 소스 전용이다.
  - 공시 provider가 늘어나도 회사 매핑은 DART 전용 규칙에 크게 의존한다.
- 변경 방향:
  - `company_source_registry` 또는 `source_system_registry` 도입 검토
  - source system별 식별자 규칙, stock code 매핑 규칙, 신뢰도 정책을 분리
  - 단, 이 단계는 뉴스/공시 ingestion 유연화와 별도 작업으로 본다.

## 구현 우선순위
1. CLI를 일반 provider 실행 명령 중심으로 재구성
2. settings/env를 provider별 하드코딩에서 descriptor config 기반으로 이동
3. trend provider 복수 지원 정리
4. company master source system 일반화

## 지금 바로 새 provider를 붙일 때의 현실적인 규칙
- 뉴스/공시 provider는 먼저 adapter를 만든다.
- adapter 출력은 항상 `RawDocumentCandidate`로 맞춘다.
- `provider_registry`에 의미를 등록한다.
- 초기에는 existing service 분기에 최소 연결만 한다.
- provider 수가 2~3개 더 늘기 전까지는 orchestration 일반화 작업을 병행하지 않아도 된다.
- provider가 5개 이상으로 늘어날 시점에는 2단계와 3단계를 먼저 끝내고 추가 연동을 계속하는 편이 안전하다.
