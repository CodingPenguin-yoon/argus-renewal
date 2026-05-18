# Provider와 수집 파이프라인

## 역할

provider는 외부 데이터 source를 Argus 내부 record로 바꾸는 계층입니다.

외부 API 응답은 화면이나 판단 엔진에 직접 들어가지 않습니다.

```text
외부 API / 파일 / mock
-> provider
-> 내부 record
-> storage
-> dashboard builder
-> API
-> frontend
```

## 주요 파일

```text
backend/src/argus_v2/cli.py
backend/src/argus_v2/providers/models.py
backend/src/argus_v2/providers/kis_auth.py
backend/src/argus_v2/providers/kis_derivatives.py
backend/src/argus_v2/providers/kis_option_chain.py
backend/src/argus_v2/providers/kis_market_reaction.py
backend/src/argus_v2/providers/context_inputs.py
backend/src/argus_v2/providers/mock_dashboard.py
backend/src/argus_v2/storage.py
```

## 내부 record 모델

파일:

```text
backend/src/argus_v2/providers/models.py
```

대표 record:

- `MarketIntradaySnapshotRecord`
- `DerivativesOptionChainSnapshotRecord`
- `DerivativesOptionChainLevelRecord`
- `MarketReactionSnapshotRecord`
- `MarketReactionSectorRecord`
- `NewsTriggerRecord`
- `BriefingProviderBatch`

provider는 최종적으로 이 record들을 반환합니다.

## CLI 수집 입구

주요 CLI:

```bash
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context
python3 -m src.argus_v2.cli smoke-news-ai
```

역할:

- `smoke-kis`: KIS token, 국내파생, 옵션체인 연결 확인
- `collect-context`: 현물 반응과 뉴스/매크로 context 수집
- `smoke-news-ai`: Gemini/OpenAI-compatible 뉴스 판단 연결 확인

## KIS 인증 provider

파일:

```text
backend/src/argus_v2/providers/kis_auth.py
```

역할:

- `KIS_APP_KEY`, `KIS_APP_SECRET`으로 access token 발급
- token을 env에 저장하지 않음
- local cache 파일에 저장

기본 cache:

```text
data/kis_token_cache.json
```

보안 원칙:

- access token은 raw sample에 남기지 않습니다.
- app key/secret은 저장 sample에서 redaction합니다.

## KIS 국내파생 provider

파일:

```text
backend/src/argus_v2/providers/kis_derivatives.py
backend/src/argus_v2/providers/kis_live.py
```

역할:

- KOSPI200 선물 기본 시세 수집
- price/change_rate/open_interest 등 normalize
- basis, market basis, open interest change rate 같은 additional metrics 구성
- `MarketIntradaySnapshotRecord` 반환

주의:

KOSPI200 시장 전체 외국인/기관/개인 선물 수급 endpoint는 아직 공식 확인 전입니다. 계좌 기반 잔고 API를 시장 전체 수급처럼 쓰지 않습니다.

## KIS 옵션체인 provider

파일:

```text
backend/src/argus_v2/providers/kis_option_chain.py
```

역할:

- 옵션 전광판/옵션 리스트 기반으로 KOSPI200 옵션체인 수집
- 행사가별 call/put 가격, 거래량, 미결제약정 normalize
- ATM, expiry, contract month 정리
- `DerivativesOptionChainSnapshotRecord` 반환

dashboard builder는 최신 옵션체인과 직전 옵션체인을 비교해 OI 변화 방향을 계산합니다.

## KIS 현물 반응 provider

파일:

```text
backend/src/argus_v2/providers/kis_market_reaction.py
backend/src/argus_v2/providers/context_inputs.py
```

역할:

- KOSPI/KOSDAQ 지수 반응
- 상승/하락 종목 수
- 업종 강약
- 외국인/기관/개인 현물 수급

현물 수급 필드:

- `spot_foreign_net_buy`
- `spot_institution_net_buy`
- `spot_individual_net_buy`

이 값은 선물 수급 필드에 대입하지 않습니다.

## Context provider

파일:

```text
backend/src/argus_v2/providers/context_inputs.py
```

이 파일은 현물 반응, 뉴스 trigger, 원천 뉴스 feed, AI enrichment를 담당합니다.

주요 class:

- `ArgusMarketReactionService`
- `ArgusNewsTriggerService`

## 뉴스 trigger 수집

뉴스 trigger 수집은 시장 판단용입니다.

지원 provider:

- `mock`
- `file`
- `rss`
- `naver`
- `dart`
- `macro`
- `hybrid`

흐름:

