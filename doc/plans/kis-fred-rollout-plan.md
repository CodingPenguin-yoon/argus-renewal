# KIS FRED Rollout Plan

## 목표
- 파생 데이터는 KIS Open API로,
- 미국채 10년물과 미국 금리는 FRED로,
- 단계적으로 붙이는 실행 순서를 고정합니다.

## 범위

### 포함
- KIS 기반 파생 source 도입 계획
- FRED 기반 미국 금리 reference 도입 계획
- backend adapter, provider registry, frontend wiring 순서

### 제외
- 실제 주문 기능
- 뉴스/공시 source 재설계
- 전체 거시 위젯의 즉시 전면 교체

## 단계별 계획

### Phase 0. 계약 고정
- source ownership 문서 승인
- target series 확정
- provider key와 env 초안 확정

### Phase 1. provider contract 설계
- `KIS`는 `MARKET_DATA`
- `FRED`는 `REFERENCE_DATA`
- adapter interface와 config ownership 정의

### Phase 2. FRED adapter
- 우선 series:
  - `DGS10`
  - `FEDFUNDS`
- 필요 시 추가:
  - `DGS2`
  - `SOFR`

완료 기준:
- backend에서 미국채 10년물 / 미국 금리 reference를 안정적으로 반환

### Phase 3. KIS derivatives adapter
- KIS 파생 endpoint 확정
- summary에 필요한 최소 필드부터 연결
- 기존 파생 요약과 provenance 연결

진행 메모:
- 완료: `pre_open_futures` contract 추가로 `KIS_DOMESTIC_DERIVATIVES` snapshot을 derivatives summary에 노출
- 완료: market-wide summary 필드를 `derivatives_daily_metrics`로 적재하는 fallback ingest 경로 추가
- 완료: `derivatives_daily_metrics` source priority를 `KRX_DERIVATIVES_MANUAL -> KIS_DOMESTIC_DERIVATIVES -> KRX_DERIVATIVES_REFERENCE -> others`로 고정
- 남음: mixed-source delta provenance와 실제 KIS endpoint 연결

완료 기준:
- `시장 신호`의 파생 요약이 KIS source로 재구성 가능

### Phase 4. frontend wiring
- 대시보드와 AI 인사이트의 금리 reference 카드 연결 완료 상태 유지
- 시장 신호의 파생 source provenance 표면 연결 완료 상태 유지
- source label, 업데이트 시각, fallback 문구 정리

### Phase 5. 검증
- KIS 실패 시 graceful fallback
- FRED 실패 시 graceful fallback
- 뉴스 동작에 영향 없음

## 우선순위
1. FRED adapter
2. KIS derivatives adapter
3. frontend reference wiring
4. 세부 지표 확장

## open questions
- KIS에서 실제로 사용할 파생 endpoint 최종 확정
- FRED series를 `DGS10`, `FEDFUNDS`로 고정할지 여부
- `DGS2`, `SOFR`를 1차 범위에 포함할지 여부

## 관련 문서
- `../reference/kis-fred-integration-contract.md`
- `open-items.md`
