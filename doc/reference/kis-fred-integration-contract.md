# KIS FRED Integration Contract

## 목적
- 다음 데이터 연동 라운드에서 source ownership을 먼저 고정합니다.
- 파생과 거시 reference를 같은 기준으로 오래 운영할 수 있게 기준 문서를 남깁니다.

## canonical source ownership

### KIS 담당
- 파생 시세
- 파생 요약에 필요한 핵심 market data
- 장기적으로 호가/체결/주문과 이어질 수 있는 파생 데이터
- market-data-first 운영이 필요한 영역의 1차 source
- WTI와 FX consistency를 KIS로 맞출 경우의 preferred operational candidate
  - 단, WTI symbol coverage는 실제 endpoint/symbol 확인이 남아 있습니다.

### FRED 담당
- 현재 runtime macro reference source
- `DEXKOUS`: 원/달러 환율 reference
- `DCOILWTICO`: WTI·에너지 reference
- `DGS10`: 미국채 10년물
- `FEDFUNDS`: 미국 금리 reference
- daily/monthly reference 용도이며, 실시간 trading feed로 보지 않습니다.

### Massive 담당
- future candidate only
- env는 예약돼 있지만 runtime에는 아직 wired 되어 있지 않습니다.
- 현재는 source ownership을 넘기지 않습니다.

## 왜 이렇게 나누는가

### 파생은 KIS
- 이 프로젝트의 파생 데이터는 단순 참고가 아니라 `시장 신호`와 직접 연결됩니다.
- 장기적으로 실제 거래 연계 가능성이 중요한 영역이므로 KIS가 더 자연스럽습니다.

### 거시 reference는 FRED
- 환율, WTI, 미국채 10년물, 미국 금리는 시장 해석용 reference에 가깝습니다.
- FRED는 시계열 안정성, 과거 데이터, 표준 series 관리에 유리합니다.
- 현재 구현도 이 구분을 따릅니다. macro reference route는 FRED만 사용합니다.

## 1차 target series

### FRED
- `DEXKOUS`: 환율
- `DCOILWTICO`: WTI·에너지
- `DGS10`: 미국채 10년물
- `FEDFUNDS`: 연방기금실효금리 월평균

### 2차 검토 series
- `DGS2`
- `SOFR`

## 1차 backend contract
- route: `GET /api/krx/macro-reference/cards`
- provider mode:
  - `disabled`
  - `file`
  - `api`
- 기본 local mode는 `disabled`입니다.
- file fixture를 먼저 통과시키고, API mode는 FRED key가 준비된 뒤 활성화합니다.

## provider family
- `KIS`: `MARKET_DATA`
- `FRED`: `REFERENCE_DATA`
- `Massive`: reserved only, not runtime-wired

## freshness policy
- `KIS derivatives`: 장중 민감도가 높으므로 짧은 캐시
- `FRED macro reference`: 해석용 reference이므로 긴 캐시

권장 기준:
- KIS summary: 30초 ~ 2분
- FRED reference: 15분 ~ 1시간

## fallback policy
- KIS 실패 시:
  - 파생 카드에 graceful fallback
  - source coverage와 업데이트 지연 문구 노출
- FRED 실패 시:
  - 환율/원유/금리 reference 카드만 fallback
  - 뉴스/시장 신호는 유지

## provenance policy
- 카드 단위로 source label을 보여줄 수 있어야 합니다.
- source가 섞여도 `KIS`, `FRED`가 구분되어야 합니다.
- 활성화 증빙은 env 존재가 아니라 route output, source label, UI provenance로 확인합니다.

## testing learnings
- Massive Basic은 historical/reference-oriented 접근으로 이해하는 편이 안전합니다.
- Massive Basic에 대해 real-time quote, conversion entitlement, snapshot entitlement를 전제하지 않습니다.
- `MASSIVE_*` env 값을 채워도 runtime wiring이 없으면 활성화되지 않습니다.
- Meaningful activation proof는 실제 route 응답과 화면 provenance입니다.

## 구현 제외 범위
- 실제 주문 기능
- 모든 거시 위젯의 일괄 source 교체
- 뉴스/공시 source 구조 재설계

## 관련 문서
- `../plans/kis-fred-rollout-plan.md`
- `../domains/derivatives/runbook.md`
- `../domains/macro-calendar/runbook.md`
