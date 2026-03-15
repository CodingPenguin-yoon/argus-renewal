# Backend API Layers

현재 코드 기준으로 뉴스 관련 백엔드 API 레이어를 공부하기 위한 문서입니다.

## 이 문서의 목적
- `/api/news/*`와 `/api/krx/news/*`가 왜 둘 다 있는지 설명합니다.
- route 파일이 직접 계산하는지, 서비스에 위임하는지 설명합니다.
- 어떤 API가 뉴스 탭 화면용이고 어떤 API가 확장용인지 구분합니다.

## 파일 범위
- `backend/src/krx/market_news/router.py`
- `backend/src/krx/news/router.py`
- `backend/src/main.py`
- 간접적으로 `backend/src/krx/news/service.py`
- 간접적으로 `backend/src/krx/source_ingestion/event_service.py`

## 1. `/api/news/*`: 뉴스 탭 전용 표면 API

### 파일
- `backend/src/krx/market_news/router.py`

### 이 파일의 성격
- 매우 얇은 router입니다.
- 요청을 받으면 매번 `create_news_product_service(get_settings())`로 서비스를 만들고,
- 필요한 읽기 메서드만 호출합니다.

### 제공 endpoint
- `GET /api/news/dashboard`
- `GET /api/news/kr`
- `GET /api/news/global`
- `GET /api/news/disclosures`
- `GET /api/news/header-context`
- `GET /api/news/coverage`

### 언제 쓰나
- `/krx/news` 페이지의 메인 데이터 공급원입니다.
- 프런트 polling route도 최종적으로 이 경로를 다시 칩니다.

### 반환 데이터 성격
- 화면 전용 요약 payload
- 이미 materialize된 카드와 coverage 정보

## 2. `/api/krx/news/*`: feed/detail/event API

### 파일
- `backend/src/krx/news/router.py`

### 이 파일의 성격
- 뉴스 관련 API를 더 넓게 묶은 router입니다.
- 탭 전용 표면뿐 아니라 feed, 검색, 상세, 이벤트 API까지 같이 제공합니다.

### feed 계열 endpoint
- `GET /api/krx/news`
- `GET /api/krx/news/top`
- `GET /api/krx/news/macro`
- `GET /api/krx/news/stock`
- `GET /api/krx/news/by-ticker/{ticker}`
- `GET /api/krx/news/search`
- `GET /api/krx/news/{news_id}`

### event 계열 endpoint
- `GET /api/krx/news/events/recent`
- `GET /api/krx/news/events/company/{company_id}`

### 중요한 차이
- feed/detail/search는 `NewsProductService`
- events 계열은 `EventNormalizationService`

즉 같은 router 파일 안에 있지만 내부 서비스는 다를 수 있습니다.

## 3. FastAPI mount: `main.py`

### 역할
- 앱 전체 router를 mount합니다.
- 이 단계에서 `/api/news`와 `/api/krx`가 같은 앱에 붙습니다.

### 공부 포인트
- `/api/news/*`가 `/api/krx/news/*`의 하위가 아니라 별도 루트라는 점을 꼭 기억해야 합니다.

## 4. 왜 API를 둘로 나눴나

### `/api/news/*`
- 화면 전용
- payload가 명확하고 작음
- `/krx/news`에 바로 쓰기 쉬움

### `/api/krx/news/*`
- 확장 API
- feed, 검색, 상세, 회사별 조회, event API 같은 범용성
- 다른 화면이나 기능에서 재사용하기 쉬움

## 5. 실제 호출 관계

### 뉴스 탭 페이지
```text
frontend/src/app/krx/news/page.tsx
-> getNewsTabData()
-> getMarketNewsDashboard()
-> GET /api/news/dashboard
```

### polling
```text
browser
-> GET /api/krx/news-tab
-> getNewsTabData()
-> GET /api/news/dashboard
```

### event API
```text
client
-> GET /api/krx/news/events/recent
-> EventNormalizationService.list_recent_events()
```

## 6. route 파일을 읽을 때 보는 법
- router 파일 자체는 복잡한 비즈니스 로직이 적습니다.
- 이 파일에서 봐야 할 것은 세 가지입니다.
  - URL 계약
  - query parameter
  - 실제로 어떤 service 메서드로 위임하는지

## 7. 디버깅할 때의 기준

### `/krx/news` 화면이 이상할 때
- 먼저 `backend/src/krx/market_news/router.py`
- 그 다음 `backend/src/krx/news/service.py`

### `/api/krx/news/events/*`가 이상할 때
- 먼저 `backend/src/krx/news/router.py`
- 그 다음 `backend/src/krx/source_ingestion/event_service.py`

### 같은 "뉴스"인데 결과가 다를 때
- 둘이 같은 API가 아니라는 점부터 확인해야 합니다.

## 8. 관련 테스트
- `backend/tests/test_api.py`
- `backend/tests/test_market_news_product.py`
- `backend/tests/test_event_pipeline.py`

## 다음 문서
- `05_frontend_news_tab.md`
- `07_file_by_file_reference.md`
