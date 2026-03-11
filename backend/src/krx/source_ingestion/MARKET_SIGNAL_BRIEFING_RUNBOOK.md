# KRX Market Signal Briefing Runbook

08:30 KST 프리마켓 브리핑(규칙 기반) 생성/조회/백테스트 운영 문서입니다.

## 1) 범위
- 시장: `KRX`
- 입력 데이터: 이미 적재된
  - `market_daily_factors`
  - `market_intraday_snapshots`
  - `derivatives_daily_metrics`
- 출력 데이터:
  - `market_briefings`
  - `market_signal_components`
  - `market_signal_backtests`

## 2) 스코어링 방식 (Deterministic)
아래 신호군을 규칙 기반으로 점수화합니다.
- 투자자 선물 수급 압력
- 미결제약정 변화 압력
- Put/Call 비율 압력
- 내재변동성 압력
- 신용잔고 추세 압력
- 야간선물 갭 시그널
- 글로벌 리스크 입력(선택, 데이터가 있을 때만 반영)

엔진은 다음을 산출합니다.
- `directional_bias`: `bullish | bearish | neutral`
- `gap_bias`: `gap_up | gap_down | flat`
- `volatility_bias`: `rising | stable | falling`
- `total_score`, `volatility_score`
- 컴포넌트별 점수/근거/소스 메타데이터
- 한국어 설명문 + Markdown 요약
- `confidence_bucket`: `low | medium | high`

모든 점수는 저장된 원천 지표를 기반으로 계산되며, 블랙박스 ML 모델을 사용하지 않습니다.

## 3) Threshold/가중치 설정 위치
환경변수:
- `MARKET_BRIEFING_SIGNAL_ENABLED`
- `MARKET_BRIEFING_SIGNAL_MARKET_SCOPE`
- `MARKET_BRIEFING_SIGNAL_RULES_JSON`

`MARKET_BRIEFING_SIGNAL_RULES_JSON`에 부분 override JSON을 넣으면 기본 규칙을 덮어쓸 수 있습니다.

예시:
```bash
export MARKET_BRIEFING_SIGNAL_RULES_JSON='{
  "classification": {
    "directional_bullish_cutoff": 1.2,
    "directional_bearish_cutoff": -1.2
  },
  "components": {
    "night_futures_gap_signal": {
      "gap_up_pct": 0.25,
      "gap_down_pct": -0.25,
      "weight": 1.2
    }
  }
}'
```

## 4) 로컬 실행
```bash
cd backend

# 1) 브리핑 생성 (기본 mode: MANUAL)
python3 -m src.krx.source_ingestion.cli generate-market-briefing --trade-date 2026-03-09

# 2) 과거일 재생성(덮어쓰기 upsert)
python3 -m src.krx.source_ingestion.cli generate-market-briefing --trade-date 2026-03-05 --mode BACKFILL

# 3) 단일 백테스트
python3 -m src.krx.source_ingestion.cli backtest-market-briefing --trade-date 2026-03-09

# 4) 기간 백테스트
python3 -m src.krx.source_ingestion.cli backtest-market-briefing-range --start-date 2026-03-01 --end-date 2026-03-09
```

## 5) API 조회/실행 (Admin)
- `POST /api/krx/admin/briefings/generate`
- `POST /api/krx/admin/briefings/backtest`
- `POST /api/krx/admin/briefings/backtest/range`
- `GET /api/krx/admin/briefings/latest`
- `GET /api/krx/admin/briefings/history`
- `GET /api/krx/admin/briefings/{trade_date}`
- `GET /api/krx/admin/briefings/{trade_date}/components`

`KRX_ADMIN_API_KEY`가 설정된 경우 `X-Admin-Key` 헤더가 필요합니다.

## 6) 운영 메모
- 생성/백테스트는 `trade_date` 기준 upsert로 idempotent 처리됩니다.
- 입력 지표가 일부 누락되면 해당 컴포넌트는 0점 + 설명문에 누락 근거를 남기고 전체 작업은 실패시키지 않습니다.
- 결과 문구에는 항상 아래 문구가 포함됩니다.
  - `본 브리핑은 정보 제공 목적이며 투자 성과를 보장하지 않습니다.`
