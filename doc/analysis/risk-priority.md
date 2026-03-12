# Risk Priority

현재 코드와 테스트 구조를 기준으로, 문제 발생 가능성과 파급 범위를 함께 본 우선순위 정리입니다.

## 우선순위 기준
- 사용자 영향 범위가 넓은가
- DB나 외부 연동을 건드리는가
- 설정 토글이 많은가
- 한 파일 또는 한 서비스에 책임이 과도하게 몰려 있는가
- 실패가 빈 화면 대신 fallback으로 조용히 숨겨질 수 있는가

## 1. 최우선 점검: `source_ingestion` + `company_master` + 마이그레이션
- 주요 파일: `backend/src/krx/source_ingestion/router.py`, `backend/src/krx/source_ingestion/service.py`, `backend/src/krx/company_master/`, `backend/src/krx/company_master/migrations/`
- 이유: 관리자 API, 외부 공급자, DB 쓰기, 파이프라인 배치가 한 덩어리로 묶여 있습니다.
- 근거: `source_ingestion/router.py`는 600줄대, `source_ingestion/service.py`는 1200줄대입니다.
- 흔한 실패 형태: 동기화는 성공처럼 보이지만 데이터가 비어 있음, 관리자 키 누락, 마이그레이션 누락, 특정 공급자만 실패
- 먼저 볼 테스트: `backend/tests/test_event_pipeline.py`, `backend/tests/test_raw_document_ingestion.py`, `backend/tests/test_company_master_pipeline.py`, `backend/tests/test_company_report_pipeline.py`

## 2. 높은 우선순위: 프런트와 백엔드의 데이터 계약 경계
- 주요 파일: `frontend/src/krx/server/data-service.ts`, `frontend/src/krx/server/client.ts`, `frontend/src/krx/*/server/data-service.ts`, `backend/src/main.py`, `backend/src/krx/router.py`
- 이유: 프런트가 여러 API 응답을 합쳐 렌더링하고 일부 실패는 빈 데이터 fallback으로 삼켜집니다.
- 흔한 실패 형태: 페이지는 열리는데 내용이 비어 있음, 특정 탭만 비정상, 응답 필드명이 바뀌어 조용히 누락
- 먼저 볼 테스트: `frontend/src/app/krx/layout.test.tsx`, `frontend/src/app/krx/page.test.tsx`, `frontend/src/app/krx/news/page.test.tsx`, `frontend/src/app/krx/global-events/page.test.tsx`, `backend/tests/test_api.py`

## 3. 높은 우선순위: 공통 KRX 레이아웃과 헤더 경로
- 주요 파일: `frontend/src/app/krx/layout.tsx`, `frontend/src/krx/server/data-service.ts`, `backend/src/krx/app_header/router.py`
- 이유: `layout.tsx`가 모든 KRX 하위 페이지보다 먼저 실행되며 검색 인덱스와 헤더를 동시에 불러옵니다.
- 흔한 실패 형태: `/krx` 하위 전체가 느려짐, 상단 헤더만 깨짐, 검색이 동작하지 않음, 전체 페이지가 공통적으로 빈약해짐
- 먼저 볼 테스트: `frontend/src/app/krx/layout.test.tsx`, `backend/tests/test_api.py`

## 4. 높은 우선순위: 뉴스 표면이 둘로 나뉜 구조
- 주요 파일: `backend/src/krx/market_news/router.py`, `backend/src/krx/news/router.py`, `frontend/src/krx/news/server/data-service.ts`, `frontend/src/krx/server/data-service.ts`
- 이유: 프런트 뉴스 탭은 `/api/news/*`를 주로 쓰고, 검색과 종목별 조회는 `/api/krx/news/*`를 함께 씁니다.
- 흔한 실패 형태: 뉴스 탭과 검색 결과가 서로 다른 데이터를 보여줌, 카드형 뉴스와 상세 조회가 다른 규칙을 따름, mock 데이터와 상품화 데이터가 섞임
- 먼저 볼 테스트: `frontend/src/app/krx/news/page.test.tsx`, `backend/tests/test_market_news_product.py`, `backend/tests/test_api.py`

## 5. 중간 우선순위: 설정과 환경 변수 드리프트
- 주요 파일: `backend/src/config/env.py`, `frontend/src/krx/lib/env.ts`, `.env.example`, `backend/.env`
- 이유: 기능 토글, API 키, DB 경로, 관리자 키, 외부 공급자 옵션이 한 곳에 모여 있습니다.
- 흔한 실패 형태: 로컬에서는 되는데 CI나 운영에서 안 됨, 일부 기능만 비활성화, 외부 공급자만 실패, admin 경로만 401
- 먼저 볼 테스트: `backend/tests/test_api.py`

## 6. 중간 우선순위: 시장 신호와 글로벌 이벤트 대형 서비스
- 주요 파일: `backend/src/krx/market_signal/service.py`, `backend/src/krx/global_events/service.py`, `backend/src/krx/news/service.py`
- 이유: 각 서비스가 1000줄 이상으로 크고, 계산 로직과 데이터 조합 책임이 큽니다.
- 흔한 실패 형태: 커버리지 계산 불일치, 날짜 기준 오작동, 규칙 기반 해석과 LLM 기반 해석 차이, 일부 카드만 깨짐
- 먼저 볼 테스트: `backend/tests/test_krx_market_signal_api.py`, `backend/tests/test_global_events.py`, `backend/tests/test_market_news_product.py`

## 7. 보조 우선순위: 문서와 검증 스크립트의 신뢰도
- 주요 파일: `doc/PROJECT_STRUCTURE.md`, `scripts/check-market-boundaries.sh`
- 이유: 구조 문서가 코드보다 뒤처지면 잘못된 전제를 만들고, boundary check 스크립트는 현재 실질 검증을 하지 않습니다.
- 흔한 실패 형태: 잘못된 파일을 수정함, 리뷰 범위를 잘못 잡음, lint가 통과해도 아키텍처 규칙 위반을 놓침
- 먼저 할 일: 실제 구조 문서 최신화, 경계 스크립트 강화 필요 여부 판단

## 디버깅 시작 순서
1. 문제가 공통 레이아웃인지 특정 탭인지 먼저 분리한다.
2. 프런트가 호출하는 API 경로가 `/api/news`, `/api/global-events`, `/api/app/header`, `/api/krx/*` 중 어디인지 확인한다.
3. 환경 변수와 `BACKEND_BASE_URL`, `db_path`, 관리자 키, provider 토글을 확인한다.
4. 데이터가 비어 있으면 공개 API 문제인지 ingestion 파이프라인 문제인지 나눈다.
5. 관련 테스트를 좁게 실행한 뒤, 필요할 때만 전체 `pnpm test`로 확장한다.
