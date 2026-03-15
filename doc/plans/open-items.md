# Open Items

| ID | Area | Item | Why | Next Action | Status |
| --- | --- | --- | --- | --- | --- |
| DATA-003 | Backend | KIS derivatives adapter 추가 | 파생 summary를 실제 매매 source와 맞춰야 함 | 최소 endpoint/필드 확정 후 adapter 추가 | Open |
| DATA-005 | Backend | KIS precedence 정책 고정 | 기존 KRX reference와 KIS가 섞일 때 우선순위 충돌 가능성 존재 | source priority 규칙과 테스트 추가 | Open |

## Recently Closed
| ID | Area | Item | Result |
| --- | --- | --- | --- |
| DATA-001 | Strategy | `파생=KIS`, `미국 금리=FRED` source 전략 고정 | 완료 |
| DATA-002 | Backend | FRED rates adapter 추가 | `GET /api/krx/macro-reference/cards`와 `DGS10`/`FEDFUNDS` contract 완료 |
| DATA-004 | Frontend | 시장 신호 source 연결 확장 | KIS/KRX provenance를 시장 신호 UI badge로 노출 완료 |
| DOC-004 | AI Insights | 심리/변동성 게이지 추가 | 완료 |
| DOC-005 | Copy | 잔여 aria-label 및 카피 정리 | 완료 |
| DOC-006 | Routing | 사용자 표면 명칭과 URL 전략 정리 | 완료 |
