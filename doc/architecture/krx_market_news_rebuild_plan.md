# KRX Market News Rebuild Plan

## 목적
- 현재 `raw_documents` 수집 축은 유지합니다.
- 뉴스/공시 가공 레이어는 국장 중심 표면에 맞게 다시 설계합니다.
- 초기 목표는 `개별 종목`이 아니라 `한국 증시 전체`에 중요한 뉴스와 공시를 안정적으로 추리는 것입니다.
- AI는 수집 자체가 아니라 `뉴스 중요도 판단`과 `현재 메인 표면 교체 판단`에 사용합니다.

## 현재 기준으로 유지할 것
- 단일 raw 테이블 유지
  - `raw_documents`
  - 뉴스/공시 구분은 `document_type` 칼럼 사용
  - 뉴스: `NEWS_CANDIDATE`
  - 공시: `DISCLOSURE`
- provider 축 유지
  - `DART`
  - `MK_RSS`
  - `NAVER_NEWS`
- 공통 기반 유지
  - `provider_registry`
  - `publisher_registry`
  - `raw_document_fetch_runs`
  - `companies`

## 현재 기준으로 교체할 것
- 기존 `events -> normalized_events -> event_evidence -> news_cards` 생성 로직은 그대로 확장하지 않습니다.
- 현재 규칙 중심의 뉴스 클러스터링, 중요도 계산, 카드 생성은 국장 메인 뉴스 선정 기준으로 다시 설계합니다.
- 핵심 문제는 다음과 같습니다.
  - 뉴스 의미 판단 부족
  - 서로 다른 사건이 같은 회사/시간대라는 이유로 잘못 묶일 수 있음
  - 새 뉴스와 현재 메인 뉴스 간 상대 비교가 약함
  - `trust_score`와 `market importance`가 분리되어도, 최종 표면 선별 구조는 아직 시장 편집 관점으로 충분히 정교하지 않음

## 제품 목표
- `/krx/news`는 기사 목록이 아니라 `국장 이벤트 카드` 중심으로 운영합니다.
- 메인 표면은 다음 세 축을 유지합니다.
  - `종합`
  - `한국 증시`
  - `글로벌 증시`
  - `공시`
- 초기 단계에서는 `한국 증시`와 `공시`에 집중합니다.
- 공시는 상위 GNB가 아니라 뉴스 내부 탭으로 유지합니다.

## 데이터 소스 역할

### DART
- raw 단계에서는 전체 공시를 계속 수집합니다.
- 시장 표면에는 `핵심 공시`만 올립니다.
- 국장 메인 표면에서 공시 영향 후보는 아래를 우선합니다.
  - 시가총액 상위 핵심 종목
  - 섹터 대표주
  - 시장 전체 파급이 큰 공시 유형
- 초기 후보군은 `top 10 + 섹터 대표주 포함 15~20개 내외`를 기준으로 둡니다.
- 공시는 `시장 표면용 핵심 후보`와 `전체 raw 보관`을 분리해서 생각합니다.

### MK_RSS
- 주요 경제지 evidence source입니다.
- 기사 메타데이터와 snippet을 `persistent evidence`로 취급합니다.
- 국장 메인 뉴스의 대표 근거 후보 역할을 맡습니다.

### NAVER_NEWS
- discovery source입니다.
- 탐색, 보강, 교차 확인용으로 사용합니다.
- 메인 표면의 사실 근거보다는 `새 이슈 탐지` 용도로 씁니다.

## 핵심 원칙

### 1. 중요도는 공신력이 아니라 시장 영향도다
- `trust_score`는 출처 신뢰도입니다.
- `importance`는 국장 메인 표면에 올릴 가치입니다.
- 같은 기사라도
  - 공신력은 낮아도 시장 영향이 크면 중요할 수 있고
  - 공신력은 높아도 시장 파급이 작으면 메인 표면에서 밀릴 수 있습니다.

### 2. 뉴스와 공시는 raw에서는 같이 저장하고, 판단 로직은 분리한다
- `raw_documents`는 유지합니다.
- 그러나 가공 시점에서는
  - `뉴스 중요도 판단`
  - `공시 중요도 판단`
  를 별도로 봅니다.
- 공시는 규칙 기반 선별 비중이 높고, 뉴스는 AI 기반 판단 비중이 높습니다.

### 3. AI는 사용자별로 호출하지 않는다
- AI는 `이벤트/뉴스 자체의 성격`을 판단합니다.
- 나중에 관심종목 기능이 생겨도, 사용자별 노출은 저장된 메타데이터로 필터링합니다.
- 즉 AI는 `한 번 해석`, 사용자별 표시는 `여러 번 재사용`이 원칙입니다.

## 목표 파이프라인

```text
raw ingestion
-> news batch AI triage
-> disclosure market filter
-> market candidate pool
-> current surface comparison
-> market surface state
-> API read models
```

## 단계별 설계

### 1. raw ingestion
- 기존 수집 축을 그대로 사용합니다.
- 입력 소스:
  - `DART`
  - `MK_RSS`
  - `NAVER_NEWS`
- 저장 위치:
  - `raw_documents`
- 저장 시 필수 구분:
  - `provider`
  - `document_type`
  - `published_at`
  - `observed_at`
  - `company_id` 또는 `company_ref`

### 2. news batch AI triage
- 새로 들어온 뉴스를 `1건씩 AI 호출`하지 않습니다.
- 짧은 배치 단위로 묶어서 한 번에 보냅니다.
- 예:
  - `1분 동안 들어온 뉴스 5~15건`
  - `AI 1회 호출`
  - 결과는 문서별로 각각 반환

