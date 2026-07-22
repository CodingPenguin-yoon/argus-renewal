# ADR-001: 데이터 종류별 다중 증권사 Provider 구조

- 상태: `ACCEPTED`
- 날짜: `2026-07-21`
- 결정자: 사용자
- 대체하는 ADR: 없음
- 대체된 ADR: 없음

## 배경

새 제품의 핵심 데이터는 한 증권사 API만으로 충족되지 않는다.

- KIS는 가격·차트·선물·옵션 시세와 장 마감 종목별 수급에 적합하다.
- LS증권은 KOSPI, KOSPI200, 선물, 콜옵션, 풋옵션의 시간대별 투자자 수급에 적합하다.
- 키움 REST API는 종목별 장중 외국인·기관 수급 차트에 적합하다.

기존 구현은 provider가 외부 응답을 내부 record로 정규화하지만 KIS 중심 책임과 설정이 남아 있다. 새 방향은 현재 코드를 즉시 교체하지 않고 새 폴더에서 capability별 계약을 만든 뒤 수직 기능 단위로 전환해야 한다.

## 결정 기준

- 핵심 데이터 요구사항 충족
- 공급자 교체와 장애 격리
- 추정치·확정치·신선도 추적
- 기존 Argus v2 계약 보호
- 테스트 가능한 provider boundary
- 소규모 운영에서 감수 가능한 복잡도

## 검토한 선택지

### 1순위: Capability 기반 Port와 증권사 Adapter

- 구조: 시장수급, 종목수급, 시세, 차트, 파생시세처럼 데이터 capability별 내부 계약을 만들고 KIS·LS·키움을 adapter로 연결한다.
- 적합한 이유: 증권사별 강점을 조합하면서 UI와 업무 규칙에서 공급자 세부사항을 제거할 수 있다.
- 장점:
  - 데이터 종류별 공급자 교체 가능
  - 공급자 장애의 영향 범위 제한
  - fixture 기반 계약 테스트 가능
  - 기존 provider 흐름을 재사용 가능
- 단점:
  - 계정·시크릿·호출 제한·운영 모니터링이 늘어난다.
  - 동일 개념의 단위와 시장 범위를 정규화해야 한다.
  - 추정치와 확정치 reconciliation이 필요하다.
- 전환 비용과 위험: 중간. 새 계약과 저장 모델이 필요하지만 기존 경로를 유지한 병행 전환이 가능하다.

### 2순위: KIS 단일 Provider 유지

- 구조: 현재 KIS provider만 확장한다.
- 적합한 경우: 운영 단순성이 데이터 완전성보다 중요할 때
- 장점: 인증·운영·호출 제한 관리가 단순하다.
- 단점: 종목별 장중 수급 갱신 횟수와 시장 파생 수급 범위가 핵심 요구사항을 충족하지 못한다.
- 추천안보다 낮은 이유: 제품의 핵심 데이터를 얻지 못한다.

### 3순위: 증권사별 모듈을 화면에서 직접 조합

- 구조: KIS·LS·키움 전용 service/API를 만들고 frontend가 결과를 조합한다.
- 적합한 경우: 짧은 실험으로 API payload만 확인할 때
- 장점: 초기 구현이 빠르다.
- 단점: 공급자 계약이 UI로 누출되고 실패·단위·신선도 처리가 중복된다.
- 추천안보다 낮은 이유: 현재 구조가 다시 강하게 결합되고 장기 변경 비용이 커진다.

## 제안 결정

- 선택: `Capability 기반 Port와 증권사 Adapter`
- 승인 내용: 1차 시장 범위는 `KRX`로 통일하고, 증권사 장중 수급은 추정값으로 사용하며 KRX 장 마감 거래실적을 확정 기준으로 사용한다.
- 승인일: `2026-07-21`

## 목표 Provider Map

| Capability | Primary | Secondary 또는 마감 검증 | 데이터 성격 |
|---|---|---|---|
| `market_investor_flow` | LS증권 `t1602` | KIS 시장 수급, KRX 장 마감 검증 | 장중 조회·시장/파생 |
| `stock_investor_flow_intraday` | 키움 `ka10064` | 없음 | 종목별 장중 외국인·기관 |
| `stock_investor_flow_eod` | KRX 장 마감 거래실적 | KIS 또는 키움 `ka10060` 대조 | 장 마감 개인·외국인·기관 확정 기준 |
| `stock_quote` | KIS | 키움 후보 | 장중 시세 |
| `stock_chart` | KIS | 키움 후보 | 가격 시계열 |
| `index_derivatives_quote` | KIS | 없음 | KOSPI200 선물·옵션 시세·체인 |
| `single_stock_derivatives_quote` | 검증 후 결정 | 없음 | 삼성전자·SK하이닉스 파생 |

