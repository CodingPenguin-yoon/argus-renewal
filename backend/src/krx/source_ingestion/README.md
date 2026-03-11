# KRX Raw Source Ingestion Runbook

KRX 뉴스/공시 소스 수집 레이어입니다.
이 모듈은 2단계로 구성됩니다.
- 1단계: `raw_documents` 중심 원천 메타데이터 수집
- 2단계: 정규화 이벤트 변환/회사 영향도 매핑/리뷰 큐 운영

프리마켓 브리핑 입력(수급/파생 지표) 수집 runbook은 `MARKET_BRIEFING_RUNBOOK.md`를 참고하세요.
프리마켓 브리핑 신호 생성/백테스트 runbook은 `MARKET_SIGNAL_BRIEFING_RUNBOOK.md`를 참고하세요.
회사 리포트(대형주 유니버스) runbook은 `COMPANY_REPORT_RUNBOOK.md`를 참고하세요.

## 1) 목적
- DART 공시 메타데이터 수집
- BigKinds 뉴스 메타데이터 수집
- Naver 뉴스 discovery/candidate 메타데이터 수집
- 중복키/중복관계 감사 추적

## 2) 주요 테이블
- `raw_documents`
- `raw_document_sources`
- `raw_document_fetch_runs`
- `raw_document_dedup_keys`
- `events`
- `event_company_edges`
- `event_extractions`
- `event_review_queue`

정규화 이벤트 스키마/LLM 계약/impact tier 상세는 `EVENT_PIPELINE.md`를 참고하세요.

## 3) Provider별 저장 필드

### DART
- 정규화 필드: `provider`, `provider_document_id(rcept_no)`, `document_type`, `title(report_nm)`, `source_url`, `receipt_at`, `published_at`, `company_id(매핑 가능 시)`, `company_ref`
- 소스 전용 필드: `provider_metadata_json(corp_code/corp_name/corp_cls/flr_nm/rcept_dt/rm)`, `raw_payload_json`
- Dedup: `PROVIDER_ID` + `rcept_no`

### BigKinds
- 정규화 필드: `title`, `publisher`, `published_at`, `source_url/canonical_url`, `summary(snippet)`, `query_text`
- 소스 전용 필드: `provider_metadata_json(query/published_raw/provider_document_id)`, `raw_payload_json(허용 메타데이터 키만 저장)`
- 본문(Full Text)은 저장하지 않음
- Dedup: `NEWS_URL_TITLE` (canonical URL + normalized title hash)
- 응답 변형 대응: `documents/items/news/data/result/return_object` 계층에서 문서 배열 탐색

### Naver News
- 정규화 필드: `title`, `source_url(originallink/link)`, `canonical_url`, `publisher(응답값 우선, 없으면 host 기반 매체명 정규화)`, `published_at(pubDate 파싱)`, `summary(description)`, `query_text`
- 소스 전용 필드: `provider_metadata_json(query/originallink/link/pub_date_raw)`, `raw_payload_json(허용 메타데이터 키만 저장)`
- canonical truth source가 아닌 discovery/candidate 용도
- Dedup: `NEWS_URL_TITLE` (canonical URL + normalized title hash)

## 4) 필수 환경 변수

### 공통
- `DB_PATH`
- `RAW_INGESTION_TIMEOUT_SECONDS`
- `RAW_INGESTION_MAX_RETRIES`
- `RAW_INGESTION_BACKOFF_SECONDS`

### DART
- `DART_API_KEY`
- `DART_DISCLOSURE_LIST_URL`
- `DART_DISCLOSURE_PAGE_COUNT`

### BigKinds
- `BIGKINDS_NEWS_ENABLED`
- `BIGKINDS_API_KEY` (enabled일 때 필수)
- `BIGKINDS_BASE_URL`
- `BIGKINDS_SEARCH_PATH`
- `BIGKINDS_PAGE_SIZE`
- `BIGKINDS_PAGE_LIMIT`

### Naver News
- `NAVER_NEWS_ENABLED`
- `NAVER_NEWS_CLIENT_ID` (enabled일 때 필수)
- `NAVER_NEWS_CLIENT_SECRET` (enabled일 때 필수)
- `NAVER_NEWS_BASE_URL`
- `NAVER_NEWS_SEARCH_PATH`
- `NAVER_NEWS_DISPLAY`
- `NAVER_NEWS_PAGE_LIMIT`
- `NAVER_NEWS_COMPANY_QUERY_TEMPLATE`
- `NAVER_NEWS_THEME_QUERY_TEMPLATE`
- `RAW_INGESTION_SCHEDULE_DAYS`
- `RAW_INGESTION_SCHEDULE_INCLUDE_DART`
- `RAW_INGESTION_SCHEDULE_INCLUDE_COMPANY_NEWS`
- `RAW_INGESTION_SCHEDULE_INCLUDE_THEME_NEWS`
- `RAW_INGESTION_SCHEDULE_COMPANY_IDS` (comma separated IDs)
- `RAW_INGESTION_SCHEDULE_COMPANY_NAMES` (comma separated names)
- `RAW_INGESTION_SCHEDULE_THEME_KEYWORDS` (comma separated keywords)

