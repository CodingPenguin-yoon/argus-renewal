# Argus Study

이 폴더는 Argus v2를 이해하기 위한 공부용 문서입니다.

목표는 개발 용어를 외우는 것이 아닙니다.

목표는 아래 질문에 스스로 답할 수 있게 되는 것입니다.

- 데이터가 어디서 들어오는가?
- 누가 외부 API를 호출하는가?
- 왜 바로 화면에서 API를 부르지 않는가?
- DB에는 무엇을 저장하는가?
- AI 뉴스 판단은 어디서 실행되는가?
- 화면에는 어떤 계약으로 데이터가 전달되는가?
- 문제가 생기면 어디부터 봐야 하는가?

## 현재 Argus를 한 문장으로 설명하면

```text
파생/옵션 데이터와 실제 뉴스 AI 판단을 SQLite에 쌓고,
그 최신 상태를 대시보드에서 보기 쉽게 보여주는 한국장 시장 상황 도구입니다.
```

Argus는 추천주 앱이 아닙니다.

Argus는 “지금 시장을 움직이는 압력이 어디서 나오고 있는가”를 확인하는 도구입니다.

## 읽는 순서

1. `01-big-picture.md`
2. `02-terms.md`
3. `03-argus-flow.md`
4. `04-why-this-structure.md`
5. `05-debugging-and-operations.md`

## 각 문서 역할

`01-big-picture.md`

전체 구조를 비유와 그림으로 설명합니다. frontend, backend, DB, provider가 각각 무슨 역할인지 먼저 잡습니다.

`02-terms.md`

provider, service, adapter, contract, schema, migration, storage, AI enrichment 같은 용어를 쉽게 풉니다.

`03-argus-flow.md`

실제 Argus v2에서 데이터가 어떻게 들어와서 화면까지 가는지 명령어와 파일 경로 기준으로 설명합니다.

`04-why-this-structure.md`

왜 API 파일 하나에 다 넣지 않는지, 왜 DB를 거치는지, 왜 contract와 provider를 분리하는지 설명합니다.

`05-debugging-and-operations.md`

데이터가 안 보일 때 어디부터 확인할지, 장 시작 전/장중에 어떤 명령을 실행할지 정리합니다.

## 지금 꼭 기억할 핵심 문장

```text
provider는 가져오고,
storage는 저장하고,
dashboard는 조립하고,
judgement는 판단하고,
API는 전달하고,
frontend는 보여준다.
```

## 실제로 자주 볼 파일

Backend:

```text
backend/src/argus_v2/cli.py
backend/src/argus_v2/providers/context_inputs.py
backend/src/argus_v2/providers/kis_live.py
backend/src/argus_v2/storage.py
backend/src/argus_v2/dashboard.py
backend/src/argus_v2/judgement/engine.py
backend/src/argus_v2/api/router.py
backend/src/argus_v2/contracts.py
backend/src/config/env.py
```

Frontend:

```text
frontend/src/app/argus/page.tsx
frontend/src/app/argus/derivatives/page.tsx
frontend/src/app/argus/reaction/page.tsx
frontend/src/app/argus/triggers/page.tsx
frontend/src/app/argus/triggers/news/page.tsx
frontend/src/argus_v2/components/dashboard.tsx
frontend/src/argus_v2/contracts/dashboard.ts
frontend/src/argus_v2/server/dashboard.ts
```

문서:

```text
doc/prd/argus-v2-prd.md
doc/plans/current-status.md
doc/plans/mvp-closeout.md
doc/study/
```

## 공부할 때 추천 방식

처음부터 코드를 위에서 아래로 다 읽지 않습니다.

이 순서로 봅니다.

1. `doc/study/01-big-picture.md`로 전체 그림을 봅니다.
2. `doc/study/02-terms.md`로 용어를 익힙니다.
3. `python3 -m src.argus_v2.cli smoke-news-ai`가 어디서 시작하는지 `cli.py`에서 찾습니다.
4. `context_inputs.py`에서 Gemini 뉴스 판단 흐름을 봅니다.
5. `storage.py`에서 DB 저장 흐름을 봅니다.
6. `dashboard.py`에서 DB 데이터를 화면용으로 바꾸는 흐름을 봅니다.
7. `frontend/src/argus_v2/components/dashboard.tsx`에서 화면 표시를 봅니다.

## 현재 MVP 상태

2026-05-13 기준:

- 레거시 KRX 전환은 완료됐습니다.
- KIS 파생/옵션 smoke는 성공했습니다.
- KIS 현물 반응 collect는 성공했습니다.
- Gemini key는 인식됐습니다.
- `gemini-2.5-flash`로 AI 뉴스 smoke가 성공했습니다.
- RSS live 뉴스 1건이 Gemini 판단을 거쳐 DB에 저장됐습니다.
- dashboard 계약에서 AI reason/confidence/factors가 확인됐습니다.
- 2026-05-14에 `뉴스 분석 > 뉴스` 원천 뉴스 피드가 추가됐습니다.
- `/api/argus/v2/news-feed`와 `/argus/triggers/news`가 동작합니다.

남은 핵심:

- 장중 KIS 반복 수집 관찰.
- 원천 뉴스 source/중복/필터 UX 보정.
- Gemini prompt와 판단 엔진 가중치 보정.