Secondary는 자동 평균이나 무조건적인 silent fallback을 뜻하지 않는다. 사용 시 source와 전환 사유를 기록한다.

1차 구현의 `market_scope`는 시세와 수급 모두 `KRX`로 고정한다. NXT와 SOR는 동일한 종목이라도 거래량과 투자자 수급 범위가 달라질 수 있으므로 별도 capability와 화면 표기 규칙을 정한 뒤 추가한다.

## 신뢰 기준과 확정 규칙

- KRX 장 마감 거래실적을 확정 기준(reference truth)으로 사용한다.
- 증권사 장중 투자자 수급은 공급자와 무관하게 `estimate`로 저장한다.
- 증권사 장중값과 KRX 확정값은 같은 행을 갱신하지 않고 서로 다른 fact로 보존한다.
- 공급자 간 값이 다르면 평균하지 않고 원본, 관측 시각, 시장 범위와 차이를 기록한다.
- KRX 자동 수집 가능 범위와 라이선스가 확인되기 전에는 redacted fixture 또는 승인된 수동 검증 데이터로 reconciliation 계약을 검증한다.

## 목표 모듈 경계

```text
backend/src/market_data/
├── domain/          # 공급자와 무관한 fact, 상태, 단위 규칙
├── application/     # capability별 수집·조회 use case
├── providers/
│   ├── kis/         # 인증과 KIS adapter
│   ├── kiwoom/      # 인증과 키움 adapter
│   └── ls/          # 인증과 LS adapter
├── collectors/      # capability별 schedule과 orchestration
└── storage/         # 새 fact 저장과 조회

frontend/src/market_terminal/
├── contracts/
├── server/
└── components/
```

초기 구현에서 폴더를 기계적으로 모두 만들지 않는다. 첫 수직 기능이 요구하는 최소 파일만 생성한다.

## 의존성 방향

```text
provider SDK/HTTP
→ provider adapter
→ capability contract
→ normalized market fact
→ storage
→ query/API
→ frontend
```

- domain과 application은 증권사 패키지·필드명·HTTP에 의존하지 않는다.
- provider adapter는 화면 계약과 판단 엔진에 의존하지 않는다.
- HTTP API는 collector를 직접 실행하지 않고 저장된 최신 fact를 조회한다.

## 데이터 계약

모든 시장 fact가 최소한 다음 provenance를 가진다.

- `provider`
- `capability`
- `market_scope`
- `instrument_code`
- `observed_at`
- `collected_at`
- `data_quality`: `estimate | confirmed`
- `freshness`: `fresh | stale | missing`
- `unit`과 `currency`
- `source_record_id` 또는 동등한 중복 방지 키

장중 추정치와 장 마감 확정치는 덮어쓰지 않고 별도 fact로 저장한다.

## 결과와 영향

- 영향을 받는 모듈: backend provider·collector·storage·API, frontend 계약과 신규 화면
- 공개 계약: 신규 `/api/market-data/v1/*`를 병행 추가하고 기존 `/api/argus/v2/*`는 유지
- 데이터: 신규 market data table을 기존 `argus_v2_*`와 병행 운영
- 테스트: provider fixture contract, 단위·부호 normalization, 중복 수집, stale 처리 테스트 추가
- 마이그레이션: 새 migration만 추가하고 기존 migration과 테이블을 수정하지 않음
- 문서: 새 명세·아키텍처·API·DB 문서를 실제 구현 단계에 맞춰 갱신

## 감수한 단점

- 증권사 계정과 시크릿이 늘어난다.
- provider별 이용 가능 시간과 호출 제한을 독립적으로 운영해야 한다.
- 공급자별 데이터 정의 차이를 지속적으로 관리해야 한다.
- 일부 화면은 공급자 장애 시 부분 데이터만 표시한다.

## 검증 방법

- 동일 fixture가 capability contract를 만족하는지 공급자별 계약 테스트
- 장중 삼성전자·SK하이닉스와 KOSPI 시장 수급의 갱신 간격 기록
- EOD 확정치와 장중 마지막 추정치 차이 기록
- 공급자 하나를 실패시켜 다른 capability API가 정상인지 확인
- KOSPI200 구성종목 수집 주기와 SQLite 쓰기량 측정

## 재검토 조건

- 단일 공급자가 모든 핵심 capability를 충분한 품질로 제공
- 호출 제한 또는 약관 때문에 KOSPI200 구성종목 수집이 불가능
- SQLite writer contention이나 보존 용량이 운영 기준을 초과
- 외부 서비스 제공 또는 다중 사용자 운영으로 라이선스·배포 경계가 변경
