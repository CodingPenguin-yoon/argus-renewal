# News Analysis Feed Update

## 요약

2026-05-14 기준으로 기존 `뉴스 트리거` 상단 탭을 `뉴스 분석`으로 바꾸고, 내부 서브탭을 `메인`과 `뉴스`로 분리했습니다.

목표는 두 가지입니다.

- `메인`: 기존처럼 AI 판단을 거친 시장 연결 트리거를 보여줍니다.
- `뉴스`: 실시간 원천 경제 뉴스를 가능한 넓게 수집해 리스트로 보여줍니다.

이 변경은 Argus를 일반 뉴스 앱으로 바꾸는 것이 아닙니다. 원천 뉴스 피드는 시장 판단을 검증하고 이후 분류/요약/연결 기능을 붙이기 위한 입력면입니다.

## 화면 구조

상단 탭:

- 시장 판단: `/argus`
- 옵션·선물: `/argus/derivatives`
- 현물 반응: `/argus/reaction`
- 뉴스 분석: `/argus/triggers`

뉴스 분석 내부 탭:

- 메인: `/argus/triggers`
- 뉴스: `/argus/triggers/news`

## API와 데이터 계약

기존 dashboard API는 유지합니다.

```text
GET /api/argus/v2/dashboard
```

원천 뉴스 피드 API를 추가했습니다.

```text
GET /api/argus/v2/news-feed
```

`news-feed` 응답은 AI 판단 결과가 아니라 원천 뉴스 표시용 계약입니다.

```text
as_of
provider
status
observed_count
error
items[]
  id
  title
  summary
  source
  published_at
  source_url
  freshness
```

## Provider 정책

시장 판단용 뉴스 트리거:

- RSS/Naver/DART/hybrid provider가 원문 후보를 가져옵니다.
- AI enrichment JSON의 `should_use=true`인 항목만 dashboard trigger로 사용합니다.
- AI가 꺼져 있거나 실패하면 실뉴스를 임의로 호재/악재 분류하지 않습니다.

원천 뉴스 피드:

- `ARGUS_NEWS_FEED_PROVIDER`를 사용합니다.
- 기본값은 `rss`입니다.
- `ARGUS_NEWS_FEED_RSS_URLS`가 비어 있으면 `ARGUS_NEWS_TRIGGERS_RSS_URLS`를 재사용합니다.
- AI enrichment 없이 최신 뉴스 아이템을 그대로 나열합니다.

## 환경 변수

```text
ARGUS_NEWS_FEED_PROVIDER=rss
ARGUS_NEWS_FEED_RSS_URLS=
ARGUS_NEWS_FEED_QUERY=
ARGUS_NEWS_FEED_LIMIT=50
ARGUS_NEWS_FEED_LOOKBACK_HOURS=24
```

## 주요 변경 파일

Backend:

- `backend/src/argus_v2/api/router.py`
- `backend/src/argus_v2/contracts.py`
- `backend/src/argus_v2/providers/context_inputs.py`
- `backend/src/config/env.py`

Frontend:

- `frontend/src/app/argus/triggers/news/page.tsx`
- `frontend/src/argus_v2/components/dashboard.tsx`
- `frontend/src/argus_v2/contracts/dashboard.ts`
- `frontend/src/argus_v2/server/dashboard.ts`

Docs:

- `README.md`
- `RUN_GUIDE.md`
- `backend/README.md`
- `frontend/README.md`
- `doc/prd/`
- `doc/plans/`
- `doc/study/`

## 검증

실행한 검증:

- `pnpm --filter frontend test`
- `pnpm --filter frontend lint`
- `pnpm --filter frontend build`
- `pytest -q backend/tests`
- `PYTHONPYCACHEPREFIX=/private/tmp/argus_pycache python3 -m compileall backend/src`
- `curl -sS http://localhost:4000/api/argus/v2/news-feed`
- `curl -sS -I http://localhost:3000/argus/triggers/news`

확인 결과:

- frontend test 3건 통과.
- backend test 39건 통과.
- Next.js build 통과.
- `/api/argus/v2/news-feed`에서 RSS 50건 수신 확인.
- `/argus/triggers/news` 200 OK 확인.

## 남은 작업

- RSS source 확대와 중복 제거 기준 보정.
- Naver/DART/hybrid provider를 원천 뉴스 탭에서 운영 설정으로 확장.
- 뉴스 탭 필터, 검색, source 구분, 중요도 표시 추가.
- 원천 뉴스와 AI 트리거 간 연결 UI 설계.
- 장중 반복 수집 기준과 자동 스케줄러 결정.
