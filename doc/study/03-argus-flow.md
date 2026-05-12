# 03. Argus 실제 흐름

## 1. 화면을 열 때 흐름

사용자가 `/argus`를 열면 흐름은 이렇습니다.

```text
브라우저
-> frontend /argus page
-> backend /api/argus/v2/dashboard
-> SQLite DB 조회
-> dashboard builder
-> judgement engine
-> JSON 응답
-> 화면 표시
```

중요한 점은 화면을 열 때 외부 API를 직접 호출하지 않는다는 것입니다. 화면은 backend dashboard API만 봅니다.

## 2. `/argus` 화면 파일

frontend route는 여기입니다.

```text
frontend/src/app/argus/page.tsx
```

이 파일은 직접 외부 API를 부르지 않습니다. backend dashboard 데이터를 가져와 화면 컴포넌트에 넘깁니다.

관련 파일은 이렇습니다.

```text
frontend/src/argus_v2/server/dashboard.ts
frontend/src/argus_v2/components/dashboard.tsx
frontend/src/argus_v2/contracts/dashboard.ts
```

`server/dashboard.ts`는 backend API 호출 담당입니다.

`components/dashboard.tsx`는 화면 표시 담당입니다.

`contracts/dashboard.ts`는 frontend가 기대하는 데이터 모양 검사 담당입니다.

## 3. dashboard API 흐름

backend API 입구는 여기입니다.

```text
backend/src/argus_v2/api/router.py
```

흐름은 단순합니다.

```text
GET /api/argus/v2/dashboard
-> DB 연결
-> build_dashboard_from_storage()
-> 결과가 있으면 반환
-> DB가 비어 있으면 mock fallback 반환
```

mock fallback은 개발용 안전장치입니다. DB가 완전히 비어 있어도 화면이 깨지지 않게 해줍니다.

## 4. dashboard builder 흐름

dashboard builder 위치는 여기입니다.

```text
backend/src/argus_v2/dashboard.py
```

하는 일은 이렇습니다.

```text
1. 최신 파생 snapshot 읽기
2. 최신 옵션체인 snapshot 읽기
3. 최신 현물 반응 snapshot 읽기
4. 최신 뉴스 트리거 읽기
5. provider health 만들기
6. judgement engine 호출하기
7. MarketDashboard로 묶기
```

이 파일은 외부 API를 호출하지 않습니다. 이미 DB에 저장된 데이터를 읽어서 화면용으로 조립합니다.

## 5. 판단 엔진 흐름

판단 엔진 위치는 여기입니다.

```text
backend/src/argus_v2/judgement/engine.py
```

판단 엔진은 데이터를 점수화해서 라벨을 만듭니다.

예를 들어:

```text
옵션 PUT 우위 -> 하방 점수
KOSPI200 선물 하락 -> 하방 점수
부정 뉴스 트리거 -> 하방 점수
반도체 강세 -> 반대 증거
```

이런 식으로 합쳐서 `하방 우위` 같은 결론을 만듭니다.

주의할 점은 판단 엔진이 “매수/매도 추천”을 만들지 않는다는 것입니다. Argus는 시장 상태를 읽는 도구입니다.

## 6. 데이터 수집 흐름

데이터 수집은 API가 아니라 CLI가 담당합니다.

```bash
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context
```

CLI 위치는 여기입니다.

```text
backend/src/argus_v2/cli.py
```

## 7. KIS smoke 흐름

`smoke-kis`는 KIS 선물/옵션 데이터를 가져옵니다.

```text
CLI smoke-kis
-> KIS token 발급 또는 cache 사용
-> KIS 국내파생 provider
-> KIS 옵션체인 provider
-> raw sample redaction
-> SQLite 저장
```

관련 파일은 이렇습니다.

```text
backend/src/argus_v2/providers/kis_auth.py
backend/src/argus_v2/providers/kis_live.py
backend/src/argus_v2/providers/kis_derivatives.py
backend/src/argus_v2/providers/kis_option_chain.py
```

`kis_auth.py`는 token 담당입니다.

`kis_derivatives.py`는 국내파생 선물 snapshot 담당입니다.

`kis_option_chain.py`는 옵션체인 담당입니다.

