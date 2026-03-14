# KRX Raw Source Ingestion Runbook

KRX 뉴스/공시 소스 수집 레이어입니다.
이 모듈은 2단계로 구성됩니다.
- 1단계: `raw_documents` 중심 원천 메타데이터 수집
- 2단계: 정규화 이벤트 변환/회사 영향도 매핑/리뷰 큐 운영

프리마켓 브리핑 입력(수급/파생 지표) 수집 runbook은 `MARKET_BRIEFING_RUNBOOK.md`를 참고하세요.
프리마켓 브리핑 신호 생성/백테스트 runbook은 `MARKET_SIGNAL_BRIEFING_RUNBOOK.md`를 참고하세요.
회사 리포트(대형주 유니버스) runbook은 `COMPANY_REPORT_RUNBOOK.md`를 참고하세요.

## 1) 목적
- DART 핵심 공시 메타데이터 수집
- MK RSS 뉴스 메타데이터 수집
- Naver 뉴스 discovery/candidate 메타데이터 수집
- 중복키/중복관계 감사 추적

## 2) 주요 테이블
- `raw_documents`
- `raw_document_sources`
- `raw_document_fetch_runs`
- `raw_document_dedup_keys`
- `publisher_registry`
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
- 기본값은 `material_only=true`
- 기본 include 예시: `사업/반기/분기보고서`, `매출액또는손익구조 변동`, `최대주주변경`, `증자/사채/감자`, `단일판매ㆍ공급계약`, `소송/회생/영업정지`
- 기본 exclude 예시: `주주총회소집공고`, `주주총회소집결의`, `의결권대리행사권유참고서류`, `감사보고서제출`, `효력발생안내`

### MK RSS
- 정규화 필드: `title`, `publisher`, `publisher_key`, `published_at`, `observed_at`, `published_at_source`, `source_url/canonical_url`, `summary(description)`, `query_text`
- 소스 전용 필드: `provider_metadata_json(feed_url/feed_title/category/pub_date_raw/image_url)`, `raw_payload_json(no/title/link/category/author/pubDate/description)`
- 기본 피드: 매일경제 경제/증권 RSS
- query는 RSS 내 `title/description/category` 로컬 필터에 사용
- Dedup: `NEWS_URL_TITLE` (canonical URL + normalized title hash)

### Naver News
- 정규화 필드: `title`, `source_url(originallink/link)`, `canonical_url`, `publisher(응답값 우선, 없으면 host 기반 매체명 정규화)`, `publisher_key`, `published_at(pubDate 파싱)`, `observed_at`, `published_at_source`, `summary(description)`, `query_text`
- 소스 전용 필드: `provider_metadata_json(query/originallink/link/pub_date_raw)`, `raw_payload_json(허용 메타데이터 키만 저장)`
- canonical truth source가 아닌 discovery/candidate 용도
- Dedup: `NEWS_URL_TITLE` (canonical URL + normalized title hash)

### Publisher Registry
- `publisher_registry`는 실제 기사 발행 매체 축을 관리한다.
- 예시:
  - `provider = NAVER_NEWS`
  - `publisher = 매일경제`
  - `publisher_key = 매일경제`
- 즉 provider와 publisher는 같은 값이 아닐 수 있다.

### 시간 필드 규칙
- `published_at`: 원문 provider가 준 발행 시각
- `observed_at`: Argus가 그 문서를 처음 본 시각
- `published_at_source`: `PROVIDER`, `RECEIPT_AT`, `OBSERVED_AT`, `UNKNOWN`
- 뉴스는 `published_at`이 비어도 `observed_at`은 항상 채운다.
- 뉴스 화면 정렬과 evidence 시간은 `published_at`이 없을 때 `observed_at`을 fallback으로 사용한다.

## 4) 필수 환경 변수

### 공통
- `DB_PATH`
- `RAW_INGESTION_TIMEOUT_SECONDS`
- `RAW_INGESTION_MAX_RETRIES`
- `RAW_INGESTION_BACKOFF_SECONDS`
- `RAW_INGESTION_DESCRIPTOR_FACTORY_PATHS` (comma separated dotted paths or `module:callable`, extra descriptor factories)
- `MK_RSS_ENABLED`
- `MK_RSS_FEED_URLS` (comma separated RSS feed URLs)

