# Backend

FastAPI 기반 KRX 백엔드입니다.

## 실행
```bash
cd backend
python3 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 4000
```

## 핵심 API
- `GET /health`
- `GET /api/app/header?market=krx`
- `GET /api/news/kr`
- `GET /api/news/global`
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
