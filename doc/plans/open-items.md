# Open Items

| ID | Area | Item | Why | Next Action | Status |
| --- | --- | --- | --- | --- | --- |
| DATA-003 | Backend | KIS derivatives adapter 추가 | 파생 summary를 실제 매매 source와 맞춰야 함 | 현재는 `AUTO_KOSPI200_FRONT` sentinel만 지원하므로, 필요 시 다른 기초자산/옵션 계약까지 자동 해석 범위를 확장 | Open |
| DATA-006 | Strategy | KIS WTI/FX ownership 확정 | KIS를 market-data-first source로 확장하면 운영 일관성이 좋아질 수 있음 | KIS WTI symbol/endpoint coverage를 확인하고, FX consistency 이전 필요성을 판단 | Open |
| DATA-007 | Strategy | Massive future candidate 기준 고정 | Massive env 예약과 실제 runtime wiring을 문서상 혼동하지 않기 위해 | Massive는 adapter와 provenance 확인 전까지 runtime source로 취급하지 않는 기준 유지 | Open |

## Notes
- backend summary contract에는 `source_coverage.comparisons`가 추가되어, 전일 대비 변화율이 어떤 source 조합으로 계산됐는지 확인할 수 있습니다.
- frontend 파생 탭은 이 `comparisons`를 mixed-source / 동일 source badge와 함께 직접 보여줍니다.
- `KIS_DOMESTIC_DERIVATIVES` provider는 공식 KIS `output1/output2/output3` object payload를 읽을 수 있지만, summary row 적재는 payload에 market-wide field가 실제로 있을 때만 발생합니다.
- live KIS provider는 `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON`에 `FID_INPUT_ISCD`가 반드시 있어야 하며, `FID_COND_MRKT_DIV_CODE`가 없으면 `F`를 기본값으로 사용합니다.
- `FID_INPUT_ISCD=AUTO_KOSPI200_FRONT`를 쓰면 provider가 공식 한국투자 지수선물 master 파일 `fo_idx_code_mts.mst.zip`에서 최근월 KOSPI200 선물 short code를 자동 해석합니다.
- 현재 runtime macro reference source는 FRED이며, 대상 series는 `DEXKOUS`, `DCOILWTICO`, `DGS10`, `FEDFUNDS`입니다.
- FRED 값은 daily/monthly reference 용도이지 실시간 trading feed가 아닙니다.
- `MASSIVE_*` env는 예약 블록일 뿐이고, 값을 넣어도 runtime wiring이 없으면 활성화되지 않습니다.
- 의미 있는 활성화 확인은 env 존재가 아니라 route output, source label, UI provenance입니다.

## Recently Closed
| ID | Area | Item | Result |
| --- | --- | --- | --- |
| DATA-001 | Strategy | `파생=KIS`, `현재 runtime macro reference=FRED` source 전략 고정 | 완료 |
| DATA-002 | Backend | FRED rates adapter 추가 | `GET /api/krx/macro-reference/cards`와 `DEXKOUS`/`DCOILWTICO`/`DGS10`/`FEDFUNDS` contract 완료 |
| DATA-004 | Frontend | 시장 신호 source 연결 확장 | KIS/KRX provenance를 시장 신호 UI badge로 노출 완료 |
| DATA-003A | Backend | KIS pre-open summary contract 추가 | derivatives summary에 `pre_open_futures` 필드를 추가하고 파생 탭에 반영 완료 |
| DATA-003B | Backend | KIS domestic market-wide summary ingest | payload summary를 `derivatives_daily_metrics`에 적재하고 KRX 부재 시 fallback 경로 확인 완료 |
| DATA-003C | Backend | KIS 최근월물 symbol 자동 결정 | `AUTO_KOSPI200_FRONT` sentinel과 공식 `fo_idx_code_mts.mst.zip` 기반 최근월 KOSPI200 선물 short code 자동 해석 완료 |
| DATA-005 | Backend | KIS precedence 정책 고정 | `KRX_DERIVATIVES_MANUAL -> KIS_DOMESTIC_DERIVATIVES -> KRX_DERIVATIVES_REFERENCE -> others` 우선순위를 summary·trends·signal engine에 공통 적용 완료 |
| DOC-004 | AI Insights | 심리/변동성 게이지 추가 | 완료 |
| DOC-005 | Copy | 잔여 aria-label 및 카피 정리 | 완료 |
| DOC-006 | Routing | 사용자 표면 명칭과 URL 전략 정리 | 완료 |
