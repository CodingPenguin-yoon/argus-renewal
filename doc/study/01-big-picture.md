# 01. 전체 그림

## 1. 웹앱은 크게 두 덩어리입니다

Argus는 크게 보면 두 덩어리입니다.

```text
사용자가 보는 화면 = frontend
데이터를 가져오고 판단해서 주는 서버 = backend
```

frontend는 브라우저에 보이는 화면입니다. 버튼, 탭, 카드, 문장, 숫자를 보여줍니다.

backend는 화면에 필요한 데이터를 준비합니다. 외부 API에서 데이터를 가져오고, DB에 저장하고, 필요한 모양으로 정리해서 frontend에 넘깁니다.

## 2. Frontend는 식당 홀, Backend는 주방입니다

비유하면 이렇습니다.

```text
손님 = 사용자
홀 = frontend
주방 = backend
재료 창고 = DB
식재료 납품처 = 외부 API
```

손님은 홀에서 메뉴를 봅니다. 하지만 요리를 직접 만들지는 않습니다. 홀은 주문을 주방에 전달하고, 주방은 창고와 납품처에서 재료를 가져와 요리를 만듭니다.

Argus도 같습니다. 사용자는 `/argus` 화면을 봅니다. 화면은 backend의 `/api/argus/v2/dashboard`에 데이터를 요청합니다. backend는 DB에 저장된 최신 시장 데이터를 읽고, 판단 엔진을 거쳐 화면에 줄 결과를 만듭니다.

## 3. Argus의 핵심 흐름

Argus v2의 핵심 흐름은 이렇습니다.

```text
외부 데이터
-> provider
-> storage
-> dashboard builder
-> judgement engine
-> API
-> frontend
```

쉬운 말로 바꾸면 이렇습니다.

```text
외부 데이터
-> 데이터 가져오는 담당자
-> DB 저장소
-> 화면용 데이터 조립
-> 시장 판단
-> 서버 응답
-> 화면 표시
```

## 4. 왜 바로 화면에서 외부 API를 부르지 않나

화면에서 바로 네이버 뉴스 API, KIS API, DART API를 호출할 수도 있을 것처럼 보입니다. 하지만 보통 그렇게 하지 않습니다.

이유는 네 가지입니다.

- API 키가 브라우저에 노출될 수 있습니다.
- 외부 API 응답 모양이 바뀌면 화면 코드가 바로 깨집니다.
- 같은 데이터를 매번 다시 부르면 느리고 비쌉니다.
- 과거 데이터를 누적해서 비교하기 어렵습니다.

그래서 Argus는 외부 데이터를 backend에서 가져오고 DB에 저장합니다. 화면은 외부 API를 직접 알 필요 없이 backend가 정리한 결과만 받습니다.

## 5. Argus는 두 종류의 실행이 있습니다

Argus backend에는 크게 두 종류의 실행이 있습니다.

```text
API 실행 = 화면이 요청할 때 응답
CLI 실행 = 사람이 명령어로 데이터 수집
```

API는 예를 들어 이런 것입니다.

```text
GET /api/argus/v2/dashboard
```

CLI는 터미널에서 실행하는 명령입니다.

```bash
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context
```

API는 “화면에 줄 데이터를 내놔”에 가깝습니다. CLI는 “외부 데이터를 가져와서 DB에 저장해”에 가깝습니다.

## 6. 왜 수집과 조회를 분리하나

중요한 구조입니다.

```text
수집 = 외부 API 호출, 실패 가능, 느릴 수 있음
조회 = DB에서 읽기, 빠르고 안정적
```

화면을 열 때마다 외부 API를 전부 호출하면 느리고 불안정합니다. KIS나 네이버가 잠깐 느려지면 Argus 화면도 느려집니다.

그래서 수집은 CLI나 스케줄러가 따로 합니다. 화면 API는 DB에 저장된 최신 데이터를 빠르게 읽습니다.

## 7. Argus v2 현재 큰 구조

현재 중요한 backend 파일은 이렇습니다.

```text
backend/src/argus_v2/
  api/router.py          화면이 호출하는 API 입구
  cli.py                 터미널 수집 명령
  contracts.py           API 응답 모양 약속
  dashboard.py           DB 데이터를 화면용으로 조립
  judgement/engine.py    시장 판단 엔진
  providers/             외부 데이터 가져오는 담당자들
  storage.py             DB 저장/조회 담당
  db.py                  SQLite 연결과 migration
  migrations/            DB 테이블 생성 SQL
```

frontend는 이렇습니다.

```text
frontend/src/app/argus/
  page.tsx               시장 판단 화면
  derivatives/page.tsx   옵션·선물 화면
  reaction/page.tsx      현물 반응 화면
  triggers/page.tsx      뉴스 트리거 화면

frontend/src/argus_v2/
  components/dashboard.tsx   실제 화면 컴포넌트
  contracts/dashboard.ts     frontend가 기대하는 데이터 모양
  server/dashboard.ts        backend API 호출
```

## 8. 제일 먼저 익혀야 할 문장

이 문장 하나를 기억하면 구조가 쉬워집니다.

```text
provider는 가져오고, storage는 저장하고, dashboard는 조립하고, API는 전달하고, frontend는 보여준다.
```

Argus 코드를 볼 때 이 기준으로 보면 됩니다.
