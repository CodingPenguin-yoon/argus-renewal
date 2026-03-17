# KIS FRED Rollout Plan

## 목표
- 파생 데이터는 KIS Open API로,
- 현재 runtime macro reference는 FRED로,
- KIS는 WTI와 likely FX consistency까지 포함하는 preferred operational candidate로 검토하되,
- WTI symbol coverage 확인 전까지는 FRED `DCOILWTICO` reference를 유지하고,
- 단계적으로 붙이는 실행 순서를 고정합니다.

## 범위

### 포함
- KIS 기반 파생 source 도입 계획
- FRED 기반 macro reference 운영 계획
- KIS 기반 WTI/FX 이전 검토 범위
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
- activation proof를 env가 아니라 route/UI provenance로 본다는 기준 고정

### Phase 1. provider contract 설계
- `KIS`는 `MARKET_DATA`
- `FRED`는 `REFERENCE_DATA`
- adapter interface와 config ownership 정의

### Phase 2. FRED adapter
- 현재 운영 series:
  - `DEXKOUS`
  - `DCOILWTICO`
  - `DGS10`
  - `FEDFUNDS`
- 필요 시 추가:
  - `DGS2`
  - `SOFR`

완료 기준:
- backend에서 daily/monthly macro reference를 안정적으로 반환
- `/api/krx/macro-reference/cards`와 UI source label에서 FRED provenance를 확인 가능

### Phase 3. KIS derivatives adapter
- KIS 파생 endpoint 확정
- summary에 필요한 최소 필드부터 연결
- 기존 파생 요약과 provenance 연결

진행 메모:
- 완료: `pre_open_futures` contract 추가로 `KIS_DOMESTIC_DERIVATIVES` snapshot을 derivatives summary에 노출
- 완료: market-wide summary 필드를 `derivatives_daily_metrics`로 적재하는 fallback ingest 경로 추가
- 완료: `derivatives_daily_metrics` source priority를 `KRX_DERIVATIVES_MANUAL -> KIS_DOMESTIC_DERIVATIVES -> KRX_DERIVATIVES_REFERENCE -> others`로 고정
- 완료: 공식 KIS `inquire-price` 응답 형태인 `output1/output2/output3` object payload support
- 완료: mixed-source delta provenance UI를 시장 신호 파생 탭에 노출
- 완료: live KIS query contract를 `KIS_DOMESTIC_DERIVATIVES_QUERY_PARAMS_JSON` + `FID_INPUT_ISCD 필수 / FID_COND_MRKT_DIV_CODE 기본값 F`로 고정
- 완료: `AUTO_KOSPI200_FRONT` sentinel이 공식 한국투자 지수선물 master 파일 `fo_idx_code_mts.mst.zip`를 읽어 최근월 KOSPI200 선물 short code를 자동 결정
- 남음: 다른 기초자산/옵션 계약까지 sentinel 자동 해석 전략 확장 여부 결정

완료 기준:
- `시장 신호`의 파생 요약이 KIS source로 재구성 가능

### Phase 4. KIS WTI/FX 검토
- KIS를 WTI의 preferred operational source로 쓸 수 있는지 symbol/endpoint coverage 확인
- 필요 시 FX도 KIS consistency 후보로 검토
- 확인 전까지 runtime macro reference는 FRED 유지

완료 기준:
- KIS WTI symbol coverage가 문서로 확인되거나, 미지원이면 FRED 유지 결정이 기록됨

### Phase 5. frontend wiring
- 대시보드와 AI 인사이트의 금리 reference 카드 연결 완료 상태 유지
- 시장 신호의 파생 source provenance 표면 연결 완료 상태 유지
- source label, 업데이트 시각, fallback 문구 정리

### Phase 6. 검증
- KIS 실패 시 graceful fallback
- FRED 실패 시 graceful fallback
- 뉴스 동작에 영향 없음
- Massive env 추가만으로 source가 바뀌지 않음을 확인
- 의미 있는 활성화 증빙은 route output / source label / UI provenance로 확인

## 우선순위
1. FRED adapter
2. KIS derivatives adapter
3. KIS WTI/FX 검토
4. frontend reference wiring
5. 세부 지표 확장

## open questions
- KIS에서 실제로 사용할 파생 endpoint 최종 확정
- KIS WTI symbol coverage를 실제로 확보할 수 있는지
- FX를 FRED `DEXKOUS`에서 KIS consistency 경로로 옮길 operational 이점이 충분한지
- FRED series를 `DEXKOUS`, `DCOILWTICO`, `DGS10`, `FEDFUNDS`로 유지할지 여부
- `DGS2`, `SOFR`를 1차 범위에 포함할지 여부
- Massive는 future candidate로만 둘지, 별도 adapter 이후 재평가할지

## 관련 문서
- `../reference/kis-fred-integration-contract.md`
- `open-items.md`
