# KRX MVP IA Runbook

## 목적
KRX MVP는 상단 GNB를 아래 5개로 고정합니다.

1. 대시보드 (`/krx/dashboard`)
2. AI 인사이트 (`/krx/insights`)
3. 파생·수급 (`/krx`, canonical route 유지)
4. 시장 뉴스 (`/krx/news`)
5. 매크로 캘린더 (`/krx/macro-calendar`)

`관심종목`은 보조 진입점입니다. 공통 헤더는 compact status 역할만 수행하고, 메인 해석 카드인 `오늘의 시장 톤`은 `AI 인사이트`에서 중심 콘텐츠로 제공합니다.

## canonical 경로와 호환 경로
- canonical:
  - `/krx/dashboard`
  - `/krx/insights`
  - `/krx`
  - `/krx/news`
  - `/krx/macro-calendar`
- 호환 redirect:
  - `/krx/overview` -> `/krx/dashboard`
  - `/krx/macro` -> `/krx/insights`
  - `/krx/global-events` -> `/krx/macro-calendar`

## 탭 구조

### 1) 대시보드 (`/krx/dashboard`)
- 지금 뭐가 중요한지 먼저 답하는 60초 cockpit
- 핵심 테이크어웨이 3개
- 거시 미니 위젯 3개
- 경고 포인트 1개
- 파생·수급/시장 뉴스/매크로 캘린더 게이트웨이

### 2) AI 인사이트 (`/krx/insights`)
- 오늘의 시장 톤
- 해석 근거 포인트
- 반대 근거
- 시장 심리 / 변동성 온도 / AI 확신도 게이지
- 파생 기준점
- 해석이 바뀌는 조건
- 오늘 확인 포인트
- 보조 참고 카드

### 3) 파생·수급 (`/krx`)
- 누가 어떤 방향으로 베팅하고 있나를 답하는 포지셔닝 surface
- 종합
- 자금 흐름
- 파생상품
- 체크포인트

딥링크:
- 종합: `GET /krx`
- 자금 흐름: `GET /krx?subtab=fund-flow`
- 파생상품: `GET /krx?subtab=derivatives`
- 체크포인트: `GET /krx?subtab=checkpoints`

### 4) 시장 뉴스 (`/krx/news`)
- 종합
- 한국 증시
- 글로벌 증시
- 공시

딥링크:
- 종합: `GET /krx/news`
- 한국 증시: `GET /krx/news?tab=kr`
- 글로벌 증시: `GET /krx/news?tab=global`
- 공시: `GET /krx/news?tab=disclosures`

### 5) 매크로 캘린더 (`/krx/macro-calendar`)
- 종합
- 핵심 이벤트
- 다음 24시간
- 이번 주
- 실적(데이터 존재 시에만 노출)

딥링크:
- 종합: `GET /krx/macro-calendar`
- 핵심 이벤트: `GET /krx/macro-calendar?tab=highlights`
- 다음 24시간: `GET /krx/macro-calendar?tab=next-24h`
- 이번 주: `GET /krx/macro-calendar?tab=week`
- 실적: `GET /krx/macro-calendar?tab=earnings`

## 핵심 규칙
- `홈/세부` 같은 추상 탭은 주 흐름에서 제거합니다.
- `시장 뉴스`는 동적 유지와 60초 폴링을 유지합니다.
- `대시보드`, `AI 인사이트`, 안정 탭은 selective prefetch 대상입니다.
- `파생`은 상위 탭이 아니라 `/krx` 내부 탭입니다.
- `매크로 캘린더`는 raw feed가 아니라 한국 증시 관점의 catalyst view입니다.

## 로컬 검증
1. 백엔드 실행
```bash
pnpm dev:backend
```
2. 프론트 실행
```bash
pnpm dev:frontend
```
3. 브라우저 확인
- `http://localhost:3000/krx/dashboard`
- `http://localhost:3000/krx/insights`
- `http://localhost:3000/krx`
- `http://localhost:3000/krx/news?tab=disclosures`
- `http://localhost:3000/krx/macro-calendar?tab=next-24h`
4. 테스트
```bash
pnpm --filter frontend test
cd backend && pytest -q
```

## 관련 문서
- `system-map.md`
- `project-structure.md`
- `../troubleshooting/navigation-and-ia.md`
