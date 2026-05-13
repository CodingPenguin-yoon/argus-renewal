# 01. 전체 그림

## 1. Argus는 무엇을 하려는 프로젝트인가

Argus v2는 한국장 시장 상황을 보기 쉽게 정리하는 도구입니다.

특히 아래 정보를 한 화면에서 연결해서 보려는 프로젝트입니다.

- KOSPI200 선물.
- 옵션체인.
- 미결제약정 변화.
- basis.
- 현물 지수 반응.
- 강세/약세 섹터.
- 외국인/기관/개인 현물 수급.
- 실제 뉴스.
- 매크로 이벤트.
- AI가 정리한 뉴스 판단 근거.

핵심 목표는 “정보를 많이 보여주기”가 아닙니다.

핵심 목표는 “오늘 시장을 흔드는 압력이 어디에서 오는지 빨리 파악하기”입니다.

## 2. Argus는 추천주 앱이 아니다

Argus는 아래 같은 문장을 목표로 합니다.

```text
미국 금리 상승과 달러 강세가 위험자산에 부담입니다.
장중 외국인 수급은 약하고 옵션은 PUT 압력이 강합니다.
다만 반도체 섹터가 버티고 있어 낙폭은 제한되는 모습입니다.
```

이런 문장은 매수/매도 추천이 아닙니다.

시장을 읽기 위한 상황 설명입니다.

Argus가 피해야 하는 것:

- 특정 종목 추천.
- 확정적 예언.
- 근거 없는 호재/악재 분류.
- 데이터가 없는데 있는 것처럼 말하기.
- AI가 실패했는데 임의로 뉴스 판단하기.

## 3. 전체 구조는 세 덩어리다

Argus는 크게 세 덩어리입니다.

```text
frontend = 사용자가 보는 화면
backend = 데이터 수집, 저장, 판단, API
SQLite DB = 수집한 데이터와 실행 기록 저장
```

더 쉽게 비유하면 이렇습니다.

```text
사용자 = 손님
frontend = 식당 홀
backend = 주방
SQLite DB = 재료 창고
외부 API = 식재료 납품처
```

손님은 주방에 직접 들어가지 않습니다.

사용자는 KIS API, Gemini API, RSS를 직접 보지 않습니다.

사용자는 frontend 화면만 봅니다.

frontend는 backend에게 정리된 시장 데이터를 요청합니다.

backend는 DB에서 최신 데이터를 읽고 화면용으로 정리합니다.

## 4. 가장 중요한 데이터 흐름

Argus v2의 핵심 흐름입니다.

```text
외부 데이터
-> provider
-> storage
-> SQLite DB
-> dashboard builder
-> judgement engine
-> API
-> frontend
```

쉬운 말로 바꾸면 이렇습니다.

```text
외부에서 가져온다
-> 내부 모양으로 바꾼다
-> DB에 저장한다
-> 화면용으로 조립한다
-> 시장 판단을 붙인다
-> API로 전달한다
-> 화면에 보여준다
```

이 흐름을 기억하면 파일 위치도 이해하기 쉬워집니다.

## 5. 수집과 조회는 다르다

Argus에서 가장 중요한 구분입니다.

```text
수집 = 외부 API 호출
조회 = DB에서 읽기
```

수집은 느릴 수 있습니다.

수집은 실패할 수 있습니다.

수집은 API key, token, timeout, rate limit에 영향을 받습니다.

조회는 빨라야 합니다.

조회는 화면을 열 때마다 안정적으로 동작해야 합니다.

그래서 Argus는 화면을 열 때 외부 API를 직접 호출하지 않습니다.

대신 먼저 CLI로 데이터를 수집해서 DB에 저장합니다.

화면은 DB에 저장된 최신 값을 읽습니다.

## 6. API와 CLI의 차이

Argus backend에는 두 종류의 실행 입구가 있습니다.

API:

```text
GET /api/argus/v2/dashboard
```

CLI:

```bash
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context
python3 -m src.argus_v2.cli smoke-news-ai
```

API는 화면이 부릅니다.

CLI는 사람이 터미널에서 실행하거나, 나중에 스케줄러가 실행합니다.

역할은 다릅니다.

```text
CLI = 데이터를 가져와 DB에 쌓는다
API = DB에 쌓인 데이터를 화면에 준다
```

## 7. 왜 frontend에서 KIS나 Gemini를 직접 부르지 않나

브라우저에서 직접 KIS API나 Gemini API를 호출하면 안 됩니다.

이유:

- API key가 브라우저에 노출될 수 있습니다.
- 외부 API 응답 모양이 바뀌면 화면 코드가 바로 깨집니다.
- 장중에 화면을 열 때마다 외부 API를 때리면 느립니다.
- 같은 데이터를 누적 비교하기 어렵습니다.
- 실패 로그를 체계적으로 남기기 어렵습니다.
- token, app secret, client secret 같은 민감값을 다루기 어렵습니다.

그래서 외부 API 호출은 backend provider가 담당합니다.

frontend는 backend가 만든 `MarketDashboard`만 받습니다.

## 8. 현재 Argus의 실제 큰 흐름

장 시작 전 또는 장중 수집:

```text
smoke-kis
-> KIS token 발급
-> 국내파생 snapshot 수집
-> 옵션체인 수집
-> SQLite 저장
```

