# 02. 용어 사전

## 1. API

API는 프로그램끼리 대화하는 입구입니다.

사용자가 브라우저에서 `/argus`를 열면 frontend가 backend에 이런 식으로 물어봅니다.

```text
GET /api/argus/v2/dashboard
```

뜻은 이렇습니다.

```text
시장 판단 화면에 필요한 데이터를 주세요.
```

Argus에서 API 입구는 여기입니다.

```text
backend/src/argus_v2/api/router.py
```

API는 보통 얇게 유지합니다. API 파일 안에 외부 API 호출, DB 저장, 복잡한 판단을 다 넣지 않습니다. API는 입구입니다. 입구가 요리까지 하면 구조가 금방 지저분해집니다.

## 2. Route

route는 주소와 코드를 연결하는 규칙입니다.

예를 들어 backend에서:

```text
/api/argus/v2/dashboard
```

이 주소가 `market_dashboard()` 함수와 연결됩니다.

frontend에서도 route가 있습니다.

```text
/argus
/argus/derivatives
/argus/reaction
/argus/triggers
```

이 주소들은 각각 화면 파일과 연결됩니다.

## 3. Provider

provider는 데이터 가져오는 담당자입니다.

예시는 이렇습니다.

```text
KIS provider = 한국투자 API에서 선물/옵션 데이터 가져오는 담당
RSS provider = RSS에서 뉴스 가져오는 담당
Naver provider = 네이버 뉴스 API에서 뉴스 가져오는 담당
DART provider = 전자공시 API에서 공시 가져오는 담당
```

provider는 외부 세계와 직접 대화합니다. 외부 API 주소, 인증 헤더, 응답 파싱 같은 지저분한 일을 provider 안에 몰아둡니다.

Argus provider 위치는 여기입니다.

```text
backend/src/argus_v2/providers/
```

## 4. Service

service는 특정 일을 처리하는 작업 단위입니다.

예를 들어 `ArgusNewsTriggerService`는 뉴스 트리거 수집 일을 담당합니다.

```text
ArgusNewsTriggerService
-> RSS/Naver/DART에서 뉴스나 공시 가져오기
-> Argus가 이해하는 NewsTriggerRecord로 바꾸기
```

service와 provider를 엄격히 구분하는 팀도 있고, 거의 같은 의미로 쓰는 팀도 있습니다. Argus에서는 “외부 데이터를 가져와 정리하는 작업 담당” 정도로 이해하면 충분합니다.

## 5. Adapter

adapter는 서로 다른 모양을 맞춰주는 변환기입니다.

외부 API들은 응답 모양이 제각각입니다.

```text
Naver: title, link, description, pubDate
DART: corp_name, report_nm, rcept_no, rcept_dt
KIS: output, output1, futs_prpr, hts_kor_isnm 등
```

Argus는 화면과 판단 엔진에서 같은 모양을 쓰고 싶습니다.

```text
NewsTriggerRecord:
  title
  summary
  impact
  source
  published_at
```

adapter는 외부 모양을 Argus 모양으로 바꿉니다. 현재 Argus에서는 provider/service 안의 `_naver_item_to_record`, `_dart_row_to_record` 같은 함수가 adapter 역할을 합니다.

## 6. Contract

contract는 데이터 모양 약속입니다.

backend가 frontend에 이런 모양으로 데이터를 주겠다고 약속합니다.

```text
MarketDashboard
  as_of
  derivatives
  triggers
  reaction
  judgement
  provider_health
```

backend contract는 여기입니다.

```text
backend/src/argus_v2/contracts.py
```

frontend도 같은 약속을 검증합니다.

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

contract가 있으면 좋은 점은 분명합니다. backend가 이상한 모양으로 데이터를 주면 빨리 알 수 있습니다. frontend도 “이 데이터가 있을 거다”라고 믿고 코드를 짤 수 있습니다.

## 7. Schema

schema는 DB 테이블이나 데이터 구조의 설계도입니다.