`kis_live.py`는 위 provider들을 한 번에 실행하고 storage에 저장하는 조율 담당입니다.

## 8. collect-context 흐름

`collect-context`는 현물 반응과 뉴스 트리거를 가져옵니다.

```text
CLI collect-context
-> 현물 반응 provider
-> 뉴스 트리거 provider
-> raw sample redaction
-> SQLite 저장
```

관련 파일은 여기입니다.

```text
backend/src/argus_v2/providers/context_inputs.py
```

현재 뉴스 트리거 provider는 아래 방식을 지원합니다.

```text
mock
file
rss
naver
dart
hybrid
```

`hybrid`는 가능한 source를 섞습니다. RSS, Naver, DART를 같이 쓰는 모드입니다.

## 9. provider가 반환하는 record

provider는 외부 API 응답을 그대로 넘기지 않습니다. Argus가 이해하는 record로 바꿔서 넘깁니다.

예를 들어 Naver 뉴스 API 응답에는 이런 필드가 있습니다.

```text
title
originallink
link
description
pubDate
```

Argus는 이것을 `NewsTriggerRecord`로 바꿉니다.

```text
id
title
summary
impact
source
published_at
connection_strength
freshness
source_url
raw_payload
```

이 변환 덕분에 dashboard builder와 judgement engine은 Naver인지 DART인지 몰라도 됩니다.

## 10. storage가 저장하는 것

storage 위치는 여기입니다.

```text
backend/src/argus_v2/storage.py
```

storage는 provider 실행 결과를 여러 테이블에 저장합니다.

대표 테이블:

```text
argus_v2_provider_runs
argus_v2_provider_samples
argus_v2_derivatives_snapshots
argus_v2_option_chain_snapshots
argus_v2_option_chain_levels
argus_v2_market_reaction_snapshots
argus_v2_market_reaction_sectors
argus_v2_news_triggers
```

## 11. provider run이 왜 중요한가

provider run은 “언제 어떤 provider를 실행했고 결과가 어땠는지”를 남깁니다.

예를 들어:

```text
v2_news_triggers
status: success
observed_count: 8
```

또는:

```text
v2_news_triggers
status: skipped
missing_fields: missing_naver_credentials
```

이 기록이 있으면 데이터가 없는 이유를 알 수 있습니다.

## 12. raw sample이 왜 중요한가

외부 API는 문서와 실제 응답이 다를 수 있습니다. 특히 금융 API는 필드명이 복잡하거나 바뀔 수 있습니다.

raw sample을 저장하면 나중에 이런 질문에 답할 수 있습니다.

```text
KIS가 실제로 어떤 필드명을 줬지?
Naver 뉴스에 링크가 originallink로 왔나 link로 왔나?
DART 공시 날짜가 어떤 형식이지?
```

단, token이나 secret은 저장하지 않습니다.

## 13. dashboard API가 DB만 읽는 이유

dashboard API가 매번 외부 API를 직접 호출하면 이런 문제가 생깁니다.

- 화면이 느려집니다.
- 외부 API 장애가 바로 화면 장애가 됩니다.
- 데이터가 매번 달라져 판단 재현이 어렵습니다.
- provider별 실패를 추적하기 어렵습니다.

그래서 Argus는 먼저 DB에 저장합니다. dashboard API는 DB 최신값을 읽습니다.

## 14. 실제 명령 예시

KIS 파생/옵션 수집:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

현물/뉴스 mock 수집:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context
```

RSS 뉴스 수집:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --news-triggers-provider rss
```

Naver 뉴스 수집:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --news-triggers-provider naver
```

DART 공시 수집:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --news-triggers-provider dart
```

섞어서 수집:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --news-triggers-provider hybrid
```

## 15. API와 CLI의 차이

다시 정리하면 이렇습니다.

```text
CLI = 데이터를 가져와서 DB에 쌓는 명령
API = DB에 쌓인 데이터를 화면에 주는 입구
```

이 둘을 분리하는 것이 Argus 구조의 핵심입니다.

## 16. 한 줄 요약

```text
collect-context와 smoke-kis가 데이터를 쌓고, dashboard API가 그 데이터를 읽고, frontend가 보여준다.
```
