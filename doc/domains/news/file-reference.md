# File By File Reference

현재 코드 기준으로 뉴스 리빌드 관련 핵심 파일을 하나씩 설명하는 공부용 레퍼런스입니다.

## 읽는 법
- 각 항목은 "이 파일이 언제 실행되는가"부터 봅니다.
- 그 다음 입력, 출력, 핵심 책임, 같이 볼 파일 순서로 읽습니다.
- 모든 함수 설명을 적은 문서는 아니고, 파일 단위 책임을 이해하기 위한 레퍼런스입니다.

## `backend/src/krx/source_ingestion/cli.py`
- 정체:
  - 운영 배치와 수동 실행을 위한 CLI entrypoint
- 언제 실행되나:
  - cron이 `run-news-automation`을 호출할 때
  - 운영자가 수동 sync/normalize/refresh를 돌릴 때
- 핵심 책임:
  - 어떤 서비스를 어떤 순서로 호출할지 결정
  - cadence 판단 결과를 받아 due tick만 실행
- 주요 입력:
  - env
  - 현재 시각
  - CLI argument
- 주요 출력:
  - raw sync 실행
  - event normalize 실행
  - news materialization refresh 실행
- 같이 볼 파일:
  - `backend/src/krx/source_ingestion/schedule.py`
  - `backend/src/krx/source_ingestion/service.py`
  - `backend/src/krx/news/service.py`

## `backend/src/krx/source_ingestion/schedule.py`
- 정체:
  - 뉴스 automation cadence 계산기
- 언제 실행되나:
  - `run-news-automation` 내부
- 핵심 책임:
  - 장중/장후/비장중 phase 결정
  - 지금 실행해야 하는지(`should_run`) 계산
- 주요 입력:
  - timezone, open/close time, weekdays, holiday, interval
- 주요 출력:
  - `NewsAutomationCadenceDecision`
- 같이 볼 파일:
  - `backend/src/config/env.py`
  - `backend/src/krx/source_ingestion/cli.py`

## `backend/src/krx/source_ingestion/service.py`
- 정체:
  - raw document 적재 서비스
- 언제 실행되나:
  - sync 명령이 돌 때
- 핵심 책임:
  - provider adapter 호출
  - publisher/provider registry 보정
  - raw document upsert
  - dedup 및 fetch run 기록
- 주요 입력:
  - provider fetch 결과
  - source request
- 주요 출력:
  - `raw_documents`
  - `raw_document_fetch_runs`
  - `raw_document_sources`
- 같이 볼 파일:
  - `backend/src/krx/source_ingestion/providers/*.py`
  - `backend/src/krx/source_ingestion/models.py`
  - `backend/src/krx/provider_registry.py`

## `backend/src/krx/source_ingestion/event_service.py`
- 정체:
  - event API용 정규화 서비스
- 언제 실행되나:
  - normalize 명령
  - `/api/krx/news/events/*`
- 핵심 책임:
  - 문서에서 event 추출
  - review queue 생성
- 주요 입력:
  - `raw_documents`
- 주요 출력:
  - `events`
  - `event_company_edges`
  - `event_extractions`
  - `event_review_queue`
- 같이 볼 파일:
  - `backend/src/krx/source_ingestion/llm.py`
  - `backend/src/krx/news/router.py`
- 주의:
  - 뉴스 탭 메인 표면 서비스와 동일한 것이 아닙니다.

## `backend/src/krx/source_ingestion/providers/dart_provider.py`
- 정체:
  - DART 공시 adapter
- 핵심 책임:
  - DART API 응답을 `RawDocumentCandidate`로 바꾸기
- 특징:
  - 공식 공시
  - `DISCLOSURE`
  - canonical 이벤트 쪽에 더 가까움

## `backend/src/krx/source_ingestion/providers/mk_rss_provider.py`
- 정체:
  - 매일경제 RSS adapter
- 핵심 책임:
  - RSS XML을 파싱해 curated news candidate로 변환
- 특징:
  - persistent evidence 역할이 강함

## `backend/src/krx/source_ingestion/providers/naver_news_provider.py`
- 정체:
  - 네이버 뉴스 검색 adapter
- 핵심 책임:
  - 검색 결과를 discovery candidate로 변환
- 특징:
  - 탐지/보강 성격
  - canonical evidence와는 역할이 다름

## `backend/src/config/env.py`
- 정체:
  - 백엔드 전체 설정 모음
- 뉴스 리빌드에서 중요한 이유:
  - automation cadence
  - provider on/off
  - batch triage AI
  - compare AI
  - event pipeline LLM
  - datalab
  모두 여기서 읽습니다.
- 같이 볼 파일:
  - `backend/src/krx/news/factory.py`
  - `backend/src/krx/source_ingestion/factory.py`

## `backend/src/krx/news/factory.py`
- 정체:
  - 뉴스 가공용 의존성 조립기
- 언제 실행되나:
  - router에서 service를 만들 때
- 핵심 책임:
  - datalab provider 생성
  - batch triage provider 생성
  - editorial compare provider 생성
  - `NewsProductService` 생성
- 같이 볼 파일:
  - `backend/src/config/env.py`
  - `backend/src/krx/news/service.py`

## `backend/src/krx/news/batch_triage_ai.py`
- 정체:
  - 1차 AI provider
- 언제 실행되나:
  - refresh 중 누락 triage row나 legacy row를 업그레이드할 때
- 핵심 책임:
  - 문서 묶음을 1회 요청으로 보내고 triage 결과를 문서별로 돌려줌
- 주요 입력:
  - `NewsBatchTriageRequestItem[]`
- 주요 출력:
  - `raw_document_id -> NewsBatchTriageResponseItem`
