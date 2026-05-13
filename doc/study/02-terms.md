# 02. 용어 사전

이 문서는 Argus를 보면서 자주 나오는 개발 용어를 쉽게 풀어쓴 문서입니다.

전문 용어를 그대로 외우지 않아도 됩니다.

아래처럼 바꿔 읽으면 됩니다.

```text
provider = 데이터 가져오는 담당자
service = 특정 작업 담당자
adapter = 모양 변환기
contract = 데이터 모양 약속
schema = DB 설계도
migration = DB 설계 변경 기록
storage = DB 저장/조회 담당자
route = 주소 연결 규칙
CLI = 터미널 실행 명령
```

## 1. API

API는 프로그램끼리 대화하는 입구입니다.

사용자가 `/argus`를 열면 frontend는 backend에 데이터를 요청합니다.

```text
GET /api/argus/v2/dashboard
```

뜻:

```text
시장 판단 화면에 필요한 데이터를 주세요.
```

Argus backend API 입구:

```text
backend/src/argus_v2/api/router.py
```

API 파일은 얇게 유지하는 것이 좋습니다.

API 파일이 외부 API 호출, DB 저장, 판단, 화면용 조립을 다 하면 금방 지저분해집니다.

Argus에서 API의 역할:

- 요청을 받습니다.
- DB 연결을 엽니다.
- dashboard builder를 호출합니다.
- 결과를 JSON으로 반환합니다.
- DB가 비어 있으면 mock fallback을 반환합니다.

API가 하지 않는 일:

- KIS API 직접 호출.
- Gemini API 직접 호출.
- RSS 직접 수집.
- 복잡한 판단 계산 직접 수행.

## 2. Route

route는 주소와 코드를 연결하는 규칙입니다.

backend route:

```text
/api/argus/v2/dashboard
```

frontend route:

```text
/argus
/argus/derivatives
/argus/reaction
/argus/triggers
/argus/triggers/news
```

Next.js에서는 폴더 구조가 route가 됩니다.

예:

```text
frontend/src/app/argus/page.tsx
-> /argus
```

```text
frontend/src/app/argus/triggers/page.tsx
-> /argus/triggers
```

```text
frontend/src/app/argus/triggers/news/page.tsx
-> /argus/triggers/news
```

## 3. Provider

provider는 데이터 가져오는 담당자입니다.

외부 세계와 직접 대화하는 코드라고 보면 됩니다.

예:

```text
KIS provider = 한국투자 API에서 선물/옵션/현물 반응 가져오기
RSS provider = RSS feed에서 뉴스 가져오기
Naver provider = 네이버 뉴스 API에서 뉴스 가져오기
DART provider = 전자공시 API에서 공시 가져오기
Gemini provider = 뉴스가 시장 판단에 쓸 만한지 AI 판단하기
```

Argus provider 위치:

```text
backend/src/argus_v2/providers/
```

provider가 담당하는 일:

- 외부 API URL 조립.
- API key나 token 적용.
- 요청 파라미터 구성.
- 응답 받기.
- timeout, 실패, 빈 응답 처리.
- 외부 응답을 Argus 내부 record로 변환.

provider가 하지 말아야 할 일:

- frontend 화면 그리기.
- DB 테이블 구조를 마음대로 바꾸기.
- 시장 판단 라벨 전체를 혼자 결정하기.
- API key를 로그에 그대로 출력하기.

## 4. Service

service는 특정 작업을 처리하는 단위입니다.

Argus 예:

```text
ArgusNewsTriggerService
```

이 service는 뉴스 trigger 수집을 담당합니다.

하는 일:

- RSS/Naver/DART/macro source에서 후보 수집.
- 후보를 `NewsTriggerRecord`로 변환.
- Gemini AI 판단 적용.
- `should_use=true` 후보만 남김.
- provider batch로 반환.

service와 provider를 엄격히 나누는 팀도 있고, 거의 같은 의미로 쓰는 팀도 있습니다.

Argus에서는 이렇게 이해하면 충분합니다.

```text
provider/service = 외부 데이터를 가져와 Argus 내부 모양으로 정리하는 작업 담당
```

## 5. Adapter

adapter는 서로 다른 데이터 모양을 맞춰주는 변환기입니다.

외부 API 응답은 제각각입니다.

Naver 뉴스:

```text
title
originallink
link
description
pubDate
```

DART 공시:

```text
corp_name
report_nm
rcept_no
rcept_dt
```

KIS 국내파생:

```text
futs_prpr
hts_kor_isnm
```

Argus 내부에서는 한 모양으로 쓰고 싶습니다.

뉴스 내부 record:

