# KRX News Pipeline Overview

현재 코드 기준으로 뉴스 리빌드의 전체 흐름을 가장 먼저 이해하기 위한 문서입니다.

## 한 줄 요약
- 뉴스 탭은 `raw_documents`를 바로 읽지 않습니다.
- 먼저 `news_batch_triage`로 1차 판단을 저장하고,
- 그 다음 `market_surface_candidates -> market_surface_state`로 화면용 표면을 만든 뒤,
- `/api/news/*`를 통해 프런트가 읽습니다.

## 큰 그림
```text
cron
-> run-news-automation
-> raw ingestion
-> raw_documents
-> news_batch_triage
-> market_surface_candidates
-> market_surface_state + market_surface_history
-> /api/news/*
-> /krx/news SSR
-> 60초 polling
```

## 이 구조가 필요한 이유
- 원문 수집과 화면 렌더링의 목적이 다릅니다.
- `raw_documents`는 "있는 그대로 모아두는 입력 저장소"입니다.
- 뉴스 탭은 "지금 화면에 무엇을 대표 카드로 보여줄지"를 빠르게 판단해야 합니다.
- 그래서 중간에 `triage`와 `materialization` 단계를 따로 둡니다.

## 런타임 모드 세 가지

### 1. cron 기반 배치 모드
- 운영 배치는 앱 내부 scheduler가 아니라 `cron`이 CLI를 호출합니다.
- 진입 파일:
  - `backend/src/krx/source_ingestion/cli.py`
  - `backend/src/krx/source_ingestion/schedule.py`
- 핵심 명령:
  - `python3 -m src.krx.source_ingestion.cli run-news-automation`

### 2. API 읽기 모드
- 사용자 화면은 `/api/news/*` 또는 `/api/krx/news/*`를 통해 읽습니다.
- `/api/news/*`는 뉴스 탭 화면용 요약 표면입니다.
- `/api/krx/news/*`는 feed, 검색, 상세, event API입니다.

### 3. 프런트 렌더링 모드
- `/krx/news`는 서버에서 첫 payload를 받아 바로 렌더링합니다.
- 이후 열린 탭에서는 60초마다 same-origin route를 폴링해 최신 상태를 다시 받아옵니다.

## 단계별 설명

### Step 1. raw ingestion
- `DART`, `MK_RSS`, `NAVER_NEWS`에서 원문을 가져옵니다.
- 저장 테이블:
  - `raw_document_fetch_runs`
  - `raw_document_sources`
  - `raw_documents`
  - `raw_document_dedup_keys`
- 이 단계에서는 "일단 저장"이 우선입니다.

### Step 2. 1차 triage
- 새 문서가 뉴스 탭에 올라갈 가치가 있는지 판단합니다.
- 저장 테이블:
  - `news_batch_triage`
- 방법:
  - 기본은 deterministic
  - 설정을 켜면 batch AI가 짧은 문서 묶음을 한 번에 판단

### Step 3. 후보 생성
- triage 결과와 공시/근거를 합쳐 화면 후보 카드를 만듭니다.
- 저장 테이블:
  - `market_surface_candidates`
- 이 테이블부터는 "화면에 보여줄 수 있는 카드" 형태가 됩니다.

### Step 4. 현재 표면 선택
- 각 표면(`KR`, `GLOBAL`, `DISCLOSURE`)에서 현재 대표 카드를 고릅니다.
- 저장 테이블:
  - `market_surface_state`
  - `market_surface_history`
- 같은 카드가 유지되더라도 explanation이 바뀌면 history에 `metadata_update`가 남습니다.

### Step 5. API 응답
- `/api/news/*`는 state와 candidate를 읽어 뉴스 탭 payload를 만듭니다.
- `/api/krx/news/*`는 더 넓은 feed/event 성격의 데이터를 제공합니다.

### Step 6. 프런트 SSR + polling
- `frontend/src/app/krx/news/page.tsx`가 SSR payload를 받습니다.
- `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`가 60초마다 `/api/krx/news-tab`을 폴링합니다.
- 실패하면 마지막 성공 payload를 유지합니다.

## 핵심 분리 원칙

### raw 저장소와 화면 표면은 다르다
- `raw_documents`는 입력 기록
- `market_surface_*`는 화면 read model

### event pipeline과 뉴스 탭 pipeline은 다르다
- `event_service.py`는 `/api/krx/news/events/*`를 위한 정규화 경로입니다.
- 뉴스 탭 메인 표면은 `news_batch_triage`와 `market_surface_*`를 중심으로 움직입니다.

### AI도 두 단계다
- 1차 AI:
  - 문서 묶음을 한 번에 triage
- 2차 AI:
  - 현재 표면과 상위 후보를 한 번에 compare

## 먼저 보면 좋은 파일
- `backend/src/krx/source_ingestion/cli.py`
- `backend/src/krx/source_ingestion/service.py`
- `backend/src/krx/news/service.py`
- `backend/src/krx/market_news/router.py`
- `frontend/src/app/krx/news/page.tsx`
- `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`

## 같이 읽을 다음 문서
- `06_database_tables.md`
- `02_backend_ingestion_automation.md`
