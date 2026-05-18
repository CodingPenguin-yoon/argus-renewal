# 뉴스 분석 아키텍처

## 목적

뉴스 분석은 두 가지 요구를 동시에 만족해야 합니다.

1. 시장 판단에 정말 영향을 주는 뉴스/매크로 trigger만 좁게 보여준다.
2. 실시간 원천 경제 뉴스는 넓게 모아서 별도 화면에서 확인할 수 있게 한다.

그래서 `뉴스 분석` 안에 `메인`과 `뉴스`를 분리했습니다.

```text
뉴스 분석
  - 메인: 시장 판단용 trigger
  - 뉴스: 원천 뉴스 feed
```

## 왜 분리했나

뉴스를 모두 시장 판단에 넣으면 문제가 생깁니다.

- 기사량이 많아져 핵심 판단이 흐려짐
- 단순 헤드라인을 시장 원인처럼 오해할 수 있음
- AI 비용과 latency가 커짐
- rate limit에 걸릴 가능성이 커짐
- dashboard가 뉴스 앱처럼 변함

반대로 원천 뉴스를 아예 안 보여주면 문제가 생깁니다.

- AI가 무엇을 후보로 봤는지 확인하기 어려움
- 실시간 경제 뉴스 흐름을 따로 볼 수 없음
- 나중에 필터/분류/요약 기능을 붙일 기반이 약함

그래서 구조를 분리했습니다.

## 화면 구조

```text
/argus/triggers
-> 뉴스 분석 > 메인
-> AI 판단을 거친 trigger 표시

/argus/triggers/news
-> 뉴스 분석 > 뉴스
-> 원천 뉴스 feed 표시
```

## API 구조

```text
/api/argus/v2/dashboard
-> MarketDashboard.triggers
-> TriggerEvent[]

/api/argus/v2/news-feed
-> NewsFeedResponse.items
-> NewsFeedItem[]
```

## 시장 판단용 trigger 흐름

```text
RSS/Naver/DART/macro/hybrid
-> NewsTriggerRecord raw candidates
-> query/time 기반 후보 제한
-> AI enrichment
-> should_use=true만 선택
-> relevance/confidence 정렬
-> argus_v2_news_triggers 저장
-> dashboard builder
-> TriggerEvent
-> /api/argus/v2/dashboard
-> /argus/triggers
```

TriggerEvent에는 AI 판단 정보가 있습니다.

- impact
- connection_strength
- ai_reason
- ai_confidence
- affected_factors

## 원천 뉴스 feed 흐름

```text
RSS/Naver/DART/macro/hybrid
-> NewsTriggerRecord raw candidates
-> dedupe
-> published_at 정렬
-> limit 적용
-> NewsFeedItem
-> /api/argus/v2/news-feed
-> /argus/triggers/news
```

NewsFeedItem에는 AI 판단 정보가 없습니다.

- title
- summary
- source
- published_at
- source_url
- freshness

## AI enrichment 정책

AI는 시장 판단용 trigger 선별에만 사용합니다.

AI 요청 schema:

- `should_use`
- `impact`
- `relevance_score`
- `connection_strength`
- `affected_factors`
- `summary`
- `reason`
- `confidence`

AI가 꺼져 있거나 실패하면:

- 시장 판단용 실뉴스 trigger는 표시하지 않습니다.
- 원천 뉴스 feed는 계속 표시할 수 있습니다.

이 정책은 “AI 없이는 임의로 호재/악재 분류하지 않는다”는 원칙과 “원천 뉴스는 실시간으로 보여준다”는 요구를 동시에 만족합니다.

## 후보 제한

RSS 후보 전체를 AI로 보내지 않습니다.

현재 방식:

- 최신순 정렬
- query term이 있으면 matching 후보 우선
- limit의 2~3배 정도만 AI 후보로 사용
- 최대 후보 수를 제한

이유:

- 비용 제어
- latency 제어
- Gemini/OpenAI-compatible rate limit 회피
- 낮은 품질 기사 제거

## Dedupe

뉴스 후보는 제목/source/published_at/source_url 기반으로 중복 제거합니다.

현재 dedupe는 1차 수준입니다. 향후에는 아래가 필요합니다.

- 같은 기사 syndication 제거
- 같은 이벤트의 여러 기사 묶기
- source priority 적용
- 제목 유사도 기반 clustering

## Source 정책

현재 지원 source:

- RSS
- Naver
- DART
- macro
- mock
- file
- hybrid

기본 원천 뉴스 feed:

```text
ARGUS_NEWS_FEED_PROVIDER=rss
```

RSS는 API key 없이 동작하므로 local MVP 기본값에 적합합니다.

## 환경 변수

시장 판단용 trigger:

```text
ARGUS_NEWS_TRIGGERS_PROVIDER
ARGUS_NEWS_TRIGGERS_RSS_URLS
ARGUS_NEWS_TRIGGERS_QUERY
ARGUS_NEWS_TRIGGERS_LIMIT
ARGUS_NEWS_TRIGGERS_LOOKBACK_HOURS
ARGUS_NEWS_AI_PROVIDER
ARGUS_NEWS_AI_MODEL
ARGUS_NEWS_AI_API_KEY
ARGUS_GEMINI_MODEL
ARGUS_GEMINI_API_KEY
```

원천 뉴스 feed:

```text
ARGUS_NEWS_FEED_PROVIDER
ARGUS_NEWS_FEED_RSS_URLS
ARGUS_NEWS_FEED_QUERY
ARGUS_NEWS_FEED_LIMIT
ARGUS_NEWS_FEED_LOOKBACK_HOURS
```

Naver:

```text
ARGUS_NEWS_NAVER_CLIENT_ID
ARGUS_NEWS_NAVER_CLIENT_SECRET
```

DART:

```text
ARGUS_DISCLOSURE_DART_API_KEY
```

## 화면 표시

### 메인

표시 내용:

- trigger title
- impact
- connection strength
- summary
- AI reason
- affected factors
- source
- AI confidence
- published_at

목적:

- 왜 시장 판단에 영향을 주는지 확인
- 파생/옵션 결론을 강화/상쇄하는지 확인

### 뉴스

표시 내용:

- title
- summary
- published_at
- source
- freshness
- 원문 링크

목적:

- 경제 뉴스 흐름 확인
- 이후 필터/분류/요약/trigger 연결 기능의 기반

## 앞으로 필요한 기능

원천 뉴스 feed:

- source별 필터
- 키워드 검색
- 중요도 표시
- 이미 trigger로 연결된 기사 표시
- 유사 기사 묶기
- 시간대별 그룹
- provider별 수신 상태 표시

AI trigger:

- connection_strength를 판단 엔진 점수에 더 정교하게 반영
- AI confidence별 UI 차등 표시
- rate limit 시 fallback 문구 개선
- prompt/schema 운영 보정

## 주의할 점

원천 뉴스 feed가 추가됐다고 해서 Argus의 중심이 뉴스 feed가 된 것은 아닙니다.

제품의 중심은 여전히:

```text
파생/옵션 포지셔닝
-> 뉴스/매크로 trigger
-> 현물 반응
-> 시장 판단
```

원천 뉴스 feed는 이 판단 체계를 보조하고 확장하기 위한 기반입니다.