### Event Pipeline
- `EVENT_PIPELINE_ENABLED`
- `EVENT_PIPELINE_BATCH_SIZE`
- `EVENT_PIPELINE_LOW_CONFIDENCE_THRESHOLD`
- `EVENT_PIPELINE_INCLUDE_LLM`
- `EVENT_PIPELINE_LLM_ENABLED`
- `EVENT_PIPELINE_LLM_PROVIDER`
- `EVENT_PIPELINE_LLM_BASE_URL`
- `EVENT_PIPELINE_LLM_API_KEY`
- `EVENT_PIPELINE_LLM_MODEL`
- `EVENT_PIPELINE_LLM_TIMEOUT_SECONDS`
- `EVENT_PIPELINE_LLM_MAX_RETRIES`
- `EVENT_PIPELINE_LLM_BACKOFF_SECONDS`
- `KRX_ADMIN_API_KEY` (설정 시 `/api/krx/admin/events/*`는 `X-Admin-Key` 헤더 필수)

### Company Report Pipeline
- `COMPANY_REPORT_PIPELINE_ENABLED`
- `COMPANY_REPORT_MARKET_SCOPE`
- `COMPANY_REPORT_UNIVERSE_KEY`
- `COMPANY_REPORT_UNIVERSE_NAME`
- `COMPANY_REPORT_UNIVERSE_TARGET_SIZE`
- `COMPANY_REPORT_SEED_STOCK_CODES`
- `COMPANY_REPORT_EVENT_LOOKBACK_DAYS`
- `COMPANY_REPORT_DISCLOSURE_LOOKBACK_DAYS`
- `COMPANY_REPORT_PRICE_LOOKBACK_DAYS`
- `COMPANY_REPORT_LLM_ENABLED`
- `COMPANY_REPORT_LLM_PROVIDER`
- `COMPANY_REPORT_LLM_BASE_URL`
- `COMPANY_REPORT_LLM_API_KEY`
- `COMPANY_REPORT_LLM_MODEL`
- `COMPANY_REPORT_LLM_TIMEOUT_SECONDS`
- `COMPANY_REPORT_LLM_MAX_RETRIES`
- `COMPANY_REPORT_LLM_BACKOFF_SECONDS`

## 5) 로컬 실행 명령

```bash
cd backend
python3 -m src.krx.source_ingestion.cli sync-dart --days 1
python3 -m src.krx.source_ingestion.cli sync-news-companies --company-id 1 --days 1
python3 -m src.krx.source_ingestion.cli sync-news-themes --keyword "반도체" --days 1
python3 -m src.krx.source_ingestion.cli backfill --start-date 2026-03-01 --end-date 2026-03-09 --provider-scope all --company-id 1 --keyword "금리"
python3 -m src.krx.source_ingestion.cli sync-scheduled
python3 -m src.krx.source_ingestion.cli normalize-events --limit 200
python3 -m src.krx.source_ingestion.cli normalize-events --limit 200 --no-llm
python3 -m src.krx.source_ingestion.cli list-event-review-queue --limit 100 --status PENDING
python3 -m src.krx.source_ingestion.cli review-event --event-id 12 --decision approve --reviewer ops --note "validated"
python3 -m src.krx.source_ingestion.cli ensure-report-universe --universe-key KRX_LARGE_CAP_CORE --target-size 25
python3 -m src.krx.source_ingestion.cli generate-company-reports-nightly --trade-date 2026-03-09 --universe-key KRX_LARGE_CAP_CORE
python3 -m src.krx.source_ingestion.cli generate-company-report --company-id 1 --trade-date 2026-03-09 --universe-key KRX_LARGE_CAP_CORE
python3 -m src.krx.source_ingestion.cli rerun-failed-company-reports --trade-date 2026-03-09 --universe-key KRX_LARGE_CAP_CORE
python3 -m src.krx.source_ingestion.cli import-company-daily-prices --company-id 1 --input ./data/company_prices_005930.json --source-name MANUAL_IMPORT
python3 -m src.krx.source_ingestion.cli import-company-investor-flows --company-id 1 --input ./data/company_flows_005930.json --source-name MANUAL_IMPORT
python3 -m src.krx.source_ingestion.cli import-company-financial-snapshots --company-id 1 --input ./data/company_financials_005930.json --source-name MANUAL_IMPORT
```

`sync-scheduled` 동작:
- `RAW_INGESTION_SCHEDULE_*` 환경변수로 대상/범위를 읽어 incremental sync를 실행
- run 중 하나라도 `FAILED`면 프로세스 exit code를 `1`로 종료 (cron/alert 연동용)
- `SKIPPED_DISABLED`(credential/flag 미설정)는 실패로 간주하지 않음

## 6) 권장 스케줄
- DART disclosures: 10~20분 간격 incremental
- BigKinds/Naver theme sync: 30분 간격 incremental
- BigKinds/Naver company sync: 30분 간격 incremental
- 통합 배치: cron에서 `sync-scheduled`를 10~30분 간격 호출
- backfill: 필요 시 수동 실행

예시 crontab:
- `../scripts/krx-raw-ingestion.crontab.example`
- `../scripts/krx-event-pipeline.crontab.example`
- `../scripts/krx-company-report.crontab.example`

## 7) 장애/비활성 동작
- BigKinds/Naver가 비활성 또는 자격 증명 누락이면 fetch run 상태를 `SKIPPED_DISABLED`로 기록
- malformed payload는 run 상태를 `FAILED`로 기록하고 `error_message`에 원인 저장