```text
fetch_triggers()
-> _fetch_raw_records()
-> _ai_candidate_records()
-> _with_ai_enrichment()
-> _deduplicate_triggers()
-> should_use=true만 선택
-> relevance/confidence 기준 정렬
-> limit 적용
-> BriefingProviderBatch 반환
```

중요 정책:

- live news는 키워드로 호재/악재 분류하지 않습니다.
- AI JSON이 `should_use=true`라고 판단한 항목만 trigger로 저장합니다.
- AI가 꺼져 있거나 실패하면 실뉴스 trigger는 저장하지 않습니다.
- mock/file의 명시적 AI enrichment는 테스트와 seed 용도로 사용할 수 있습니다.

## 원천 뉴스 feed 수집

원천 뉴스 feed는 `뉴스 분석 > 뉴스` 화면용입니다.

흐름:

```text
fetch_feed()
-> _fetch_raw_records()
-> _feed_batch()
-> dedupe
-> published_at 기준 정렬
-> limit 적용
-> NewsFeedResponse 변환
```

중요 차이:

- AI enrichment를 하지 않습니다.
- `impact`, `connection_strength`, `ai_reason`을 만들지 않습니다.
- 최신 경제 뉴스 목록을 넓게 보여주는 입력면입니다.

## RSS provider

기본 RSS:

```text
https://www.mk.co.kr/rss/30100041/
https://www.mk.co.kr/rss/50200011/
```

역할:

- RSS XML 요청
- `<item>` 파싱
- title/link/description/pubDate 추출
- `NewsTriggerRecord`로 normalize

원천 뉴스 feed의 기본 provider는 `rss`입니다. API key 없이 동작해야 하기 때문입니다.

## Naver provider

환경 변수:

```text
ARGUS_NEWS_NAVER_CLIENT_ID
ARGUS_NEWS_NAVER_CLIENT_SECRET
ARGUS_NEWS_NAVER_BASE_URL
ARGUS_NEWS_NAVER_SEARCH_PATH
ARGUS_NEWS_NAVER_DISPLAY
ARGUS_NEWS_NAVER_PAGE_LIMIT
```

역할:

- Naver news search API 호출
- HTML tag 제거
- originallink/link 정리
- 최신순 page 수집

## DART provider

환경 변수:

```text
ARGUS_DISCLOSURE_DART_API_KEY
ARGUS_DISCLOSURE_DART_BASE_URL
ARGUS_DISCLOSURE_DART_LIST_PATH
ARGUS_DISCLOSURE_DART_CORP_CLS
ARGUS_DISCLOSURE_DART_PBLNTF_TY
```

역할:

- DART 공시 목록 조회
- 회사명 + 공시명으로 title 구성
- DART viewer URL 구성
- 공시를 뉴스 trigger 후보로 normalize

## Macro provider

지원 provider:

- `mock`
- `file`

역할:

- 뉴스가 아닌 금리/환율/미국 지수/원자재 이벤트를 같은 trigger 구조로 태움
- `macro` provider 단독 또는 `hybrid` 안에서 사용 가능

## Hybrid provider

`hybrid`는 여러 source를 합칩니다.

포함 가능:

- RSS
- Naver
- DART
- macro

source별 credential이 없으면 해당 source는 건너뛰고 가능한 source만 사용합니다.

## Provider health

provider 실행 결과는 `argus_v2_provider_runs`에 저장되고 dashboard API의 `provider_health`로 노출됩니다.

화면은 provider별 상태를 표시합니다.

예:

- KIS 국내파생
- KIS 옵션체인
- v2 현물 반응
- v2 뉴스 트리거

## 새 provider 추가 절차

1. 외부 응답 sample을 확보합니다.
2. 내부 record로 normalize할 dataclass를 정합니다.
3. raw_payload를 record에 보존합니다.
4. `BriefingProviderBatch`로 반환합니다.
5. `ArgusV2Storage.save_provider_batch()`가 저장 가능한지 확인합니다.
6. provider run metadata에 input_count, filtered_count, error 정보를 남깁니다.
7. dashboard 계약에 노출할지 결정합니다.
8. 테스트를 추가합니다.

## 장애를 볼 때 순서

뉴스가 안 보이면:

```text
provider run status
-> provider sample 존재 여부
-> AI candidate/enriched/selected count
-> news trigger table 저장 여부
-> dashboard API triggers
-> frontend 화면
```

원천 뉴스 feed가 안 보이면:

```text
/api/argus/v2/news-feed 응답
-> provider 설정
-> RSS/Naver/DART credential
-> lookback_hours
-> feed limit
-> frontend /argus/triggers/news
```
