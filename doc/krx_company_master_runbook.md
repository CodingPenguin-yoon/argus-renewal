# KRX Company Master Runbook

## 목적
DART corp_code와 KIS 종목 마스터를 동기화한 뒤, 단일 canonical company로 매핑합니다.

## 사전 준비
1. `.env`에 DB 및 provider 환경 변수를 설정합니다.
2. DART는 `DART_SYNC_ENABLED=true` + `DART_API_KEY`가 필요합니다.
3. KIS는 `KIS_MASTER_PROVIDER=file` 또는 `api` 중 하나를 사용합니다.

## 실행 순서
```bash
cd backend
python3 -m src.krx.company_master.cli sync-dart
python3 -m src.krx.company_master.cli sync-kis
python3 -m src.krx.company_master.cli build-mapping
python3 -m src.krx.company_master.cli summary --recent-limit 20
python3 -m src.krx.company_master.cli export-unresolved --output ./data/unresolved_mappings.csv
python3 -m src.krx.company_master.cli list-unresolved --limit 200
python3 -m src.krx.company_master.cli list-manual-overrides --limit 200
```

## 미해결 건 처리
1. `unresolved_mappings.csv`에서 `mapping_status=CONFLICT`를 우선 확인합니다.
2. 운영자가 override를 추가합니다.
3. `build-mapping`을 재실행합니다.

```bash
python3 -m src.krx.company_master.cli add-manual-override \
  --source-system KIS \
  --source-record-id 005930 \
  --action MAP \
  --force-canonical-key manual:samsung \
  --force-canonical-name 삼성전자 \
  --note "ops confirmed"

python3 -m src.krx.company_master.cli import-manual-overrides \
  --input ./data/company_manual_overrides.csv \
  --created-by ops
```

## 안전 원칙
- ambiguous 매칭은 자동 병합하지 않고 `CONFLICT + needs_review=1`로 남깁니다.
- source 메타데이터(원천 시스템/ID/URL/스니펫)를 유지합니다.
