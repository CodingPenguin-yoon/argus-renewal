# Plans And Tracking Guide

`plans/`는 현재 작업 상태와 남은 일, 해결 로그, 과거 계획 문서를 함께 관리하는 공간입니다.

## 문서 역할
- `open-items.md`
  - 남은 작업의 source-of-truth
- `resolved-log.md`
  - 해결된 변경의 날짜순 로그
- `current-status.md`
  - 지금 기준 한 장 요약
- `kis-fred-rollout-plan.md`
  - 다음 라운드의 KIS/FRED 연동 실행 계획
- `archive/`
  - 과거 계획 문서
- `legacy-guides/`
  - 현재 사실 문서로 쓰지 않는 오래된 학습 가이드
- `logs/`
  - 문서가 아닌 과거 산출물

## 주의
- `archive/`와 `legacy-guides/`는 과거 기록 보관 영역이라 예전 용어와 예전 경로가 남아 있을 수 있습니다.
- 현재 사실 확인은 항상 `../architecture/`와 활성 `../domains/` 문서를 우선합니다.

## 갱신 규칙
- 사용자 표면이나 시스템 구조가 바뀌면 `current-status.md`를 먼저 갱신합니다.
- 남은 작업의 우선순위나 상태가 바뀌면 `open-items.md`를 갱신합니다.
- 실제 구현이 끝나면 `resolved-log.md`에 날짜, 변경 요약, 영향 문서를 추가합니다.
- `architecture/` 문서와 `plans/` 문서가 서로 모순되면 `architecture/`를 사실 기준으로 보고 `plans/`를 수정합니다.