```text
NewsTriggerRecord
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

adapter는 외부 모양을 내부 모양으로 바꿉니다.

Argus에서는 이런 함수들이 adapter 역할을 합니다.

```text
_rss_item_to_record
_normalize_file_row
_fetch_dart_records
_apply_news_ai_decision
```

## 6. Contract

contract는 데이터 모양 약속입니다.

backend가 frontend에게 이런 모양으로 데이터를 주겠다는 약속입니다.

Argus의 대표 contract:

```text
MarketDashboard
```

대략 이런 구조입니다.

```text
MarketDashboard
  as_of
  derivatives
  reaction
  triggers
  judgement
  provider_health
```

backend contract:

```text
backend/src/argus_v2/contracts.py
```

frontend contract:

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

contract가 있으면 좋은 점:

- backend와 frontend가 같은 약속을 봅니다.
- 필드가 빠지면 빨리 알 수 있습니다.
- 화면 코드를 안전하게 짤 수 있습니다.
- 테스트 기준이 생깁니다.

## 7. Schema

schema는 DB 설계도입니다.

DB 테이블이 어떤 칼럼을 가지는지 정합니다.

예:

```text
argus_v2_news_triggers
  title TEXT
  summary TEXT
  impact TEXT
  source_name TEXT
  published_at TEXT
  connection_strength TEXT
