# Open Items

| ID | Area | Item | Why | Next Action | Status |
| --- | --- | --- | --- | --- | --- |
| DATA-003 | Backend | KIS derivatives adapter 추가 | 파생 summary를 실제 매매 source와 맞춰야 함 | 실제 KIS endpoint 필드 매핑과 mixed-source delta provenance UI 연결 | Open |

## Notes
- backend summary contract에는 `source_coverage.comparisons`가 추가되어, 전일 대비 변화율이 어떤 source 조합으로 계산됐는지 확인할 수 있습니다.

## Recently Closed
| ID | Area | Item | Result |
| --- | --- | --- | --- |
| DATA-001 | Strategy | `파생=KIS`, `미국 금리=FRED` source 전략 고정 | 완료 |
| DATA-002 | Backend | FRED rates adapter 추가 | `GET /api/krx/macro-reference/cards`와 `DGS10`/`FEDFUNDS` contract 완료 |
| DATA-004 | Frontend | 시장 신호 source 연결 확장 | KIS/KRX provenance를 시장 신호 UI badge로 노출 완료 |
| DATA-003A | Backend | KIS pre-open summary contract 추가 | derivatives summary에 `pre_open_futures` 필드를 추가하고 파생 탭에 반영 완료 |
| DATA-003B | Backend | KIS domestic market-wide summary ingest | payload summary를 `derivatives_daily_metrics`에 적재하고 KRX 부재 시 fallback 경로 확인 완료 |
| DATA-005 | Backend | KIS precedence 정책 고정 | `KRX_DERIVATIVES_MANUAL -> KIS_DOMESTIC_DERIVATIVES -> KRX_DERIVATIVES_REFERENCE -> others` 우선순위를 summary·trends·signal engine에 공통 적용 완료 |
| DOC-004 | AI Insights | 심리/변동성 게이지 추가 | 완료 |
| DOC-005 | Copy | 잔여 aria-label 및 카피 정리 | 완료 |
| DOC-006 | Routing | 사용자 표면 명칭과 URL 전략 정리 | 완료 |
