# Current Status

## Done
- KRX IA를 `대시보드 / AI 인사이트 / 시장 신호 / 시장 뉴스 / 매크로 캘린더`로 재정렬했습니다.
- 공통 헤더는 compact status 중심으로 축소했고, 메인 해석은 `AI 인사이트`로 이동했습니다.
- `doc/` 분류를 `architecture / domains / plans / reference / troubleshooting` 기준으로 정리했습니다.
- KRX 성능 정책 1차/2차 정리로 시장 신호, 파생, AI 인사이트 macro news에 30초 재검증을 적용했고, 상단 GNB는 안정 탭만 적극 prefetch하도록 조정했습니다.
- production 서버 기준 수동 측정에서 `/krx/dashboard` 최초 진입 시 `/krx`, `/krx/insights`, `/krx/macro-calendar` prefetch는 확인됐고 `/krx/news` prefetch는 보이지 않았습니다.
- 같은 세션에서 `AI 인사이트` 클릭 후 추가 리소스는 0건이었고, `시장 뉴스` 클릭 후에는 뉴스 RSC와 탭별 리소스가 새로 요청되어 prefetch 정책이 의도대로 동작함을 확인했습니다.
- `대시보드` 상단에 환율, WTI·에너지, 금리 기준의 거시 미니 위젯을 추가했습니다.
- `AI 인사이트`에 `시장 심리 / 변동성 온도 / AI 확신도` 게이지를 추가했고 접근성 속성을 보강했습니다.
- 사용자 표면 canonical 경로를 `/krx/dashboard`, `/krx/insights`, `/krx/macro-calendar`로 정리하고, 기존 경로는 redirect로 유지했습니다.
- 오늘 작업의 배경과 의사결정을 쉬운 말로 설명하는 `doc/troubleshooting/` 문서를 추가했습니다.
- 다음 라운드 source 전략으로 `파생=KIS`, `미국채 10년물/미국 금리=FRED` 기준 문서와 rollout plan을 추가했습니다.

## In Progress
- 다음 데이터 source 연동 라운드의 범위와 순서를 문서로 고정했습니다.

## Next
1. FRED rates adapter 범위와 series 확정
2. KIS derivatives adapter 범위와 endpoint 확정
3. backend provider wiring
4. frontend 연결

## Risks
- legacy redirect는 당분간 유지되므로, 외부 링크나 북마크는 새 경로와 구 경로가 공존할 수 있습니다.
- 아카이브 문서는 과거 설계 의도이므로 현재 구조 설명으로 재사용하면 안 됩니다.

## Last Updated
- 2026-03-16