```

schema는 API contract와 다릅니다.

```text
schema = DB 저장 구조
contract = API 응답 구조
```

DB schema는 migration 파일에 있습니다.

```text
backend/src/argus_v2/migrations/
```

## 8. Migration

DB 구조를 바꾸는 기록입니다.

예:

```text
새 테이블 추가
새 칼럼 추가
index 추가
check constraint 추가
```

Argus migration 위치:

```text
backend/src/argus_v2/migrations/
```

왜 필요한가:

- DB 구조도 코드처럼 버전 관리해야 합니다.
- 어느 시점에 어떤 테이블이 생겼는지 추적할 수 있습니다.
- 새 개발 환경에서도 같은 DB 구조를 만들 수 있습니다.

쉬운 비유:

```text
migration = DB 공사 기록
```

## 9. Storage

storage는 DB 저장/조회 담당입니다.

Argus 위치:

```text
backend/src/argus_v2/storage.py
```

provider가 가져온 데이터를 DB에 넣을 때 storage를 씁니다.

dashboard가 최신 데이터를 읽을 때도 storage를 씁니다.

흐름:

```text
provider -> storage -> SQLite
SQLite -> storage -> dashboard
```

storage가 담당하는 것:

- provider run 저장.
- raw sample 저장.
- derivatives snapshot 저장.
- option chain snapshot/level 저장.
- market reaction snapshot/sector 저장.
- news trigger 저장.
- 최신 snapshot 조회.
- 민감값 redaction.

storage를 따로 두는 이유:

- SQL이 여기저기 흩어지지 않습니다.
- 저장 규칙이 한 곳에 모입니다.
- redaction을 빠뜨릴 가능성이 줄어듭니다.
- 나중에 SQLite에서 PostgreSQL로 바꾸기 쉬워집니다.

## 10. SQLite

SQLite는 파일 하나로 동작하는 가벼운 DB입니다.

Argus 로컬 DB:

```text
backend/data/argus.db
```

장점:

- 설치가 가볍습니다.
- 로컬 개발에 빠릅니다.
- 파일 하나라 관리가 쉽습니다.
- MVP 단계에서 충분합니다.

한계:

- 여러 서버가 동시에 쓰는 운영 환경에는 약합니다.
- 대규모 쓰기/조회에는 PostgreSQL이 더 적합합니다.

현재 판단:

```text
지금은 SQLite로 충분하고,
나중에 운영 규모가 커지면 PostgreSQL로 이동한다.
```

## 11. Raw Sample

raw sample은 외부 API에서 받은 원본 샘플입니다.

예:

- KIS 원본 응답 일부.
- RSS 원본 item.
- Naver 뉴스 원본 row.
- Gemini AI 판단 payload.

왜 저장하나:

- 외부 API가 실제로 뭘 줬는지 확인할 수 있습니다.
- 문서와 실제 응답이 다를 때 비교할 수 있습니다.
- 파싱 버그를 찾을 수 있습니다.
- 나중에 provider를 보정할 수 있습니다.

주의:

- raw sample에 API key, token, secret이 들어가면 안 됩니다.

## 12. Redaction

redaction은 민감값을 지우는 것입니다.

예:

```text
authorization: Bearer abc123
-> authorization: [REDACTED]
```

Argus가 가려야 하는 값:

- access_token.
- authorization.
- appsecret.
- client_secret.
- token.
- api_key.

redaction이 중요한 이유:

- raw sample은 디버깅에 필요합니다.
- 하지만 secret이 DB에 저장되면 위험합니다.
- 금융 API 프로젝트에서는 민감값을 남기지 않는 습관이 중요합니다.

## 13. Provider Run

provider run은 provider를 한 번 실행한 기록입니다.

예:

```text
provider_key: v2_news_triggers
status: success
observed_count: 1
sample_count: 1
started_at: ...
finished_at: ...
metadata_json: ...
```

왜 중요한가:

- 뉴스가 안 보이는 이유를 알 수 있습니다.
- KIS가 성공했는지 실패했는지 알 수 있습니다.
- AI가 disabled였는지 timeout이었는지 알 수 있습니다.
- provider별 실행 결과를 나중에 추적할 수 있습니다.

Argus 화면의 provider health는 이 기록과 최신 snapshot을 바탕으로 만들어집니다.

## 14. Provider Health

provider health는 데이터 수신 상태입니다.

상태:

```text
fresh = 정상
partial = 일부 수신
stale = 오래됨
missing = 없음
```

초보 투자자용 도구에서 중요합니다.

데이터가 없는데 판단을 확실하게 보여주면 위험합니다.

provider health는 이런 위험을 줄입니다.

## 15. CLI

CLI는 터미널에서 실행하는 명령입니다.

Argus CLI:

```text
backend/src/argus_v2/cli.py
```

명령:

```bash
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context
python3 -m src.argus_v2.cli smoke-news-ai
```

CLI 역할:

- 실제 외부 API 연결 확인.
- 데이터 수집.
- DB 저장.
- 운영 smoke test.

## 16. Smoke Test

smoke test는 “큰불이 나는지 빠르게 확인하는 실제 동작 테스트”입니다.

완벽한 검증은 아닙니다.

하지만 실제 연결이 되는지 확인하는 데 좋습니다.

Argus smoke:

```text
smoke-kis = KIS token, 파생, 옵션체인 연결 확인
smoke-news-ai = Gemini 뉴스 판단 연결 확인
```

성공했다고 모든 품질이 보장되는 것은 아닙니다.

성공의 의미:

```text
외부 API와 현재 설정이 최소한 연결은 된다.
```

## 17. Mock

mock은 가짜 데이터입니다.

왜 필요한가:

- API key 없이도 화면을 볼 수 있습니다.
- 외부 API 장애와 관계없이 개발할 수 있습니다.
- 테스트가 안정적입니다.
- 새 개발 환경에서 바로 실행할 수 있습니다.

Argus 원칙:

```text
run without external API keys
```

그래서 mock은 계속 필요합니다.

## 18. Fixture

fixture는 테스트용 고정 데이터입니다.

예:

```text
반도체 강세 뉴스 1건
FOMC 금리 상승 뉴스 1건
KIS 옵션체인 샘플 100건
```

mock과 fixture 차이:

```text
mock = 개발용 가짜 데이터
fixture = 테스트용 고정 데이터
```

## 19. Judgement Engine

judgement engine은 시장 판단 엔진입니다.

Argus 위치:

```text
backend/src/argus_v2/judgement/engine.py
```

보는 데이터:

- 선물 가격 변화.
- basis.
- market basis.
- 선물 미결제약정 증감률.
- 옵션 CALL/PUT 압력.
- 옵션 OI 변화.
- 현물 지수 반응.
- 강세/약세 섹터.
- 뉴스/매크로 trigger.
- 외국인 현물 수급 보조 신호.

출력 라벨:

```text
강한 상방
상방 우위
중립
하방 우위
강한 하방
```

주의:

- 추천이 아닙니다.
- 시장 상태 요약입니다.
- 실제 장중 사례로 계속 보정해야 합니다.

## 20. Dashboard Builder

dashboard builder는 DB에 있는 여러 데이터를 화면용 한 덩어리로 조립합니다.

Argus 위치:

```text
backend/src/argus_v2/dashboard.py
```

하는 일:

- 최신 derivatives snapshot 읽기.
- 최신 option chain snapshot 읽기.
- 최신 market reaction snapshot 읽기.
- 최신 news trigger 읽기.
- provider health 만들기.
- judgement engine 호출하기.
- `MarketDashboard`로 묶기.

dashboard builder는 외부 API를 호출하지 않습니다.

이미 저장된 DB 데이터만 읽습니다.

## 21. Frontend Component

component는 화면 조각입니다.

Argus 대표 component:

```text
frontend/src/argus_v2/components/dashboard.tsx
```

component가 하는 일:

- 카드 표시.
- 탭 구성.
- 라벨 표시.
- 숫자 포맷.
- empty/loading/error 상태 표시.
- financial disclaimer 표시.

component가 하지 말아야 할 일:

- KIS API 직접 호출.
- Gemini API 직접 호출.
- DB 직접 조회.
- secret 값 사용.

## 22. Zod

Zod는 TypeScript에서 데이터 모양을 검사하는 도구입니다.

Argus 위치:

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

역할:

- backend JSON이 frontend가 기대한 모양인지 검사.
- 필드가 빠졌거나 타입이 다르면 빨리 실패.

예:

```text
ai_confidence는 high, medium, low 중 하나여야 한다.
```

## 23. Pydantic

Pydantic은 Python에서 데이터 모양을 검사하는 도구입니다.

Argus 위치:

```text
backend/src/argus_v2/contracts.py
```

Zod와 비슷합니다.

```text
Pydantic = backend 계약 검사
Zod = frontend 계약 검사
```

## 24. Environment Variable

environment variable, 줄여서 env는 설정값입니다.

Argus env 예:

```env
KIS_APP_KEY=
KIS_APP_SECRET=
ARGUS_NEWS_AI_PROVIDER=gemini
ARGUS_GEMINI_MODEL=gemini-2.5-flash
ARGUS_GEMINI_API_KEY=
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

