# KRX Market Briefing Input Runbook

08:30 KST 프리마켓 브리핑용 입력 데이터를 안정적으로 적재하기 위한 수집 파이프라인 운영 문서입니다.

실제 규칙 기반 브리핑 생성/백테스트는 `MARKET_SIGNAL_BRIEFING_RUNBOOK.md`를 참고하세요.

## 1) 목표
아래 입력을 정규화/저장합니다.
- KIS 투자자 수급, 프로그램 매매, 신용/대차 관련 일별 팩터
- KIS 국내 선물/옵션 프리오픈 스냅샷
- KIS 야간선물 스냅샷
- KRX 파생 참조지표(투자자 매매성과, put/call ratio, implied volatility)

브리핑 문장 생성/예측은 이 모듈의 범위가 아닙니다.

## 2) 테이블
- `market_daily_factors`
- `market_intraday_snapshots`
- `derivatives_daily_metrics`
- `provider_health_checks`
- `briefing_input_runs`

`source_name`, `source_url`, `source_record_id`, `raw_payload_json`을 함께 저장해 감사 가능성을 유지합니다.

## 3) Provider 의존성
- `KisMarketBreadthService`
  - mode: `disabled | file | api`
  - 수집 범위: 투자주체 순매수, 프로그램 매매, 신용/융자/대차 관련 지표
- `KisDomesticDerivativesService`
  - mode: `disabled | file | api`
  - 수집 범위: 프리오픈 선물/옵션 스냅샷
- `KisNightFuturesService`
  - mode: `disabled | file | api`
  - 수집 범위: 야간선물 스냅샷
- `KrxDerivativesReferenceService`
  - mode: `disabled | file | api`
  - 수집 범위: put/call ratio, implied volatility, open interest 및 파생 투자자 지표
  - 자동 수집이 어려우면 `import-briefing-krx-reference`로 수동 입력

실제 응답 키가 환경마다 다를 경우 `*_FIELD_ALIAS_MAP_JSON`으로 canonical 필드 매핑을 주입할 수 있습니다.
예시:
`KIS_MARKET_BREADTH_FIELD_ALIAS_MAP_JSON={"investor_foreign_net_buy":["frg_ntby_amt","foreign_net_amt"]}`

## 4) 지표 구분 (Mandatory vs Optional)
Mandatory (최소 브리핑 입력 요건)
- `trade_date`
- `source_name`
- 투자주체 순매수(가능한 participant class 기준)
- 프로그램 매매 총량(가능한 경우)
- 신용/융자/대차 관련 잔고 지표 중 최소 1개
- 선물 가격/변화/거래량(가능한 경우)
- `put_call_ratio`
- `implied_volatility`

Optional (소스 제공 시 저장)
- 세부 participant class 확장 필드
- `open_interest_total/call_open_interest/put_open_interest`
- bid/ask 등 추가 intraday 지표
- 글로벌 입력 Provider(향후 확장용 인터페이스)

필수 필드가 일부 누락되어도 run 전체를 실패시키지 않고 로그에 누락 필드를 기록합니다.

## 5) 실행 명령
```bash
cd backend
python3 -m src.krx.source_ingestion.cli collect-briefing-eod --trade-date 2026-03-09
python3 -m src.krx.source_ingestion.cli collect-briefing-night --trade-date 2026-03-09
python3 -m src.krx.source_ingestion.cli collect-briefing-preopen --trade-date 2026-03-10
python3 -m src.krx.source_ingestion.cli backfill-briefing --start-date 2026-03-01 --end-date 2026-03-09
python3 -m src.krx.source_ingestion.cli import-briefing-krx-reference --trade-date 2026-03-09 --input ./data/krx_derivatives_2026-03-09.json
```

수동 import CSV 템플릿:
- `doc/krx_derivatives_reference_manual_template.csv` (repo root 기준)

## 6) 조회 API (Admin)
- `GET /api/krx/admin/briefing-inputs/runs`
- `GET /api/krx/admin/briefing-inputs/provider-health-checks`
- `GET /api/krx/admin/briefing-inputs/market-daily-factors`
- `GET /api/krx/admin/briefing-inputs/market-intraday-snapshots`
- `GET /api/krx/admin/briefing-inputs/derivatives-daily-metrics`

`KRX_ADMIN_API_KEY`가 설정된 경우 `X-Admin-Key` 헤더가 필요합니다.
## 7) 스케줄러 계획 (08:30 KST 기준)
권장 cron orchestration:
- 평일 06:40 KST: 야간선물 수집
  - `collect-briefing-night --trade-date <today_kst>`
- 평일 08:20 KST: 프리오픈 스냅샷 수집
  - `collect-briefing-preopen --trade-date <today_kst>`
- 평일 08:30 KST: 규칙 기반 브리핑 생성
  - `generate-market-briefing --trade-date <today_kst> --mode SCHEDULED`
- 평일 16:10 KST: 장마감 일별 팩터 수집
  - `collect-briefing-eod --trade-date <today_kst>`

운영에서는 `provider_health_checks`의 `FAILED`/`SKIPPED_DISABLED`를 알림 기준으로 사용하세요.

## 8) 장애/품질 처리
- Provider별 실패는 독립 처리: 한 Provider 실패가 다른 Provider 적재를 중단시키지 않음
- 각 Provider는 retry/backoff 독립 구성
- run 결과는 `briefing_input_runs.status`에 `SUCCESS/PARTIAL_SUCCESS/FAILED/SKIPPED_DISABLED`로 기록
- 재실행 시 upsert되어 idempotent 보장