### DART
- `DART_API_KEY`
- `DART_DISCLOSURE_LIST_URL`
- `DART_DISCLOSURE_PAGE_COUNT`
- `DART_MATERIAL_ONLY`
- `DART_MATERIAL_INCLUDE_PATTERNS` (comma separated, 비어 있으면 기본 allowlist 사용)
- `DART_MATERIAL_EXCLUDE_PATTERNS` (comma separated, 비어 있으면 기본 denylist 사용)

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
- `RAW_INGESTION_SCHEDULE_DISCLOSURE_PROVIDERS` (comma separated provider keys, legacy `INCLUDE_DART`보다 우선)
- `RAW_INGESTION_SCHEDULE_COMPANY_NEWS_PROVIDERS` (comma separated provider keys)
- `RAW_INGESTION_SCHEDULE_THEME_NEWS_PROVIDERS` (comma separated provider keys)
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
python3 -m src.krx.source_ingestion.cli list-ingestion-providers
python3 -m src.krx.source_ingestion.cli backfill-publishers
python3 -m src.krx.source_ingestion.cli sync-dart --days 1
python3 -m src.krx.source_ingestion.cli sync-disclosures --provider DART --days 1
python3 -m src.krx.source_ingestion.cli sync-news-companies --company-id 1 --days 1
python3 -m src.krx.source_ingestion.cli sync-news-themes --keyword "반도체" --days 1
python3 -m src.krx.source_ingestion.cli sync-news --provider MK_RSS --scope themes --keyword "금리" --days 1
python3 -m src.krx.source_ingestion.cli probe-news-provider --provider MK_RSS --query "금리" --sample-limit 10
python3 -m src.krx.source_ingestion.cli probe-news-provider --provider NAVER_NEWS --query "반도체 증시" --sample-limit 10
python3 -m src.krx.source_ingestion.cli probe-trend-provider --provider NAVER_DATALAB --group "반도체=반도체,삼성전자" --sample-limit 10
python3 -m src.krx.source_ingestion.cli backfill --start-date 2026-03-01 --end-date 2026-03-09 --provider-scope all --company-id 1 --keyword "금리"
python3 -m src.krx.source_ingestion.cli sync-scheduled
python3 -m src.krx.source_ingestion.cli run-news-automation
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
- provider CSV 설정이 있으면 legacy boolean보다 우선해서 해당 provider만 실행
- run 중 하나라도 `FAILED`면 프로세스 exit code를 `1`로 종료 (cron/alert 연동용)
- `SKIPPED_DISABLED`(credential/flag 미설정)는 실패로 간주하지 않음

`run-news-automation` 동작:
- 1분 cron tick에서 호출하는 canonical wrapper command다.
- `RAW_INGESTION_AUTOMATION_*` 환경변수로 KRX 세션 phase와 cadence를 계산한다.
- 장중(09:00~15:30, Mon-Fri)은 매 분 실행, 장 마감 후(15:30~18:00)는 5분 cadence, 그 외 시간/주말은 10분 cadence로 내부 skip 또는 실행을 결정한다.
- due tick이면 `sync-scheduled`와 같은 raw sync 범위를 실행한 뒤, event pipeline이 enabled일 때 정규화를 돌리고, 마지막에 news product materialization refresh를 강제로 수행한다.
- due가 아니면 `SKIPPED_CADENCE` JSON만 출력하고 종료한다.

read-only probe 동작:
- `probe-news-provider`는 `MK_RSS`, `NAVER_NEWS`를 직접 호출하고 DB에는 아무것도 쓰지 않는다.
- `probe-trend-provider`는 `NAVER_DATALAB` 점수 응답만 확인하며 기사 row를 만들지 않는다.
- 두 명령 모두 기본 샘플 출력은 최대 10건이며, credential 누락 시 `SKIPPED_DISABLED`를 반환한다.

descriptor factory 확장:
- `RAW_INGESTION_DESCRIPTOR_FACTORY_PATHS`에 callable 경로를 넣으면 factory가 extra descriptor를 로드한다.
- callable 시그니처는 `factory(settings) -> RawIngestionFactoryExtension | dict | None`
- 반환 payload는 `news` / `disclosures` 또는 `news_provider_descriptors` / `disclosure_provider_descriptors` 키를 사용할 수 있다.

publisher backfill:
- `backfill-publishers`는 기존 raw 문서에서 `publisher_key`가 비어 있는 행을 채우고 `publisher_registry`를 만든다.
- `--all`을 주면 이미 key가 있는 행도 다시 스캔한다.

## 6) 권장 스케줄
- DART disclosures: 10~20분 간격 incremental
- MK RSS theme sync: 15~30분 간격 incremental
- BigKinds/Naver theme sync: 30분 간격 incremental
- BigKinds/Naver company sync: 30분 간격 incremental
- 통합 배치: cron에서 `run-news-automation`을 1분 간격 호출하고, command 내부에서 세션별 cadence로 실제 실행 빈도를 낮춘다.
- backfill: 필요 시 수동 실행

예시 crontab:
- `../scripts/krx-raw-ingestion.crontab.example`
- `../scripts/krx-event-pipeline.crontab.example`
- `../scripts/krx-company-report.crontab.example`

## 7) 장애/비활성 동작
- MK RSS/BigKinds/Naver가 비활성 또는 자격 증명 누락이면 fetch run 상태를 `SKIPPED_DISABLED`로 기록
- malformed payload는 run 상태를 `FAILED`로 기록하고 `error_message`에 원인 저장
