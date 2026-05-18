# Session-aware Collector Plan

## Goal

Argus v2 수집을 데이터 성격별로 분리합니다.

- 파생/옵션/현물 반응은 KRX 세션에 맞춰 수집합니다.
- 뉴스/DART/매크로는 휴일과 장외에도 계속 수집합니다.
- 야간 파생 세션은 1차 구현에서는 꺼두되, 저장/수집 계약은 야간 세션을 받을 수 있게 둡니다.

## Scope

### Phase 1

- `regular`, `night`, `closed` 세션 판정 유틸을 추가합니다.
- 정규장 market collector는 세션이 열렸을 때만 기존 KIS/context 수집 함수를 호출합니다.
- 장외/휴장에는 외부 market API를 반복 호출하지 않고 collector 결과를 `skipped`로 반환합니다.
- news collector는 세션과 무관하게 실행할 수 있게 분리합니다.
- CLI에 `collect-once`를 추가해 cron, launchd, 수동 테스트가 같은 경로를 쓰게 합니다.

### Phase 2

- `collect-loop` 반복 모드를 추가합니다.
- provider health에 `market_closed`, `last_success_at`, `next_scheduled_run`을 더 명확히 노출합니다.
- 원천 뉴스 feed도 DB 저장형으로 옮깁니다.

### Phase 3

- `ARGUS_COLLECTOR_NIGHT_MARKET_ENABLED=true`로 야간 파생 수집을 활성화합니다.
- 야간 파생은 정규장 판단과 분리해 `night session read`와 `next open setup`으로 표시합니다.
- 야간 뉴스와 야간 파생을 다음 정규장 장전 컨텍스트에 연결합니다.

## Session Rules

시간 기준은 KST입니다.

- 정규 파생 세션: 기본 08:40-15:50 수집 창.
- 현물 반응: 정규 market collector 안에서 기존 provider 설정을 따릅니다.
- 야간 파생 세션: 기본 17:50-06:05 수집 창, 1차에서는 disabled.
- 뉴스: 24시간 수집 가능.

야간 세션은 자정을 넘기므로 `snapshot_time`, `session_type`, `trading_date`를 분리해서 다룹니다.

## Collector Commands

```bash
cd backend
python3 -m src.argus_v2.cli collect-once
python3 -m src.argus_v2.cli collect-once --market-only
python3 -m src.argus_v2.cli collect-once --news-only
python3 -m src.argus_v2.cli collect-once --force-market
python3 -m src.argus_v2.cli collect-loop --interval-seconds 60
```

## Initial Defaults

- 정규장 market 수집: enabled.
- 야간 market 수집: disabled.
- 뉴스 수집: enabled.
- 장외 market 수집: skipped.
- 휴장일 market 수집: skipped.
