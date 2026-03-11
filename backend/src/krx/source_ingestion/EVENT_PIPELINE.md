# KRX Normalized Event Pipeline Runbook

KRX 공시/뉴스 원천 문서를 `normalized market event`로 변환하는 파이프라인입니다.

## 1) 목적
- 원천 문서(`raw_documents`)를 이벤트 단위로 정규화
- 이벤트와 회사 영향 관계를 `direct / indirect / theme` tier로 저장
- 신뢰도/확신도 기반 review queue 운영
- LLM을 parser/summarizer로만 사용하고, 사실 원천은 source data로 제한

## 2) 이벤트 Taxonomy
내부 key는 snake_case를 사용하고, UI 표시는 label을 사용합니다.

- `earnings`
- `guidance`
- `contract_order` (`contract/order`)
- `supply_customer` (`supply/customer`)
- `capex_factory` (`capex/factory`)
- `mna_investment` (`M&A/investment`)
- `shareholder_return`
- `financing`
- `regulation_policy` (`regulation/policy`)
- `product_launch`
- `management_change_of_control` (`management/change_of_control`)
- `legal_dispute` (`legal/dispute`)
- `accident_outage_incident` (`accident/outage/incident`)
- `macro_theme` (`macro/theme`)

## 3) DB Schema
마이그레이션: `src/krx/company_master/migrations/003_event_pipeline.sql`

- `events`
  - 이벤트 본문: `event_type`, `summary`, `sentiment`
  - source provenance: `primary_document_id`, `source_provider`, `source_url`, `canonical_url`, `metadata_json`
  - scoring: `trust_score`, `confidence`, `status`
  - legal-safe 메타: `provider_document_id`, `snippet`, URL/ID 중심 저장

- `event_company_edges`
  - `event_id` x `company_id`
  - `impact_tier` (`direct|indirect|theme`)
  - `reason`, `evidence_text`, `mapping_rule_source`, `confidence`

- `event_extractions`
  - raw 문서별 추출 감사 로그 (`raw_document_id` unique)
  - `extraction_method` (`LLM|FALLBACK_RULE|DETERMINISTIC_DART`)
  - `parse_status`, `input_hash`, `output_json`, `error_message`

- `event_review_queue`
  - 저신뢰 이벤트 검토 큐
  - `queue_status` (`PENDING|APPROVED|REJECTED`)
  - `review_reason`, `review_score`, `review_threshold`, reviewer 메타

## 4) Impact Tier Rules
- `direct`
  - DART filer/company mapping이 명확한 경우
  - 원문에서 명시적 주체 회사로 판단되는 경우
- `indirect`
  - 공급망/고객사/자회사/주주/경쟁 구문 등 관계 키워드 기반 연관
- `theme`
  - 섹터/정책/거시 테마 중심 연관으로 회사 직접 주체성이 약한 경우

모든 edge는 다음을 저장합니다.
- `confidence`
- `evidence_text`
- `mapping_rule_source`

## 5) LLM Output Contract
LLM 응답은 JSON only여야 하며, 필수 필드는 아래와 같습니다.

```json
{
  "event_type": "...",
  "summary": "...",
  "sentiment": "positive|negative|neutral|mixed",
  "companies": [
    {
      "company_id": 123,
      "impact_tier": "direct|indirect|theme",
      "reason": "...",
      "confidence": 0.0
    }
  ],
  "risk_flags": [],
  "confidence": 0.0
}
```

주의:
- LLM은 parser/summarizer 역할만 수행
- source data에 없는 사실을 생성하면 안 됨
- LLM 비활성 시 fallback rule path가 자동 사용됨

## 6) Accepted / Rejected Mapping Examples
### Accepted
- DART 공시 + filer 매핑 존재:
  - `삼성전자 사업보고서 제출`
  - 회사 edge: `삼성전자 / direct / reason=DART filer mapping`

- 뉴스 기사:
  - title: `삼성전자, SK하이닉스와 공급 계약 확대`
  - summary: `두산로보틱스는 정부 정책 테마 수혜 기대`
  - edge:
    - 삼성전자 `direct`
    - SK하이닉스 `indirect`
    - 두산로보틱스 `theme`

### Rejected (or queued)
- source가 discovery 뉴스이고 근거 문구가 약해 confidence 임계치 미달
- company mention이 없거나 모호하여 `no_company_mapping` risk flag가 발생
- review queue에서 운영자가 `reject` 결정

## 7) 운영 명령
```bash
cd backend
python3 -m src.krx.source_ingestion.cli normalize-events --limit 200
python3 -m src.krx.source_ingestion.cli normalize-events --limit 200 --no-llm
python3 -m src.krx.source_ingestion.cli list-event-review-queue --limit 100 --status PENDING
python3 -m src.krx.source_ingestion.cli review-event --event-id 12 --decision approve --reviewer ops --note "validated"
```

## 8) API
- `GET /api/krx/news/events/recent`
- `GET /api/krx/news/events/company/{company_id}`
- `POST /api/krx/admin/events/sync`
- `GET /api/krx/admin/events/review-queue`
- `POST /api/krx/admin/events/review-queue/{event_id}/approve`
- `POST /api/krx/admin/events/review-queue/{event_id}/reject`

관리 endpoint 인증:
- `KRX_ADMIN_API_KEY`가 설정되어 있으면 `/api/krx/admin/events/*` 요청은 `X-Admin-Key` 헤더가 필요합니다.
- 미설정 시 로컬 개발 편의를 위해 인증이 비활성화됩니다.

## 9) Idempotency / Rerun
- 원천 문서 단위 dedup key로 event upsert
- `event_extractions.raw_document_id` unique로 중복 추출 방지
- low-confidence 기준 재평가 시 review queue upsert
- duplicate raw 문서(`is_duplicate=1`)는 정규화 대상에서 제외

## 10) Scheduler
- raw ingestion cron 예시: `../scripts/krx-raw-ingestion.crontab.example`
- event normalization cron 예시: `../scripts/krx-event-pipeline.crontab.example`
