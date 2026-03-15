# KRX Prefetch Measurement

상단 GNB prefetch 정책의 실제 효과를 확인하기 위한 수동 측정 체크리스트입니다.

## 목적
- 안정 탭 prefetch가 클릭 전에 실제 요청을 발생시키는지 확인합니다.
- `시장 뉴스`가 prefetch 제외 정책대로 동작하는지 확인합니다.
- 전환 체감 개선을 설명할 수 있는 최소 증거를 확보합니다.

## 사전 조건
- production 모드에서 확인해야 합니다. 개발 모드에서는 Next.js prefetch 동작이 다릅니다.
- build가 성공한 상태여야 합니다.
- 측정 대상 정책:
  - `대시보드`, `AI 인사이트`, `시장 신호`, `매크로 캘린더`: prefetch 적극 적용
  - `시장 뉴스`: prefetch 제외

## 실행 절차
1. `pnpm --filter frontend build`
2. `pnpm --filter frontend start`
3. 브라우저에서 `/krx/dashboard`를 엽니다.
4. DevTools `Network` 탭을 열고 `Preserve log`를 켭니다.
5. 페이지를 새로고침한 뒤 2~3초 정도 idle 상태로 둡니다.
6. `rsc`, `prefetch`, `krx`, `insights`, `macro-calendar`, `news` 키워드로 요청을 확인합니다.
7. `AI 인사이트`, `시장 신호`, `매크로 캘린더`, `시장 뉴스`를 순서대로 클릭하면서 요청 수와 응답 시점을 비교합니다.

## 기대 결과
- 클릭 전에 `/krx/insights`, `/krx`, `/krx/macro-calendar` 관련 route payload 또는 RSC 요청이 먼저 보이면 prefetch wiring은 정상입니다.
- `/krx/news` 관련 prefetch 요청은 idle 상태에서 보이지 않아야 합니다.
- 이미 prefetch된 안정 탭은 클릭 시 route bootstrap 요청이 줄거나 전환이 더 짧아야 합니다.
- `/krx/news`는 클릭 시점에만 route 요청이 발생해도 정상입니다.

## 현재 측정 요약
- `/krx/dashboard` 최초 진입 시 `/krx`, `/krx/insights`, `/krx/macro-calendar` prefetch 확인
- `/krx/news` prefetch는 확인되지 않음
- 같은 세션에서 `AI 인사이트` 클릭 후 추가 리소스는 0건
- `시장 뉴스` 클릭 후 뉴스 RSC와 탭별 리소스가 새로 요청됨

## 현재 코드 기준 참고
- GNB prefetch 설정: `frontend/src/krx/components/layout/top-nav.tsx`
- build 출력 기준 revalidate route:
  - `/krx/dashboard`
  - `/krx/insights`
  - `/krx/derivatives`
- 동적 유지 route:
  - `/krx/news`
  - `/krx`
  - `/krx/macro-calendar`

## 현재 환경 제약
- Codex 실행 환경에서는 포트 바인딩 제약이 있을 수 있어, 브라우저 네트워크 측정은 실제 사용자 환경 또는 별도 로컬 터미널에서 재확인하는 편이 안전합니다.
