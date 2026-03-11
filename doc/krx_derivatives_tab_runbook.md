# KRX 파생(시장 신호 통합) Runbook

## 개요
파생 데이터(`derivatives_daily_metrics`, `market_intraday_snapshots`, `market_briefings`, `market_signal_components`)는 `시장 신호(/krx)` 내부 카드(`선물·옵션 신호`)의 근거로 사용합니다.

신규 수집 파이프라인을 만들지 않고, 기존 브리핑 입력/시그널 파이프라인 위에서 집계 API만 확장합니다.

## 데이터 소스

### 필수(최소 Level 1)
- `derivatives_daily_metrics`
  - `put_call_ratio`
  - `call_open_interest`
  - `put_open_interest`
  - `open_interest_total` (있으면 전일 대비 `oi_change` 계산)

### 선택(있으면 확장)
- `derivatives_daily_metrics`
  - 투자자 수급: `futures_investor_*`, `options_investor_*`
  - `implied_volatility`
  - `additional_metrics_json` 내 `call_notional`, `put_notional`, `participant_summary`, `expiry_summary` 등
- `market_intraday_snapshots`
  - `session_type='NIGHT_SESSION'`의 `change_rate`/`price`/`price_change`
- `market_briefings`, `market_signal_components`
  - 브리핑 엔진 생성 결과(있으면 우선 사용)

## 렌더링 레벨
- Level 1: 일간 요약만 있음
  - 요약 카드 + 트렌드 + 규칙 해설
- Level 2: 일간 요약 + 참여자 수급 있음
  - 참여자 섹션 추가
- Level 3: Level 2 + 만기/계약 상세 있음
  - 만기/계약 상세 패널 추가

## 공개 API
- `GET /api/krx/derivatives/summary?date=YYYY-MM-DD`
- `GET /api/krx/derivatives/trends?preset=20d`
- `GET /api/krx/derivatives/investor-flow?preset=20d`
- `GET /api/krx/derivatives/briefing?date=YYYY-MM-DD`
- `GET /api/krx/derivatives/coverage?date=YYYY-MM-DD`

응답에는 `source_coverage`와 `missing_fields`가 포함되어, 부분 실패/누락 시에도 화면이 깨지지 않도록 설계되어 있습니다.

## 로컬 실행
```bash
# backend
source .venv/bin/activate
pnpm dev:backend

# frontend
pnpm dev:frontend
```

브라우저 확인:
- `http://localhost:3000/krx`

## 백필 / 수동 입력
기존 수집 CLI를 그대로 사용합니다.

```bash
cd backend

# 파생 일간 참조지표 수집
python3 -m src.krx.source_ingestion.cli collect-briefing-eod --trade-date 2026-03-09

# 야간선물 스냅샷 수집
python3 -m src.krx.source_ingestion.cli collect-briefing-night --trade-date 2026-03-09

# 수동 파생 참조 입력(템플릿: doc/krx_derivatives_reference_manual_template.csv)
python3 -m src.krx.source_ingestion.cli import-briefing-krx-reference \
  --trade-date 2026-03-09 \
  --input ./data/krx_derivatives_2026-03-09.csv
```

## 누락 데이터 확인
```bash
# 집계 커버리지 확인
curl "http://localhost:4000/api/krx/derivatives/coverage?date=2026-03-09"

# 관리자 원시 입력 확인
curl "http://localhost:4000/api/krx/admin/briefing-inputs/derivatives-daily-metrics"
curl "http://localhost:4000/api/krx/admin/briefing-inputs/market-intraday-snapshots?session_type=NIGHT_SESSION"
```

## 해설 생성 원칙
- `market_briefings`가 있으면 해당 해설/바이어스를 우선 사용
- 없으면 결정론적 규칙 해석 사용:
  - Put/Call
  - Put/Call 변화
  - Call/Put OI
  - OI 변화
  - 외국인 선물 수급
  - 야간선물
  - IV(있을 때)
- 항상 정보 제공 목적 문구 포함(성과 보장 금지)

## 알려진 제한사항
- 옵션 체인/스트라이크 히트맵은 원천 데이터가 `additional_metrics_json`에 없으면 표시하지 않음
- `call_notional`, `put_notional`은 원천에 없으면 `null` + `missing_fields`로 노출
- 차트는 현재 최근 20세션(기본 `preset=20d`) 기반
