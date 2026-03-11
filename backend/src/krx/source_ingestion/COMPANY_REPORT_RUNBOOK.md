# KRX Company Report Pipeline Runbook

KRX 대형주(초기 20~30종목) 대상 야간 리포트 자동 생성 운영 문서입니다.

## 1) 목적
- 회사별 데이터(수급/이벤트/공시/가격 컨텍스트)를 구조화해 야간 리포트 생성
- 출력은 반드시 사실 기반(source-grounded)으로 생성
- 리포트 결과를 DB에 구조화 JSON + Markdown으로 동시 저장
- 리포트 품질보다 일관된 적재/조회/재실행(idempotent) 보장을 우선

## 2) 주요 테이블
마이그레이션: `src/krx/company_master/migrations/006_company_reports.sql`

- `report_universes`
  - 유니버스 메타 정보(키, 이름, 선택 모드, 목표 종목 수)
- `report_universe_members`
  - 유니버스 멤버(회사 ID, active/inactive 상태)
- `company_reports`
  - 회사/일자별 최신 리포트 본문(JSON + Markdown)
- `company_report_sections`
  - 섹션별 분해 저장(고정 섹션 키)
- `company_report_runs`
  - 실행 이력(배치키, 상태, 재실행 연결, 에러)
- `company_daily_prices` (선택 입력)
  - 종목별 OHLCV/수익률(있으면 intraday fallback보다 우선 사용)
- `company_investor_flows` (선택 입력)
  - 종목별 투자자 수급(있으면 시장레벨 수급보다 우선 사용)
- `company_financial_snapshots` (선택 입력)
  - 종목별 재무 스냅샷(있으면 mapping metadata보다 우선 사용)

## 3) Universe 편입/편집
회사 마스터(`companies`)를 기준으로 편입합니다.

### 방법 A. CLI로 편입
```bash
cd backend
python3 -m src.krx.source_ingestion.cli ensure-report-universe \
  --universe-key KRX_LARGE_CAP_CORE \
  --universe-name "KRX Large Cap Core" \
  --target-size 25 \
  --seed-stock-code 005930 \
  --seed-stock-code 000660

python3 -m src.krx.source_ingestion.cli sync-report-universe-members \
  --universe-key KRX_LARGE_CAP_CORE \
  --replace \
  --stock-code 005930 \
  --stock-code 000660 \
  --stock-code 035420
```

### 방법 B. Admin API로 편입
- `POST /api/krx/admin/company-reports/universes/{universe_key}/members`
  - query: `replace`, `stock_code`, `company_id`

### 조회
- `GET /api/krx/admin/company-reports/universes`
- `python3 -m src.krx.source_ingestion.cli list-report-universes`
- `python3 -m src.krx.source_ingestion.cli list-report-universe-members --universe-key KRX_LARGE_CAP_CORE`

## 4) 리포트 스키마(핵심)
`company_reports.report_payload_json`에는 아래 고정 섹션이 포함됩니다.

- `one_line_status`
- `recent_key_events`
- `flow_summary`
- `technical_context_summary`
- `bull_points`
- `bear_points`
- `watch_items`
- `confidence` (`score`, `bucket`, `rationale`)
- `source_coverage`

`company_report_sections`에도 동일 섹션을 분리 저장해 프론트/API에서 쉽게 조합할 수 있습니다.

## 5) 입력 데이터 조립 규칙
기존 저장 데이터를 우선 사용합니다.

- 가격 컨텍스트:
  - 우선: `company_daily_prices`
  - fallback: `market_intraday_snapshots` (종목코드 매칭 시)
- 수급 요약:
  - 우선: `company_investor_flows`
  - fallback: `market_daily_factors`
- 정규화 이벤트: `events` + `event_company_edges`
- 공시 요약: `raw_documents` (`provider='DART'`, `document_type='DISCLOSURE'`)
- 재무 스냅샷:
  - 우선: `company_financial_snapshots`
  - fallback: `company_source_mappings.source_metadata_json` 최신 KIS 메타

데이터가 누락되면 실패시키지 않고 coverage를 낮춰 fallback 리포트를 생성합니다.

## 6) LLM / Fallback 동작
- Provider 추상화: `disabled | openai_compatible`
- LLM 출력 계약(JSON) 파싱 실패/타임아웃 시 규칙 기반 fallback으로 전환
- 전환 시 run 상태는 `PARTIAL_SUCCESS`로 기록되고 `company_report_runs.error_message`에 사유가 남습니다.

주의:
- 본문 full-text 저장 없이 ID/URL/요약/스니펫 중심 메타만 유지
- 매수/매도/목표주가 등 직접 투자 조언 문구는 금지

## 7) 실행 명령
```bash
cd backend

# 유니버스 생성/시드
python3 -m src.krx.source_ingestion.cli ensure-report-universe --universe-key KRX_LARGE_CAP_CORE --target-size 25

# 야간 배치 생성
python3 -m src.krx.source_ingestion.cli generate-company-reports-nightly \
  --trade-date 2026-03-09 \
  --universe-key KRX_LARGE_CAP_CORE

# 단일 회사 재실행
python3 -m src.krx.source_ingestion.cli generate-company-report \
  --company-id 1 \
  --trade-date 2026-03-09 \
  --universe-key KRX_LARGE_CAP_CORE

# 실패 subset만 재실행
python3 -m src.krx.source_ingestion.cli rerun-failed-company-reports \
  --trade-date 2026-03-09 \
  --universe-key KRX_LARGE_CAP_CORE \
  --reference-batch-run-key 2026-03-09:KRX_LARGE_CAP_CORE:scheduled:abcd1234

# 조회
python3 -m src.krx.source_ingestion.cli latest-company-report --company-id 1 --universe-key KRX_LARGE_CAP_CORE
python3 -m src.krx.source_ingestion.cli company-report-history --company-id 1 --universe-key KRX_LARGE_CAP_CORE --limit 20
python3 -m src.krx.source_ingestion.cli latest-universe-reports --universe-key KRX_LARGE_CAP_CORE --limit 50
python3 -m src.krx.source_ingestion.cli list-company-report-runs --universe-key KRX_LARGE_CAP_CORE --limit 100

# 선택 입력 수동 적재(JSON)
python3 -m src.krx.source_ingestion.cli import-company-daily-prices --company-id 1 --input ./data/company_prices_005930.json --source-name MANUAL_IMPORT
python3 -m src.krx.source_ingestion.cli import-company-investor-flows --company-id 1 --input ./data/company_flows_005930.json --source-name MANUAL_IMPORT
python3 -m src.krx.source_ingestion.cli import-company-financial-snapshots --company-id 1 --input ./data/company_financials_005930.json --source-name MANUAL_IMPORT

# 선택 입력 조회
python3 -m src.krx.source_ingestion.cli list-company-daily-prices --company-id 1 --limit 20
python3 -m src.krx.source_ingestion.cli list-company-investor-flows --company-id 1 --limit 20
python3 -m src.krx.source_ingestion.cli list-company-financial-snapshots --company-id 1 --limit 20
```

## 8) 스케줄링
cron 예시는 `../scripts/krx-company-report.crontab.example`를 참고하세요.

권장:
- 평일 18:40 KST: nightly batch (`generate-company-reports-nightly`)
- 평일 19:10 KST: failed subset rerun (`rerun-failed-company-reports`)
