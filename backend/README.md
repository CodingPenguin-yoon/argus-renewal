# Backend

FastAPI 기반 KRX 백엔드입니다.

## 실행
```bash
cd backend
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 4000
```

환경 변수는 루트의 `.env.example`을 기준으로 관리합니다. 실제로 값을 넣을 때는 `backend/.env`를 쓰고, 섹터별 정리와 현재 필수값은 [doc/reference/env-by-sector.md](/Users/yoon/03_projects/05_economy_project/argus_renewal/doc/reference/env-by-sector.md)를 보면 됩니다.

## 핵심 API
- `GET /health`
- `GET /api/app/header?market=krx`
- `GET /api/news/dashboard`
- `GET /api/news/kr`
- `GET /api/news/global`
- `GET /api/news/disclosures`
- `GET /api/news/header-context`
- `GET /api/news/coverage`
- `GET /api/global-events/highlight`
- `GET /api/global-events/upcoming?window=24h`
- `GET /api/global-events/week`
- `GET /api/global-events/coverage`

KRX 라우트:
- `GET /api/krx/stocks`
- `GET /api/krx/stocks/{ticker}`
- `GET /api/krx/events/upcoming`
- `GET /api/krx/news`
- `GET /api/krx/news/top`
- `GET /api/krx/news/macro`
- `GET /api/krx/news/stock`
- `GET /api/krx/news/by-ticker/{ticker}`
- `GET /api/krx/news/{news_id}`
- `GET /api/krx/market-signal/summary`
- `GET /api/krx/market-signal/trends`
- `GET /api/krx/market-signal/components`
- `GET /api/krx/derivatives/summary`
- `GET /api/krx/derivatives/trends`
- `GET /api/krx/derivatives/investor-flow`
- `GET /api/krx/derivatives/briefing`
- `GET /api/krx/derivatives/coverage`

## KRX 뉴스 가공 레이어
- KRX 뉴스 탭은 `raw_documents`를 입력으로 받아 `news_batch_triage`, `market_surface_candidates`, `market_surface_state`, `market_surface_history`를 재생성하는 시장 표면 materialization을 사용합니다.
- `news_batch_triage`의 1차 판단은 기본 deterministic 경로로 채워지며, `NEWS_PRODUCT_BATCH_TRIAGE_*`를 켜면 짧은 뉴스 묶음을 OpenAI-compatible endpoint에 1회 보내는 batch triage로 업그레이드할 수 있습니다.
- 2차 AI는 `NEWS_PRODUCT_EDITORIAL_AI_*` 설정으로 켜지며, 상위 카드를 하나씩 enrich하는 대신 현재 표면과 top 후보 묶음을 1회 compare해서 `story_state`, `importance_label`, `editorial_reason`, `editorial_boost`를 적용합니다.
- `run-news-automation`은 여전히 `sync -> normalize -> refresh` 순서를 유지하지만, 기본 normalize는 `RAW_INGESTION_AUTOMATION_NORMALIZE_INCLUDE_LLM=false`라서 문서별 event LLM fan-out 없이 deterministic event freshness만 유지합니다.
- `/api/news/*`와 `/api/krx/news/*` 응답 계약은 유지하되, 내부 구현은 기존 `normalized_events`/`event_evidence`/`news_cards` 중심 경로 대신 새 시장 표면 테이블을 우선 사용합니다.
- 뉴스 탭 프런트는 `GET /api/news/dashboard`로 요약 카드, 공시 카드, 헤더 컨텍스트, 커버리지까지 한 번에 받아 새로고침 시 중복 왕복을 줄입니다.
- 구조와 파일 책임은 `doc/domains/news/source-map.md`, 변경 요약은 `doc/domains/news/rebuild-summary.md`를 참고합니다.

## 테스트
```bash
cd backend
pytest -q
```

## Provider Probe
```bash
cd backend
python3 -m src.krx.source_ingestion.cli probe-news-provider --provider BIGKINDS --query "반도체" --sample-limit 10
python3 -m src.krx.source_ingestion.cli probe-news-provider --provider NAVER_NEWS --query "반도체 증시" --sample-limit 10
python3 -m src.krx.source_ingestion.cli probe-trend-provider --provider NAVER_DATALAB --group "반도체=반도체,삼성전자" --sample-limit 10
```