DB schema 예시는 이렇습니다.

```text
argus_v2_news_triggers
  title TEXT
  summary TEXT
  impact TEXT
  published_at TEXT
```

Argus의 DB schema는 migration 파일에 있습니다.

```text
backend/src/argus_v2/migrations/
```

contract는 API 데이터 모양 약속이고, schema는 DB 저장 구조라고 보면 됩니다.

## 8. Migration

migration은 DB 구조를 바꾸는 기록입니다.

예를 들어 새 테이블이 필요하면 migration SQL 파일을 만듭니다.

```text
argus_v2_001_storage.sql
argus_v2_002_reaction_triggers.sql
```

앱이 실행되면 `db.py`가 아직 적용되지 않은 migration을 DB에 적용합니다.

왜 migration이 필요하냐면, DB 구조도 코드처럼 버전 관리해야 하기 때문입니다.

## 9. Storage

storage는 DB 저장/조회 담당입니다.

provider가 외부 데이터를 가져오면 storage가 DB에 저장합니다.

```text
provider -> storage -> SQLite DB
```

API가 화면용 데이터를 만들 때도 storage가 DB에서 최신 데이터를 읽습니다.

```text
API -> storage -> SQLite DB
```

Argus storage 위치는 여기입니다.

```text
backend/src/argus_v2/storage.py
```

## 10. SQLite

SQLite는 파일 하나로 동작하는 가벼운 DB입니다.

Argus 로컬 개발에서는 이 파일을 씁니다.

```text
backend/data/argus.db
```

나중에 서버 운영이 커지면 PostgreSQL 같은 DB로 바꿀 수 있습니다. 하지만 지금 단계에서는 SQLite가 빠르고 단순합니다.

## 11. Raw Sample

raw sample은 외부 API에서 받은 원본 샘플입니다.

예를 들어 Naver가 준 원본 row, KIS가 준 원본 payload를 일부 저장합니다.

왜 저장하냐면:

- 나중에 외부 API 응답이 이상할 때 확인할 수 있습니다.
- 파싱 로직이 잘못됐는지 비교할 수 있습니다.
- provider가 실제로 뭘 받았는지 추적할 수 있습니다.

단, API 키나 token 같은 민감값은 저장하면 안 됩니다. 그래서 Argus storage는 `access_token`, `authorization`, `appsecret` 같은 값을 `[REDACTED]`로 지웁니다.

## 12. Redaction

redaction은 민감값을 지우는 것입니다.

예시:

```text
authorization: Bearer abc123
-> authorization: [REDACTED]
```

Argus에서는 raw sample 저장 전에 민감값을 자동으로 가립니다.

## 13. Provider Run

provider run은 provider를 한 번 실행한 기록입니다.

예를 들어 `collect-context`를 한 번 실행하면 이런 기록이 남습니다.

```text
provider_key: v2_news_triggers
status: success
observed_count: 8
started_at: ...
finished_at: ...
```

이 기록이 있으면 “뉴스가 안 보이는 이유가 수집 실패인지, 수집은 됐는데 필터에 걸린 건지”를 구분할 수 있습니다.

## 14. Provider Health

provider health는 데이터 수신 상태입니다.

Argus 화면 하단의 “데이터 수신 상태”가 이 개념입니다.

상태는 대략 이렇게 나뉩니다.

```text
fresh = 정상
partial = 일부 수신
stale = 지연
missing = 미수신
```

초보 투자자용 도구에서 특히 중요합니다. 데이터가 안 들어왔는데 마치 확실한 판단처럼 보여주면 안 되기 때문입니다.

## 15. CLI

CLI는 터미널에서 실행하는 명령입니다.

Argus CLI는 여기입니다.

```text
backend/src/argus_v2/cli.py
```

예시:

```bash
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context
```

CLI는 주로 데이터 수집, 테스트, 운영 작업에 씁니다.

## 16. Smoke Test

smoke test는 “큰불은 안 나는지 확인하는 간단한 실제 동작 테스트”입니다.

