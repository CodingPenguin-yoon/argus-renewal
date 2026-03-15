# Backend Materialization

현재 코드 기준으로 뉴스 리빌드의 핵심 가공 레이어를 자세히 설명하는 문서입니다.

## 이 문서의 범위
- `backend/src/krx/news/factory.py`
- `backend/src/krx/news/batch_triage_ai.py`
- `backend/src/krx/news/editorial_ai.py`
- `backend/src/krx/news/service.py`
- 관련 env와 저장 테이블

## 이 레이어가 하는 일
- raw 문서를 바로 화면에 보내지 않습니다.
- 먼저 "시장 표면 후보"로 해석하고,
- 그중 현재 대표 카드를 골라
- 프런트가 바로 읽을 수 있는 read model로 저장합니다.

## 1. `factory.py`

### 역할
- `NewsProductService`를 만들 때 필요한 의존성을 묶습니다.
- datalab provider, batch triage provider, compare AI provider를 settings 기반으로 조립합니다.

### 왜 factory가 필요한가
- 서비스 본체는 "뉴스를 어떻게 계산할지"만 알아야 합니다.
- API key, base URL, enabled 여부 같은 wiring은 factory에 두는 편이 깔끔합니다.

### 주입 대상
- `NaverDatalabTrendProvider`
- `OpenAICompatibleNewsBatchTriageProvider` 또는 disabled provider
- `OpenAICompatibleNewsEditorialAIProvider` 또는 disabled provider

## 2. 1차 AI: `batch_triage_ai.py`

### 역할
- 짧은 뉴스 묶음을 한 번에 AI로 보내 triage 결과를 받습니다.

### 핵심 데이터 클래스
- `NewsBatchTriageRequestItem`
  - 문서 한 건을 AI에 보낼 때 필요한 최소 입력
- `NewsBatchTriageResponseItem`
  - 문서별 triage 결과

### 핵심 provider 인터페이스
- `NewsBatchTriageProvider`
- 구현:
  - `DisabledNewsBatchTriageProvider`
  - `OpenAICompatibleNewsBatchTriageProvider`

### 이 파일이 내리는 판단
- `market_scope`
- `primary_region`
- `importance_label`
- `impact_direction`
- `reason_short`
- `confidence`

### 중요한 점
- "문서마다 개별 호출"이 아니라 "배치 1회 호출"이 목표입니다.
- 실패해도 전체 파이프라인이 죽지 않도록 deterministic fallback을 전제로 둡니다.

## 3. 2차 AI: `editorial_ai.py`

### 역할
- 현재 표면과 top 후보를 비교해 "대표 카드를 유지할지, 설명을 갱신할지"를 보정합니다.

### 핵심 데이터 클래스
- `NewsEditorialAICurrentSurface`
  - 현재 각 표면의 대표 카드 요약
- `NewsEditorialAIRequest`
  - 후보 카드 한 건의 비교 입력
- `NewsEditorialAICompareRequest`
  - 현재 표면 묶음 + 후보 묶음
- `NewsEditorialAIResponse`
  - 비교 결과

### provider 구조
- `NewsEditorialAIProvider`
- 구현:
  - `DisabledNewsEditorialAIProvider`
  - `OpenAICompatibleNewsEditorialAIProvider`

### 이 파일이 반환하는 값
- `story_state`
- `importance_label`
- `editorial_reason`
- `editorial_boost`
- `confidence`

### 중요한 점
- 지금 구조는 카드별 fan-out이 아니라 compare pass 1회입니다.
- `editorial_boost`는 음수도 허용되므로, 기존 카드보다 덜 중요한 후보를 일부러 낮출 수 있습니다.

## 4. 본체: `service.py`

### 역할
- 뉴스 리빌드의 핵심 서비스입니다.
- raw 문서, triage, attention score, compare 결과를 종합해
- `news_batch_triage`와 `market_surface_*`를 관리합니다.

### 핵심 클래스
- `NewsProductService`

### 이 서비스가 직접 하는 일
- recent raw documents 읽기
- 기존 triage row 읽기
- 누락 row나 legacy row를 triage로 업그레이드
- cluster 생성
- score 계산
- compare AI 적용
- candidate/state/history 저장
- API에서 바로 쓰는 read model 반환

## 5. materialization 흐름