- 같이 볼 파일:
  - `backend/src/krx/news/service.py`
- 공부 포인트:
  - 왜 per-document 호출이 아니라 batch 호출인지

## `backend/src/krx/news/editorial_ai.py`
- 정체:
  - 2차 compare AI provider
- 언제 실행되나:
  - top candidate를 현재 표면과 비교할 때
- 핵심 책임:
  - 현재 표면과 후보 묶음을 비교해 editorial override를 반환
- 주요 입력:
  - `NewsEditorialAICompareRequest`
- 주요 출력:
  - `cluster_key -> NewsEditorialAIResponse`
- 같이 볼 파일:
  - `backend/src/krx/news/service.py`

## `backend/src/krx/news/service.py`
- 정체:
  - 뉴스 리빌드의 핵심 서비스
- 언제 실행되나:
  - `/api/news/*`를 읽을 때
  - materialization refresh 때
- 핵심 책임:
  - recent raw docs 로드
  - triage row 관리
  - cluster/candidate/state/history 계산
  - dashboard/header/coverage/feed 데이터 제공
- 주요 입력:
  - `raw_documents`
  - `news_batch_triage`
  - optional datalab score
  - optional AI 결과
- 주요 출력:
  - `news_batch_triage`
  - `market_surface_candidates`
  - `market_surface_state`
  - `market_surface_history`
  - API read payload
- 같이 볼 파일:
  - `backend/tests/test_market_news_product.py`
  - `backend/src/krx/news/factory.py`
- 공부 포인트:
  - 이 파일이 사실상 뉴스 탭의 "도메인 서비스 + read model builder"라는 점

## `backend/src/krx/market_news/router.py`
- 정체:
  - 뉴스 탭 화면 전용 router
- 핵심 책임:
  - `/api/news/*` 계약 제공
- 특징:
  - router는 얇고, 대부분 서비스 위임만 함

## `backend/src/krx/news/router.py`
- 정체:
  - feed/detail/event router
- 핵심 책임:
  - `/api/krx/news/*` 제공
- 특징:
  - 같은 뉴스 router 안에 event API도 있음
  - 일부는 `NewsProductService`, 일부는 `EventNormalizationService` 사용

## `frontend/src/app/krx/news/page.tsx`
- 정체:
  - 뉴스 탭 SSR entry
- 핵심 책임:
  - active tab 계산
  - 초기 `NewsTabData` fetch
  - live dashboard 렌더 시작

## `frontend/src/app/api/krx/news-tab/route.ts`
- 정체:
  - 프런트 same-origin polling route
- 핵심 책임:
  - 브라우저가 60초마다 접근하는 no-store JSON endpoint 제공
- 특징:
  - 백엔드 주소를 브라우저가 직접 알지 않아도 됨

## `frontend/src/krx/server/data-service.ts`
- 정체:
  - KRX 공통 탭 데이터 조합 entry
- 뉴스에서 중요한 함수:
  - `getNewsTabData()`
- 핵심 책임:
  - dashboard payload를 받아 정렬/필터링한 뒤 `NewsTabData`로 반환

## `frontend/src/krx/news/server/data-service.ts`
- 정체:
  - 뉴스 탭 백엔드 응답 mapper
- 핵심 책임:
  - `/api/news/*` 응답을 프런트 도메인 타입으로 바꿈
- 공부 포인트:
  - 백엔드 snake_case와 프런트 camelCase의 경계

## `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`
- 정체:
  - client-side live state holder
- 핵심 책임:
  - polling
  - visibility resume
  - 마지막 성공 payload 유지
- 특징:
  - 화면 갱신 로직은 여기 있고, 시각 렌더링은 dashboard 컴포넌트가 맡음

## `frontend/src/krx/news/components/news-tab-dashboard.tsx`
- 정체:
  - 순수 렌더링 중심 컴포넌트
- 핵심 책임:
  - summary, card section, coverage UI를 그림
- 공부 포인트:
  - data fetch 로직보다 presentation 구조를 보는 파일

## `frontend/src/krx/types/domain.ts`
- 정체:
  - 프런트 최종 타입 정의
- 뉴스에서 중요한 타입:
  - `MarketNewsCard`
  - `MarketNewsCoverage`
  - `MarketNewsHeaderContext`
  - `NewsTabData`
- 공부 포인트:
  - 프런트 전체가 어떤 shape의 payload를 기대하는지 여기서 가장 잘 보임

## `backend/src/krx/company_master/migrations/016_market_surface_materialization.sql`
- 정체:
  - 뉴스 리빌드 핵심 테이블 정의 migration
- 핵심 책임:
  - `news_batch_triage`
  - `market_surface_candidates`
  - `market_surface_state`
  - `market_surface_history`
  테이블과 인덱스를 만듦
- 공부 포인트:
  - 서비스 코드를 볼 때 이 migration을 같이 보면 state/history 구조가 훨씬 빨리 이해됩니다.

## 같이 보면 좋은 테스트
- `backend/tests/test_market_news_product.py`
- `backend/tests/test_raw_document_ingestion.py`
- `backend/tests/test_api.py`
- `frontend/src/app/krx/news/page.test.tsx`
- `frontend/src/app/api/krx/news-tab/route.test.ts`
- `frontend/src/krx/news/components/news-tab-live-dashboard.test.tsx`

## 마지막 체크 질문
- 이 파일은 입력 저장소를 만드나, 화면 read model을 만드나?
- 이 파일은 batch orchestration인가, 실제 도메인 계산기인가?
- 이 파일은 backend boundary인가, frontend boundary인가?
- 이 파일이 읽는 source-of-truth는 무엇인가?