```text
collect-context
-> KIS 현물 반응 수집
-> RSS 뉴스 수집
-> Gemini AI 뉴스 판단
-> SQLite 저장
```

화면 조회:

```text
/argus 접속
-> frontend server 함수
-> backend dashboard API
-> SQLite 최신값 조회
-> dashboard builder
-> judgement engine
-> frontend component 표시
```

## 9. 현재 중요한 backend 파일

```text
backend/src/argus_v2/cli.py
```

터미널 명령 입구입니다.

`smoke-kis`, `collect-context`, `smoke-news-ai`가 여기서 시작합니다.

```text
backend/src/argus_v2/providers/
```

외부 데이터를 가져오는 담당자들이 모여 있습니다.

KIS, RSS, Gemini, DART, Naver 같은 외부 세계와 대화합니다.

```text
backend/src/argus_v2/storage.py
```

SQLite DB에 저장하고 조회하는 담당입니다.

provider run, raw sample, snapshot, trigger를 저장합니다.

```text
backend/src/argus_v2/dashboard.py
```

DB 최신 데이터를 화면용 `MarketDashboard`로 조립합니다.

```text
backend/src/argus_v2/judgement/engine.py
```

파생/옵션, 뉴스, 현물 반응을 종합해서 `하방 우위`, `상방 우위` 같은 판단 라벨을 만듭니다.

```text
backend/src/argus_v2/api/router.py
```

frontend가 호출하는 API 입구입니다.

```text
backend/src/argus_v2/contracts.py
```

backend가 frontend에 주는 데이터 모양 약속입니다.

## 10. 현재 중요한 frontend 파일

```text
frontend/src/app/argus/page.tsx
frontend/src/app/argus/derivatives/page.tsx
frontend/src/app/argus/reaction/page.tsx
frontend/src/app/argus/triggers/page.tsx
```

Next.js route 파일입니다.

각 URL과 화면을 연결합니다.

```text
frontend/src/argus_v2/server/dashboard.ts
```

backend dashboard API를 호출합니다.

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

backend가 준 JSON이 frontend가 기대하는 모양인지 Zod로 검사합니다.

```text
frontend/src/argus_v2/components/dashboard.tsx
```

실제 화면 카드, 탭, 패널을 그립니다.

## 11. DB는 왜 필요한가

DB는 단순히 데이터를 보관하는 파일이 아닙니다.

Argus에서 DB는 운영 기록입니다.

DB에 저장하는 이유:

- 같은 데이터를 다시 볼 수 있습니다.
- 직전 snapshot과 비교할 수 있습니다.
- provider가 성공했는지 실패했는지 기록할 수 있습니다.
- 외부 API raw sample을 확인할 수 있습니다.
- AI가 어떤 이유로 뉴스를 선택했는지 추적할 수 있습니다.
- 화면이 외부 API 속도에 영향받지 않습니다.

현재 로컬 DB:

```text
backend/data/argus.db
```

## 12. AI는 어디에 붙어 있는가

AI는 frontend에 붙어 있지 않습니다.

AI는 뉴스 provider 흐름 안에 붙어 있습니다.

흐름:

```text
RSS 기사 수집
-> NewsTriggerRecord 후보 생성
-> 후보 제한
-> Gemini에게 JSON 판단 요청
-> should_use=true인 것만 trigger로 저장
-> dashboard API가 읽음
-> frontend가 reason/confidence/factors 표시
```

현재 기본 모델:

```text
gemini-2.5-flash
```

AI가 결정하는 것:

- 이 뉴스를 시장 판단에 쓸지.
- 긍정/부정/중립인지.
- 한국장과 연결 강도가 강한지 약한지.
- 어떤 요인이 영향받는지.
- 왜 그렇게 판단했는지.

AI가 실패하면:

```text
실뉴스를 임의 분류하지 않는다.
```

## 13. provider health가 왜 중요한가

금융 대시보드에서 가장 위험한 것은 데이터가 없는데 있는 척하는 것입니다.

그래서 Argus는 provider health를 보여줍니다.

상태:

```text
fresh = 정상
partial = 일부 수신
stale = 오래됨
missing = 없음
```

예를 들어 뉴스가 안 보일 때 가능한 원인은 여러 가지입니다.

```text
RSS 수집 실패
Gemini key 없음
Gemini timeout
AI가 should_use=false 판단
DB 저장 실패
화면 contract 오류
```

provider health와 provider run 기록이 있으면 원인을 좁힐 수 있습니다.

## 14. 지금 단계에서 가장 중요한 생각

Argus는 아직 “완성된 예측기”가 아닙니다.

현재 중요한 것은 구조가 제대로 닫혔는지입니다.

```text
데이터가 들어온다
저장된다
판단된다
화면에 표시된다
실패 원인을 볼 수 있다
```

이 구조가 닫히면 이후에는 데이터 품질과 판단 품질을 하나씩 올리면 됩니다.

## 15. 한 줄 암기

```text
Argus는 외부 데이터를 바로 화면에 뿌리는 앱이 아니라,
외부 데이터를 내부 계약으로 바꿔 DB에 쌓고,
그 최신 상태를 시장 판단 대시보드로 보여주는 앱이다.
```
