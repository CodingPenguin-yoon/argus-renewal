# KRX News Domain Docs

현재 코드 기준으로 뉴스 서브시스템을 이해하고 운영하기 위한 도메인 문서 묶음입니다.

## 이 폴더의 목적
- 뉴스 서브시스템의 현재 런타임 구조를 기능 단위로 나눠 읽을 수 있게 합니다.
- 코드만 바로 열면 놓치기 쉬운 `DB -> backend -> API -> frontend` 연결을 먼저 잡게 합니다.
- 운영 절차보다 구조 이해와 파일 책임 파악에 집중합니다.

## 추천 읽는 순서
1. `pipeline.md`
2. `database-tables.md`
3. `ingestion-automation.md`
4. `materialization.md`
5. `api-layers.md`
6. `frontend-surface.md`
7. `file-reference.md`

## 문서 묶음 설명
- `pipeline.md`
  - 전체 흐름을 가장 짧게 잡는 입문 문서
  - cron, raw ingestion, materialization, API, polling의 연결을 먼저 설명합니다.
- `ingestion-automation.md`
  - `run-news-automation`, provider adapter, raw document 적재, event normalization 경계를 설명합니다.
- `materialization.md`
  - `NewsProductService`, batch triage, compare AI, state/history 기록을 자세히 설명합니다.
- `api-layers.md`
  - `/api/news/*`와 `/api/krx/news/*`를 왜 둘로 나눴는지와 각 route가 어떤 서비스 메서드를 쓰는지 설명합니다.
- `frontend-surface.md`
  - `/krx/news` 페이지가 SSR과 60초 polling을 같이 쓰는 이유와 파일별 책임을 설명합니다.
- `database-tables.md`
  - migration, 테이블, 주요 컬럼, 관계, 읽기/쓰기 주체를 정리합니다.
- `file-reference.md`
  - 가장 실전적인 문서입니다.
  - 파일 하나씩 "언제 실행되는지", "무슨 입력을 받고", "무슨 출력을 만드는지"를 정리합니다.

## 범위
- 이 폴더는 `뉴스 리빌드 관련 파일` 중심입니다.
- 포함:
  - `backend/src/krx/news/*`
  - `backend/src/krx/market_news/router.py`
  - `backend/src/krx/news/router.py`
  - `backend/src/krx/source_ingestion/cli.py`
  - `backend/src/krx/source_ingestion/service.py`
  - `backend/src/krx/source_ingestion/event_service.py`
  - `frontend/src/app/krx/news/page.tsx`
  - `frontend/src/app/api/krx/news-tab/route.ts`
  - `frontend/src/krx/news/*`
  - `frontend/src/krx/server/data-service.ts`
  - 뉴스 관련 migration
- 제외:
  - 매크로 캘린더 전체 구현
  - 파생/시장신호 전체 구현
  - 회사 리포트 전체 구현

## 같이 보면 좋은 문서
- `../../architecture/system-map.md`
- `source-map.md`
- `rebuild-summary.md`
- `runbook.md`

## 읽는 팁
- 먼저 `pipeline.md`와 `database-tables.md`를 읽고 나서 코드를 보면 훨씬 덜 헷갈립니다.
- `file-reference.md`는 코드 옆에 띄워두고 참조하는 용도로 쓰는 게 좋습니다.
- 구조 판단은 오래된 설계 문서보다 현재 코드와 테스트를 우선합니다.