#### 배치 AI가 판단할 것
- `market_scope`
  - `kr_market`
  - `global_market`
  - `sector`
  - `company`
  - `ignore`
- `market_importance_prelim`
  - `high`
  - `medium`
  - `low`
- `impact_direction`
  - `positive`
  - `negative`
  - `mixed`
  - `neutral`
- `reason_short`
- `affected_companies`
- `related_sectors`

#### 배치 AI가 하지 않을 것
- 최종 카드 순위 확정
- 사용자별 관심종목 반영
- 공시 전체 재해석

### 3. disclosure market filter
- DART는 전체 raw를 저장합니다.
- 하지만 시장 표면에는 핵심 공시만 올립니다.
- 1차 필터는 규칙 기반으로 둡니다.

#### 시장 표면용 핵심 공시 조건
- 회사 조건
  - top 10 핵심주
  - 섹터 대표주
- 공시 조건
  - 실적/가이던스
  - 유상증자/감자
  - CB/BW/EB
  - 자사주 취득/소각
  - 최대주주/지배구조 변화
  - 대형 수주/계약
  - 영업정지/회생/소송/횡령배임

### 4. market candidate pool
- 시장 표면 후보군은 다음 두 축에서 만듭니다.
  - 뉴스 AI triage 결과 중 `kr_market`, `global_market`, `sector`
  - 핵심 공시 필터를 통과한 DART 공시
- 이 단계의 목적은 “메인 표면에 올라갈 수 있는 후보 목록”을 만들기입니다.

### 5. current surface comparison
- 이 레이어가 이번 재설계의 핵심입니다.
- 새 뉴스만 보는 것이 아니라, `현재 메인 표면에 있는 카드`와 비교합니다.
- 판단 질문:
  - 새 후보가 현재 메인 카드보다 더 중요한가
  - 기존 카드를 유지해야 하는가
  - 같은 흐름의 후속 업데이트인가
  - 공시 탭에만 남기고 메인에서는 제외해야 하는가

#### 입력
- 현재 메인 표면 상태
- 이번 배치 신규 후보
- 핵심 공시 후보

#### 출력
- `keep`
- `promote`
- `replace`
- `demote`
- `disclosure_only`

### 6. market surface state
- 현재 상단 카드 상태를 DB에 저장합니다.
- 이 상태는 다음 배치 비교에 재사용합니다.
- 장 종료 후 일일 단위로 archive/reset할 수 있어야 합니다.

## AI 사용 원칙

### 1차 AI: 뉴스 triage
- 대상: 새로 들어온 뉴스 배치
- 목적: 국장 relevance와 초기 중요도 판단
- 모델: `Gemini 2.5 Flash-Lite` 우선

### 2차 AI: 표면 비교/편집
- 대상: 현재 상단 상태 + 신규 후보
- 목적: 유지/교체/상향/하향 결정
- 이 단계는 호출 빈도를 줄이기 위해
  - 장중 배치
  - top 후보만
  - 작은 컨텍스트
  로 운영합니다.

### AI를 쓰지 않는 부분
- raw 수집
- provider/fetch run 기록
- DART 1차 핵심 공시 필터
- 사용자별 관심종목 필터링

## 권장 저장 구조

### 기존 유지
- `raw_documents`
- `raw_document_fetch_runs`
- `companies`

### 신규 또는 대체 대상
- `news_batch_triage`
  - 새 뉴스 1차 AI 판단 결과
- `market_surface_candidates`
  - 메인 표면 후보군
- `market_surface_state`
  - 현재 메인에 걸린 카드 상태
- `market_surface_history`
  - 장중 교체 이력

## 시장 표면과 공시 표면의 관계
- 시장 메인 표면은 `뉴스 + 시장영향 공시 일부`만 보여줍니다.
- 공시 탭은 시장 표면보다 넓은 범위를 보여줍니다.
- 모든 공시가 메인 시장 뉴스가 될 필요는 없습니다.
- 공시는 별도 탭이 이미 있으므로, 메인 표면에서는 `핵심 공시 strip` 수준으로 시작합니다.

## 미래 확장: 관심종목
- 초기에는 국장 전체만 봅니다.
- 나중에 관심종목 탭이 생기면, AI를 다시 호출하지 않습니다.
- 이미 저장된 메타데이터를 재사용합니다.
  - `affected_companies`
  - `market_scope`
  - `company_relevance`
  - `disclosure_priority`

## 구현 순서

### Phase 1
- raw 수집 유지
- 기존 뉴스 가공 레이어를 더 키우지 않음
- `news batch triage` 도입
- `DART market filter` 고정

### Phase 2
- `market_surface_state` 도입
- 현재 표면 vs 신규 후보 비교 레이어 추가
- 종합/한국 증시/공시 표면을 새 상태 테이블 기준으로 교체

### Phase 3
- 글로벌 증시 확장
- 관심종목 표면 확장
- 필요 시 AI 프롬프트/평가 체계 고도화

## 지금 시점의 결론
- raw 적재 구조는 유지합니다.
- 현재 문제는 수집이 아니라 `가공/선정/비교`입니다.
- 따라서 재설계의 중심은
  - `뉴스 배치 AI triage`
  - `공시 시장 필터`
  - `현재 메인 표면 상태 비교`
  입니다.
- 이 설계는 국장 중심 MVP를 먼저 만들고, 이후 관심종목 확장으로 자연스럽게 이어질 수 있습니다.
