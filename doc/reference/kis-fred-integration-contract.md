# KIS FRED Integration Contract

## 목적
- 다음 데이터 연동 라운드에서 source ownership을 먼저 고정합니다.
- 파생과 거시 금리를 같은 기준으로 오래 운영할 수 있게 기준 문서를 남깁니다.

## canonical source ownership

### KIS 담당
- 파생 시세
- 파생 요약에 필요한 핵심 market data
- 장기적으로 호가/체결/주문과 이어질 수 있는 파생 데이터

### FRED 담당
- 미국채 10년물
- 미국 기준금리/정책금리 계열
- 미국 단기금리/보조금리 계열

## 왜 이렇게 나누는가

### 파생은 KIS
- 이 프로젝트의 파생 데이터는 단순 참고가 아니라 `시장 신호`와 직접 연결됩니다.
- 장기적으로 실제 거래 연계 가능성이 중요한 영역이므로 KIS가 더 자연스럽습니다.

### 미국 금리는 FRED
- 미국채 10년물과 미국 금리는 시장 해석용 reference에 가깝습니다.
- FRED는 시계열 안정성, 과거 데이터, 표준 series 관리에 유리합니다.

## 1차 target series

### FRED
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

## freshness policy
- `KIS derivatives`: 장중 민감도가 높으므로 짧은 캐시
- `FRED rates`: 해석용 reference이므로 긴 캐시

권장 기준:
- KIS summary: 30초 ~ 2분
- FRED reference: 15분 ~ 1시간

## fallback policy
- KIS 실패 시:
  - 파생 카드에 graceful fallback
  - source coverage와 업데이트 지연 문구 노출
- FRED 실패 시:
  - 금리 reference 카드만 fallback
  - 뉴스/시장 신호는 유지

## provenance policy
- 카드 단위로 source label을 보여줄 수 있어야 합니다.
- source가 섞여도 `KIS`, `FRED`가 구분되어야 합니다.

## 구현 제외 범위
- 실제 주문 기능
- 모든 거시 위젯의 일괄 source 교체
- 뉴스/공시 source 구조 재설계

## 관련 문서
- `../plans/kis-fred-rollout-plan.md`
- `../domains/derivatives/runbook.md`
- `../domains/macro-calendar/runbook.md`
