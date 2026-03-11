# KRX MVP IA Runbook

## 목적
KRX MVP는 상단 GNB를 아래 3개로 고정합니다.

1. 시장 신호 (`/krx`)
2. 뉴스 (`/krx/news`)
3. 글로벌 이벤트 (`/krx/global-events`)

`관심종목`은 보조 진입점이며, `홈/세부` 같은 추상 탭은 사용자 주 흐름에서 제거합니다.

## 홈/세부 제거 이유
- `홈 > 세부 > 실제 목적 탭` 구조는 클릭 깊이가 불필요하게 늘어납니다.
- 사용자는 바로 목적 탭(파생상품, 공시, 핵심 이벤트 등)으로 이동해야 합니다.
- `종합` 탭을 각 섹션의 개요 탭으로 고정해 일관성을 유지합니다.

## 탭 구조
### 1) 시장 신호 (`/krx`)
- 종합
- 자금 흐름
- 파생상품
- 체크포인트

규칙:
- 파생상품은 `시장 신호` 내부 탭으로 고정합니다.
- `/krx/derivatives` 레거시 경로는 호환 리다이렉트만 유지합니다.

딥링크:
- 종합: `GET /krx`
- 자금 흐름: `GET /krx?subtab=fund-flow`
- 파생상품: `GET /krx?subtab=derivatives`
- 체크포인트: `GET /krx?subtab=checkpoints`

### 2) 뉴스 (`/krx/news`)
- 종합
- 한국 증시
- 글로벌 증시
- 공시

규칙:
- 뉴스는 이벤트 카드 중심 UX를 유지합니다.
- 공시는 독립 상위 GNB가 아니라 `뉴스` 내부 탭으로 제공합니다.

딥링크:
- 종합: `GET /krx/news`
- 한국 증시: `GET /krx/news?tab=kr`
- 글로벌 증시: `GET /krx/news?tab=global`
- 공시: `GET /krx/news?tab=disclosures`

### 3) 글로벌 이벤트 (`/krx/global-events`)
- 종합
- 핵심 이벤트
- 다음 24시간
- 이번 주
- 실적(데이터 존재 시에만 노출)

규칙:
- 실적 데이터가 없으면 실적 탭을 숨기거나 비활성 상태로 처리합니다(현재 구현: 숨김).

딥링크:
- 종합: `GET /krx/global-events`
- 핵심 이벤트: `GET /krx/global-events?tab=highlights`
- 다음 24시간: `GET /krx/global-events?tab=next-24h`
- 이번 주: `GET /krx/global-events?tab=week`
- 실적: `GET /krx/global-events?tab=earnings` (데이터가 있을 때만 유효)

## 데이터 소스/서비스
### 시장 신호
- 백엔드: `backend/src/krx/market_signal/service.py`, `backend/src/krx/derivatives/service.py`
- 프론트:
  - 탭 셸: `frontend/src/krx/components/market-signal/market-signal-dashboard.tsx`
  - 서브탭 규칙: `frontend/src/krx/market-signal/lib/subtabs.ts`

### 뉴스
- 백엔드: `backend/src/krx/news/service.py`, `backend/src/krx/market_news/router.py`
- 프론트:
  - 탭 셸: `frontend/src/krx/components/news/news-tab-dashboard.tsx`
  - 탭 규칙: `frontend/src/krx/news/lib/tabs.ts`

### 글로벌 이벤트
- 백엔드: `backend/src/krx/global_events/service.py`, `backend/src/krx/global_events/router.py`
- 프론트:
  - 탭 셸: `frontend/src/krx/components/events/global-events-dashboard.tsx`
  - 탭 규칙: `frontend/src/krx/global-events/lib/tabs.ts`

## Empty state 가이드
- 사용자 표면에는 운영자/관리자 지시 문구를 노출하지 않습니다.
- 예시:
  - "아직 동기화된 데이터가 없습니다."
  - "최신 데이터가 준비되면 이 영역에 표시됩니다."
  - "현재 표시 가능한 이벤트가 없습니다."

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
- `http://localhost:3000/krx`
- `http://localhost:3000/krx?subtab=derivatives`
- `http://localhost:3000/krx/news?tab=disclosures`
- `http://localhost:3000/krx/global-events?tab=next-24h`
4. 테스트
```bash
pnpm --filter frontend test
cd backend && pytest -q
```