왜 env를 쓰나:

- API key를 코드에 넣지 않기 위해.
- 로컬/운영 설정을 다르게 하기 위해.
- provider를 쉽게 바꾸기 위해.
- timeout, limit 같은 운영값을 코드 수정 없이 바꾸기 위해.

주의:

- `.env`는 보통 커밋하지 않습니다.
- `.env.example`에는 키 값 없이 변수명만 둡니다.

## 25. AI Enrichment

AI enrichment는 원문 뉴스에 AI 판단 정보를 붙이는 것입니다.

RSS 원문에는 시장 판단에 필요한 구조화 정보가 없습니다.

RSS 원문:

```text
title
description
link
pubDate
```

AI enrichment 결과:

```json
{
  "should_use": true,
  "impact": "negative",
  "relevance_score": 90,
  "connection_strength": "strong",
  "confidence": "high",
  "summary": "미국 금리 상승과 달러 강세가 위험자산에 부담입니다.",
  "reason": "해외 금리와 달러는 한국장 외국인 수급과 지수 심리에 직접 연결됩니다.",
  "affected_factors": ["금리", "환율", "외국인 수급"]
}
```

Argus는 이 판단 결과를 보고 뉴스 trigger로 저장할지 결정합니다.

## 26. JSON Schema

JSON schema는 AI가 어떤 JSON 모양으로 응답해야 하는지 알려주는 설계도입니다.

Gemini에게 그냥 “판단해줘”라고 하면 자유로운 문장을 줄 수 있습니다.

Argus는 화면과 DB에 넣어야 하므로 정해진 JSON이 필요합니다.

그래서 AI에게 이런 구조를 요구합니다.

```text
should_use
impact
relevance_score
connection_strength
confidence
summary
reason
affected_factors
```

## 27. Rate Limit

rate limit은 외부 API 호출 제한입니다.

예:

```text
짧은 시간에 너무 많이 호출하면 429 Too Many Requests
```

Argus에서 실제로 있었던 일:

- RSS 후보가 많았습니다.
- 후보 전체를 Gemini에 보내면 429가 발생했습니다.
- 그래서 AI 호출 전에 후보를 줄이도록 수정했습니다.

현재 기본값:

```text
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

## 28. Timeout

timeout은 응답을 기다리는 최대 시간입니다.

외부 API가 너무 오래 걸리면 계속 기다리지 않고 끊습니다.

Argus 뉴스 AI timeout:

```text
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

timeout이 중요한 이유:

- 장중 대시보드는 빠르게 돌아야 합니다.
- 한 기사에서 오래 멈추면 전체 수집이 느려집니다.
- 실패 후보는 버리고 다음 후보로 넘어가는 편이 낫습니다.

## 29. Candidate

candidate는 아직 최종 저장 전인 후보 데이터입니다.

뉴스 흐름:

```text
RSS item
-> NewsTriggerRecord candidate
-> query/limit 적용
-> Gemini 판단
-> should_use=true면 trigger 저장
```

candidate를 줄이는 이유:

- AI 비용 절감.
- timeout 감소.
- rate limit 감소.
- 잡음 뉴스 감소.

## 30. Freshness

freshness는 데이터가 얼마나 최신인지 나타냅니다.

예:

```text
fresh = 방금 들어온 데이터
partial = 일부만 들어온 데이터
stale = 오래된 데이터
missing = 데이터 없음
```

금융 대시보드에서 freshness는 매우 중요합니다.

오래된 데이터를 최신처럼 보여주면 판단이 왜곡됩니다.

## 31. 한 줄 정리

Argus 용어를 쉽게 바꾸면 이렇습니다.

```text
provider는 가져오고,
adapter는 모양을 바꾸고,
storage는 저장하고,
contract는 약속하고,
dashboard는 조립하고,
judgement는 판단하고,
frontend는 보여준다.
```
