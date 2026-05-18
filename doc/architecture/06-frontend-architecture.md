# 프론트엔드 구조

## 역할

frontend는 backend API 계약을 받아 사용자가 빠르게 시장 상태를 읽을 수 있게 보여주는 계층입니다.

frontend는 시장 판단을 새로 계산하지 않습니다. 이미 backend에서 구조화한 계약을 검증하고 렌더링합니다.

## 주요 파일

```text
frontend/src/app/argus/page.tsx
frontend/src/app/argus/derivatives/page.tsx
frontend/src/app/argus/reaction/page.tsx
frontend/src/app/argus/triggers/page.tsx
frontend/src/app/argus/triggers/news/page.tsx
frontend/src/argus_v2/components/dashboard.tsx
frontend/src/argus_v2/contracts/dashboard.ts
frontend/src/argus_v2/server/dashboard.ts
frontend/src/argus_v2/lib/env.ts
```

## Route 구조

Next.js App Router를 사용합니다.

```text
/argus
-> frontend/src/app/argus/page.tsx

/argus/derivatives
-> frontend/src/app/argus/derivatives/page.tsx

/argus/reaction
-> frontend/src/app/argus/reaction/page.tsx

/argus/triggers
-> frontend/src/app/argus/triggers/page.tsx

/argus/triggers/news
-> frontend/src/app/argus/triggers/news/page.tsx
```

각 route는 server component로 backend 데이터를 가져온 뒤 공통 UI component에 전달합니다.

## 데이터 호출

파일:

```text
frontend/src/argus_v2/server/dashboard.ts
```

함수:

```text
getArgusV2Dashboard()
getArgusV2NewsFeed()
```

`getArgusV2Dashboard()`는 `/api/argus/v2/dashboard`를 호출합니다.

`getArgusV2NewsFeed()`는 `/api/argus/v2/news-feed`를 호출합니다.

두 함수 모두 `cache: "no-store"`를 사용합니다. 시장 데이터는 최신성이 중요하기 때문입니다.

## 환경 변수

파일:

```text
frontend/src/argus_v2/lib/env.ts
```

주요 값:

```text
BACKEND_BASE_URL=http://localhost:4000
```

frontend는 이 base URL로 backend API를 호출합니다.

## 계약 검증

파일:

```text
frontend/src/argus_v2/contracts/dashboard.ts
```

역할:

- backend 응답을 Zod schema로 검증
- TypeScript type 생성
- 테스트 fixture와 실제 API 계약 일치 유지

주요 schema:

- `marketDashboardSchema`
- `newsFeedResponseSchema`

## 공통 shell

파일:

```text
frontend/src/argus_v2/components/dashboard.tsx
```

`ArgusShell`은 모든 Argus 화면의 공통 frame입니다.

포함 요소:

- 최상단 판단 label
- confidence badge
- as_of
- 상단 tab nav
- primary driver
- children 영역
- provider health section

이 구조 덕분에 상세 화면도 첫 화면과 같은 맥락 안에서 움직입니다.

## 상단 탭

상단 탭은 `ARGUS_TABS`로 정의합니다.

```text
시장 판단 -> /argus
옵션·선물 -> /argus/derivatives
현물 반응 -> /argus/reaction
뉴스 분석 -> /argus/triggers
```

상단 탭은 product scope를 강하게 제한합니다.

MVP에 없는 것:

- AI 전용 탭
- 관심종목 탭
- 일반 뉴스 앱형 독립 탭

AI는 각 화면 안의 해석 레이어입니다.

## 뉴스 분석 내부 탭

뉴스 분석 화면에는 내부 탭이 있습니다.

```text
메인 -> /argus/triggers
뉴스 -> /argus/triggers/news
```

`메인`은 기존 뉴스/매크로 trigger 화면입니다.

`뉴스`는 원천 뉴스 feed 화면입니다.

## 주요 화면 component

### `ArgusV2Dashboard`

route:

```text
/argus
```

역할:

- 시장 판단 첫 화면
- 결론, 핵심 수급, 대표 trigger, 강/약 섹터를 압축 표시

### `ArgusV2DerivativesView`

route:

```text
/argus/derivatives
```

역할:

- 옵션·선물 상세
- KOSPI200 선물, PCR, OI 변화, basis, 주요 옵션 level 표시

### `ArgusV2ReactionView`

route:

```text
/argus/reaction
```

역할:

- 현물 반응 상세
- KOSPI/KOSDAQ, 상승/하락 종목 수, 현물 투자자 수급, 섹터 강약 표시

### `ArgusV2TriggersView`

route:

```text
/argus/triggers
```

역할:

- 뉴스 분석 메인
- AI 판단을 거친 시장 연결 trigger 표시
- AI reason, confidence, affected factors 표시

### `ArgusV2NewsFeedView`

route:

```text
/argus/triggers/news
```

역할:

- 원천 뉴스 feed 표시
- title, summary, source, published_at, source_url 표시
- 원문 링크 제공

## Empty state

Argus는 데이터가 없을 때 조용히 숨기지 않습니다.

사용하는 component:

```text
EmptyNote
```

예:

- 대표 뉴스 없음
- 옵션 레벨 미수신
- 섹터 반응 미연결
- 실시간 뉴스 없음
- 뉴스 수신 오류

## 색상 규칙

한국 시장 관례를 따릅니다.

- 상승/긍정: red 계열
- 하락/부정: blue 계열
- 중립/미수신: neutral

관련 함수:

```text
toneClass()
pointTone()
optionPressureTone()
```

## 접근성과 상태

현재 구조에서 지키는 것:

- 상단 탭은 `nav`와 `aria-label` 사용
- 현재 페이지는 `aria-current="page"` 사용
- 기사 원문 링크는 `target="_blank"`와 `rel="noreferrer"` 사용
- 데이터 수신 상태를 text로 표시

## 테스트

파일:

```text
frontend/src/app/argus/page.test.tsx
```

검증 내용:

- 상단 탭 shell 렌더링
- 빈 상태 표시
- 뉴스 분석 feed subtab 렌더링
- 원문 링크 표시

## 변경 시 체크리스트

화면이나 계약을 바꿀 때:

1. backend Pydantic contract 확인
2. frontend Zod schema 수정
3. route page 수정
4. `dashboard.tsx` component 수정
5. test fixture 수정
6. `pnpm --filter frontend test`
7. `pnpm --filter frontend lint`
8. `pnpm --filter frontend build`
