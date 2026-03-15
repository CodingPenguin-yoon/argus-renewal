# Frontend News Tab

현재 코드 기준으로 `/krx/news` 프런트 경로를 공부하기 위한 문서입니다.

## 이 문서의 범위
- `frontend/src/app/krx/news/page.tsx`
- `frontend/src/app/api/krx/news-tab/route.ts`
- `frontend/src/krx/server/data-service.ts`
- `frontend/src/krx/news/server/data-service.ts`
- `frontend/src/krx/news/components/news-tab-live-dashboard.tsx`
- `frontend/src/krx/news/components/news-tab-dashboard.tsx`
- `frontend/src/krx/types/domain.ts`

## 1. 페이지 entry: `page.tsx`

### 역할
- `/krx/news`의 서버 컴포넌트 entry입니다.
- SSR 시점에 초기 데이터를 가져와 live dashboard로 넘깁니다.

### 하는 일
1. query string에서 탭을 읽음
2. `normalizeNewsTab()`으로 active tab 결정
3. `getNewsTabData()` 호출
4. `NewsTabLiveDashboard`에 초기 payload 전달

### 중요한 점
- 이 파일은 polling을 직접 하지 않습니다.
- 첫 화면 데이터를 안정적으로 받는 SSR entry 역할입니다.

## 2. same-origin polling route: `route.ts`

### 역할
- 브라우저가 60초마다 접근하는 프런트 내부 JSON route입니다.

### 왜 필요한가
- 브라우저가 백엔드 URL을 직접 알 필요가 없게 합니다.
- 같은 origin에서 `no-store` JSON만 받아오면 되므로 단순합니다.
- 프런트 내부 fetch 경로가 고정됩니다.

### 하는 일
- `getNewsTabData()`를 다시 호출
- 결과를 `Cache-Control: no-store`로 반환

## 3. 탭 데이터 조합 entry: `frontend/src/krx/server/data-service.ts`

### 역할
- KRX 여러 탭의 데이터 조합 entry입니다.
- 뉴스 탭에서는 `getNewsTabData()`가 핵심입니다.

### `getNewsTabData()`가 하는 일
1. `getMarketNewsDashboard()` 호출
2. KR 탭용 누적 카드 확보를 위해 `getMarketNewsCards("kr", 50)`를 추가 호출
3. KR/GLOBAL 카드에서 MVP scope 필터 적용
4. `종합`은 dashboard payload에 포함된 `briefing`을 그대로 사용
5. `글로벌`은 ranking score 기준 정렬 유지
6. `한국 증시` 탭은 KR 누적 카드를 최신 시각 기준으로 다시 정렬
7. disclosure 카드 상한 적용
8. 최종 `NewsTabData` 반환

### 실패 시 처리
- 콘솔에 에러를 찍고
- 빈 카드와 empty briefing/coverage/header context를 반환합니다.

## 4. 뉴스 전용 mapper: `frontend/src/krx/news/server/data-service.ts`

### 역할
- `/api/news/*` 응답을 프런트 타입으로 정규화합니다.

### 이 파일에서 중요한 것
- API payload 타입 정의(`ApiMarketNewsCard`, `ApiMarketNewsCoverage`, `ApiMarketNewsBriefing` 등)
- mapper 함수
  - `mapMarketNewsCard`
  - `mapMarketNewsCoverage`
  - `mapMarketNewsHeaderContext`
  - `mapMarketNewsBriefing`
- 최종 fetch 함수
  - `getMarketNewsDashboard`
  - `getMarketNewsCards`
  - `getMarketNewsCoverage`
  - `getMarketNewsHeaderContext`

### 공부 포인트
- 백엔드 snake_case를 프런트 camelCase로 바꾸는 지점입니다.
- 도메인 타입 경계가 어디인지 이해하기 좋습니다.

## 5. polling 상태 보유: `news-tab-live-dashboard.tsx`

### 역할
- 클라이언트 컴포넌트입니다.
- 초기 SSR payload를 받아 내부 state로 들고 있고, 60초마다 최신 payload로 교체합니다.

### 동작 순서
1. `initialData`로 state 초기화
2. `setInterval`로 60초마다 fetch
3. `document.visibilityState`가 `hidden`이면 요청 생략
4. 탭이 다시 보이면 즉시 한 번 갱신
5. 실패하면 현재 state 유지
6. KR 탭 페이지 상태를 들고 있다가 탭 전환 시 첫 페이지로 리셋
7. polling 후 KR 카드 수가 줄면 현재 페이지를 마지막 유효 페이지로 보정

### 중요한 상수
- `NEWS_TAB_POLL_INTERVAL_MS = 60_000`
- `NEWS_TAB_POLL_PATH = "/api/krx/news-tab"`

### 왜 이 파일이 필요한가
- 서버 컴포넌트만으로는 열린 탭이 자동 갱신되지 않습니다.
- polling 상태는 브라우저에서만 유지해야 하므로 client component가 필요합니다.
- KR 탭의 5개 단위 페이지네이션도 브라우저 상태로 관리하는 편이 단순합니다.

## 6. 순수 렌더링: `news-tab-dashboard.tsx`

### 역할
- 실제 카드 UI를 렌더링합니다.
- 데이터 갱신은 하지 않고, props를 받아 그립니다.

### 이 파일을 읽을 때 볼 포인트
- summary 브리핑 영역
- KR/GLOBAL/DISCLOSURE 섹션 배치
- KR 탭 시간순 누적 렌더링과 5개 단위 이전/다음 버튼
- coverage 표시
- 카드별 시각화 방식

### 중요한 점
- 로직보다 presentation이 많은 파일입니다.
- `종합`은 대표 카드 1개 대신 `briefing.headline + summary + keyPoints + linkedHeadlines`를 다문단 서술형 리포트 흐름으로 렌더링합니다.
- 데이터 shape를 이해하려면 `NewsTabData` 타입을 같이 봐야 합니다.

## 7. 타입 경계: `domain.ts`

### 역할
- 프런트에서 쓰는 최종 도메인 타입을 정의합니다.

### 뉴스 탭에서 중요한 타입
- `MarketNewsCard`
- `MarketNewsEvidence`
- `MarketNewsBriefing`
- `MarketNewsCoverage`
- `MarketNewsHeaderContext`
- `NewsTabData`

### 공부 포인트
- 프런트는 이 타입을 기준으로 움직입니다.
- 따라서 백엔드 응답이 바뀌면 mapper와 이 타입부터 같이 봐야 합니다.

## 8. 전체 흐름 다시 보기
```text
SSR
-> page.tsx
-> getNewsTabData()
-> getMarketNewsDashboard()
-> /api/news/dashboard

client polling
-> news-tab-live-dashboard.tsx
-> /api/krx/news-tab
-> getNewsTabData()
-> /api/news/dashboard + /api/news/kr?limit=50
```

## 9. 자주 헷갈리는 점
- `/api/krx/news-tab`은 백엔드 API가 아니라 프런트 route입니다.
- `page.tsx`는 SSR entry이고, live update는 `news-tab-live-dashboard.tsx`가 담당합니다.
- `news-tab-dashboard.tsx`는 data fetch보다 rendering 책임이 큽니다.

## 10. 관련 테스트
- `frontend/src/app/krx/news/page.test.tsx`
- `frontend/src/app/api/krx/news-tab/route.test.ts`
- `frontend/src/krx/news/components/news-tab-live-dashboard.test.tsx`

## 다음 문서
- `06_database_tables.md`
- `07_file_by_file_reference.md`
