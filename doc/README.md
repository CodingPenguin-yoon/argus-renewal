# Documentation Index

`doc/`는 `architecture`, `domains`, `plans`, `reference`, `troubleshooting` 다섯 축으로 정리합니다.

## 먼저 읽을 문서
1. `architecture/README.md`
2. `architecture/implementation-status.md`
3. `architecture/system-map.md`
4. `architecture/project-structure.md`
5. `architecture/krx-mvp-ia.md`
6. 작업 대상 도메인의 `domains/` 문서
7. 변경 배경을 쉬운 말로 보려면 `troubleshooting/README.md`

## 폴더 구조
- `architecture/`
  - 현재 코드베이스 기준 사실 문서
  - 구현 상태, 시스템 맵, 프로젝트 구조, IA 정책을 여기서 먼저 확인합니다.
- `domains/`
  - 특정 도메인을 깊게 파는 문서와 도메인별 운영 메모를 함께 둡니다.
- `plans/`
  - 남은 작업, 해결 로그, 과거 계획과 레거시 가이드를 둡니다.
- `reference/`
  - 데이터 모델, provider 설계, 리스크, 템플릿, Codex 참고자료를 둡니다.
- `troubleshooting/`
  - 비전공자도 읽을 수 있는 작업 설명과 점검 가이드를 둡니다.

## 아키텍처 문서
- `architecture/README.md`
- `architecture/implementation-status.md`
- `architecture/system-map.md`
- `architecture/project-structure.md`
- `architecture/krx-mvp-ia.md`

## 도메인 심화 문서
- `domains/news/README.md`
- `domains/news/source-map.md`
- `domains/news/pipeline.md`
- `domains/news/ingestion-automation.md`
- `domains/news/materialization.md`
- `domains/news/api-layers.md`
- `domains/news/frontend-surface.md`
- `domains/news/database-tables.md`
- `domains/news/file-reference.md`
- `domains/news/rebuild-summary.md`

## 도메인 문서
- `domains/news/README.md`
- `domains/news/runbook.md`
- `domains/macro-calendar/runbook.md`
- `domains/derivatives/runbook.md`
- `domains/company-master/runbook.md`

## 계획 및 추적 문서
- `plans/README.md`
- `plans/current-status.md`
- `plans/open-items.md`
- `plans/kis-fred-rollout-plan.md`
- `plans/resolved-log.md`
- `plans/archive/`
- `plans/legacy-guides/`
- `plans/logs/`

## 참고 자료
- `reference/domain-oriented-data-model.md`
- `reference/env-by-sector.md`
- `reference/provider-flexibility-design.md`
- `reference/kis-fred-integration-contract.md`
- `reference/risk-priority.md`
- `reference/codex-multi-agent-prompts.md`
- `reference/krx-derivatives-reference-manual-template.csv`

## 쉬운 설명 문서
- `troubleshooting/README.md`
- `troubleshooting/navigation-and-ia.md`
- `troubleshooting/performance-and-prefetch.md`
- `troubleshooting/dashboard-and-insights.md`
- `troubleshooting/routing-and-links.md`
- `troubleshooting/docs-and-history.md`

## 유지 규칙
- 현재 구조가 바뀌면 `architecture/system-map.md`와 `architecture/project-structure.md`를 같이 갱신합니다.
- 작업을 시작하거나 닫을 때는 `plans/current-status.md`, `plans/open-items.md`, `plans/resolved-log.md` 중 필요한 문서를 같이 갱신합니다.
- 현재 기준 문서와 과거 계획 문서를 섞지 않습니다. 현재 사실은 `architecture/`와 `domains/`에, 과거 기록은 `plans/archive/`와 `plans/legacy-guides/`에 둡니다.