`smoke-kis`는 KIS API가 실제로 token을 발급하고 선물/옵션 데이터를 받아 DB에 저장하는지 확인합니다.

완벽한 테스트는 아니지만, 실제 연결이 되는지 빠르게 확인할 수 있습니다.

## 17. Mock

mock은 가짜 데이터입니다.

왜 가짜 데이터를 쓰냐면:

- API 키 없이도 개발할 수 있습니다.
- 외부 API가 죽어도 화면 개발을 계속할 수 있습니다.
- 테스트를 안정적으로 만들 수 있습니다.

Argus는 DB가 비어 있으면 mock dashboard를 보여줍니다. 또한 `collect-context` 기본 provider도 mock입니다.

## 18. Fixture

fixture는 테스트용 고정 데이터입니다.

예를 들어 테스트에서 “반도체 강세 뉴스 1건”을 고정해두고, provider가 이걸 잘 변환하는지 확인할 수 있습니다.

mock은 개발용 가짜 데이터라는 느낌이 강하고, fixture는 테스트용 고정 데이터라는 느낌이 강합니다.

## 19. Judgement Engine

judgement engine은 시장 판단 엔진입니다.

Argus에서는 아래 데이터를 종합해서 판단 라벨을 만듭니다.

```text
파생/옵션
뉴스 트리거
현물 반응
```

결과는 이런 라벨 중 하나입니다.

```text
강한 상방
상방 우위
중립
하방 우위
강한 하방
```

위치는 여기입니다.

```text
backend/src/argus_v2/judgement/engine.py
```

## 20. Dashboard Builder

dashboard builder는 DB에 있는 여러 데이터를 화면용 한 덩어리로 조립합니다.

Argus 위치는 여기입니다.

```text
backend/src/argus_v2/dashboard.py
```

하는 일은 이렇습니다.

```text
최신 파생 snapshot 읽기
최신 옵션체인 읽기
최신 현물 반응 읽기
최신 뉴스 트리거 읽기
provider health 만들기
judgement engine 호출하기
MarketDashboard로 묶기
```

## 21. Frontend Component

component는 화면 조각입니다.

Argus 화면 컴포넌트는 여기 있습니다.

```text
frontend/src/argus_v2/components/dashboard.tsx
```

예를 들어 시장 판단 패널, 옵션·선물 패널, 현물 반응 패널, 뉴스 트리거 패널이 component입니다.

## 22. Zod

Zod는 frontend에서 데이터 모양을 검사하는 도구입니다.

backend가 준 JSON이 frontend가 기대한 모양인지 확인합니다.

Argus 위치는 여기입니다.

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

## 23. Pydantic

Pydantic은 Python backend에서 데이터 모양을 검사하는 도구입니다.

Argus backend contract는 Pydantic 모델로 되어 있습니다.

```text
backend/src/argus_v2/contracts.py
```

Zod와 Pydantic은 역할이 비슷합니다. 하나는 frontend 쪽, 하나는 backend 쪽입니다.

## 24. Environment Variable

environment variable, 줄여서 env는 설정값입니다.

API 키, DB 경로, provider 선택 같은 값을 코드에 박아두지 않고 `.env`로 뺍니다.

예시:

```text
KIS_APP_KEY=
ARGUS_NEWS_NAVER_CLIENT_ID=
ARGUS_DISCLOSURE_DART_API_KEY=
```

코드에 API 키를 직접 쓰면 보안상 위험합니다. 그래서 env로 관리합니다.

## 25. Provider 이름이 왜 영어인가

provider, service, storage 같은 용어는 개발자들이 자주 쓰는 관습입니다. 꼭 영어로 이해할 필요는 없습니다.

이렇게 바꿔 읽으면 됩니다.

```text
provider = 데이터 가져오는 담당자
service = 특정 작업 담당자
storage = 저장소 담당자
contract = 데이터 모양 약속
schema = DB 설계도
migration = DB 설계 변경 기록
route = 주소 연결 규칙
```
