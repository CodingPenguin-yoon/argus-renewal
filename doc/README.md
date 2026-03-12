# Documentation Index

이 디렉터리는 현재 코드 기준 문서와 운영 런북을 함께 모아둔 곳입니다.

## 읽는 순서
1. `architecture/current-system-map.md`
2. `architecture/domain-oriented-data-model.md`
3. `PROJECT_STRUCTURE.md`
4. `analysis/risk-priority.md`
5. 작업 대상에 맞는 런북
6. Codex 운영이 필요하면 `codex_multi_agent_prompts.md`

## 현재 구조 문서
- `architecture/current-system-map.md`: 실제 런타임 진입점, 주요 실행 경로, 프런트와 백엔드 연결 지점
- `architecture/domain-oriented-data-model.md`: 도메인/프로바이더/퍼블리셔 축 기준으로 본 추천 데이터 모델
- `architecture/provider-flexibility-design.md`: provider 추가/교체를 전제로 한 뉴스/공시 파이프라인 유연화 설계안
- `PROJECT_STRUCTURE.md`: 현재 리포지토리의 디렉터리 구조와 역할 요약
- `analysis/risk-priority.md`: 문제 가능성이 높은 영역을 우선순위로 정리한 점검 가이드

## 제품 및 운영 런북
- `krx_mvp_ia_runbook.md`: KRX MVP 정보 구조와 탭 정책
- `krx_news_tab_runbook.md`: 뉴스 탭 운영 메모
- `krx_global_events_tab_runbook.md`: 글로벌 이벤트 탭 운영 메모
- `krx_derivatives_tab_runbook.md`: 파생상품 탭 운영 메모
- `krx_company_master_runbook.md`: 회사 마스터 및 매핑 운영 메모
- `krx_3axis_api_implementation_plan.md`: 3축 API 구현 계획
- `krx_derivatives_reference_manual_template.csv`: 파생상품 기준 데이터 수기 템플릿

## Codex 운영
- `codex_multi_agent_prompts.md`: parent session에서 바로 붙여 넣는 멀티 에이전트 프롬프트 모음

## 문서 원칙
- 구조 판단은 오래된 설명보다 실제 코드와 테스트를 우선한다.
- 문서가 코드와 어긋나면 `architecture/current-system-map.md`와 `PROJECT_STRUCTURE.md`를 먼저 갱신한다.
- 운영 리스크는 `analysis/risk-priority.md`에 누적한다.