### refresh 시작
- `refresh_materialized(force=...)`
- TTL과 source freshness를 보고 refresh가 필요한지 판단합니다.

### recent triage 확보
- `_resolve_recent_triage_rows(...)`
- 최근 raw document id를 기준으로 기존 `news_batch_triage`를 읽습니다.
- 누락 row는 새로 만듭니다.
- legacy provenance가 없는 row는 batch triage가 켜져 있으면 업그레이드 대상이 됩니다.

### triage row 생성
- `_build_triage_rows(...)`
- 먼저 deterministic triage를 만듭니다.
- batch triage가 켜져 있으면 request batch를 만들어 AI 호출을 시도합니다.
- 성공한 row는 `llm_batch`
- 실패한 row는 `llm_batch_fallback` 또는 deterministic 성격으로 남습니다.

### cluster 생성
- `_build_clusters(...)`
- triage row를 기준으로 문서를 cluster 단위로 묶습니다.
- duplicate 문서는 primary cluster key를 재사용합니다.

### attention score
- datalab score를 읽어 `attention_score`에 반영합니다.

### compare AI
- `_resolve_editorial_ai_enrichments(...)`
- 현재 state를 읽어 current surfaces를 만들고
- 상위 candidate만 compare request로 묶어 한 번에 AI를 부릅니다.

### candidate/state/history 저장
- `_replace_materialized(...)`
- `market_surface_candidates`를 재작성합니다.
- 각 표면의 lead를 골라 `market_surface_state`를 씁니다.
- state가 바뀌면 `market_surface_history`에 snapshot을 남깁니다.

## 6. state와 history가 왜 중요한가

### `market_surface_state`
- 지금 화면의 대표 카드 상태를 저장합니다.
- 단순히 candidate key만 두지 않고 `state_json`에도 요약을 남깁니다.
- 현재는 이런 정보가 들어갑니다.
  - lead card id
  - lead candidate key
  - lead title
  - published_at
  - ranking_score
  - story_state
  - importance_label
  - editorial_reason
  - ai_confidence
  - ai_provider
  - ai_model

### `market_surface_history`
- 이전에는 대표 카드가 바뀔 때만 의미가 컸습니다.
- 지금은 같은 대표 카드가 유지돼도 explanation/provenance가 바뀌면 `metadata_update`를 남깁니다.
- 운영 관점에서는 "왜 화면 설명이 바뀌었는지" 확인하는 데 도움이 됩니다.

## 7. 주요 읽기 메서드
- `get_dashboard()`
  - `/api/news/dashboard`에서 쓰는 종합 payload
- `list_cards(region=...)`
  - KR/GLOBAL 카드 리스트
- `list_disclosure_cards(...)`
  - 공시 카드
- `get_header_context()`
  - 헤더용 요약 정보
- `get_coverage()`
  - source coverage 정보
- `list_feed_items(...)`
  - feed 계열 API에서 쓰는 read model

## 8. 관련 env
- `NEWS_PRODUCT_LOOKBACK_DAYS`
- `NEWS_PRODUCT_CARD_LIMIT`
- `NEWS_PRODUCT_REPRESENTATIVE_EVIDENCE_LIMIT`
- `NEWS_PRODUCT_REFRESH_TTL_SECONDS`
- `NEWS_PRODUCT_DATALAB_WINDOW_DAYS`
- `NEWS_PRODUCT_BATCH_TRIAGE_*`
- `NEWS_PRODUCT_EDITORIAL_AI_*`

## 9. 공부할 때 특히 봐야 할 포인트
- `news_batch_triage`가 현재 source-of-truth라는 점
- compare AI가 per-card가 아니라 한 번의 compare request라는 점
- state/history가 화면 디버깅에 중요한 운영 힌트라는 점
- event pipeline과 news surface pipeline이 같은 뉴스 서비스가 아니라는 점

## 자주 생기는 오해
- `service.py`가 raw ingestion까지 하는 것은 아닙니다.
- batch triage가 켜져 있어도 모든 문서를 무조건 AI로 다시 보내는 구조는 아닙니다.
- compare AI는 카드 생성 자체보다 "최종 표면 편집"에 더 가깝습니다.

## 먼저 같이 볼 테스트
- `backend/tests/test_market_news_product.py`

## 다음 문서
- `04_backend_api_layers.md`
- `07_file_by_file_reference.md`
