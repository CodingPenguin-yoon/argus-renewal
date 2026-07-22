# 구현 계획: Argus v2 레거시 정리와 제거

- 상태: `APPROVED`
- 날짜: `2026-07-21`
- 관련 요구사항: `project-docs/specifications/project-specification.md`
- 관련 ADR: `project-docs/decisions/ADR-002-clean-rebuild-with-selective-legacy-extraction.md`
- 승인자: 사용자

## 1. 위험도

- 분류: `HIGH`
- 판단 근거: 기존 공동 문서와 이후 애플리케이션·테스트·migration을 제거하며, 현재 worktree에 사용자 변경이 함께 존재한다.
- 실패 영향: KIS 요청 규칙과 fixture, 기존 실행 방법, 복구 근거 또는 사용자 변경을 잃을 수 있다.
- 되돌리기 어려운 부분: untracked 또는 ignored 파일은 Git으로 복구할 수 없고, 레거시 코드를 새 테스트 자산 추출 전에 삭제하면 검증 근거가 사라진다.

## 2. 확인한 현재 상태

- 기존 문서: `doc/` 26개 파일, `README.md`, `RUN_GUIDE.md`, backend·frontend README가 Argus v2 제품과 `/argus`·`/api/argus/v2/*`를 설명한다.
- 기존 코드: `backend/src/argus_v2/`, `frontend/src/argus_v2/`, `frontend/src/app/argus/`가 현재 실행 경로다.
- 기존 테스트: KIS 인증, provider mapping, redaction, collector lease, 옵션 fixture와 함께 폐기 대상인 뉴스·AI·judgement 테스트가 섞여 있다.
- 외부 참조: root·backend·frontend README, `package.json`, `.env.example`, `scripts/argus-v2-kis-smoke.crontab.example`, frontend root route가 레거시 경로를 참조한다.
- 로컬 민감·운영 파일 검사: 실제 `.env`, token cache, 운영 DB는 발견되지 않았다. `.tmp/codex-tmp/` 아래 약 20MB, 62개 tracked 생성형 pytest 산출물만 발견했다.
- 현재 사용자 변경: `.codex/`, `.ralph/`, `.serena/`, `agent.md`, `AGENTS.md` 관련 변경은 이 계획에서 수정하거나 복구하지 않는다.
- 확인되지 않은 항목: 저장소 외부에서 `/argus` 또는 `/api/argus/v2/*`를 사용하는 소비자 존재 여부

## 3. 목표와 범위

- 목표: 새 구현을 시작하기 전에 구제품 문서와 생성형 산출물을 정리하고, 레거시 코드·테스트는 검증 지식을 새 구조로 추출한 직후 제거한다.
- 범위: 아래 두 단계의 명시적 삭제 manifest, root README 재작성, 참조 검사, 테스트 자산 추출 후 레거시 제거
- 비범위: `.agent-harness/`, `.agents/`, `AGENTS.md`, `project-docs/`, 사용자 변경, `.pnpm-store/`, 실제 `.env`·token·운영 DB, Git commit·push
- 인수 조건:
  - 삭제된 문서 경로를 가리키는 활성 링크가 없다.
  - 새 코드와 테스트는 `argus_v2`를 import하지 않는다.
  - 보존 대상으로 정한 KIS·provider 테스트 시나리오가 새 계약 테스트로 존재한다.
  - 레거시 제거 뒤 전체 검색에서 활성 `argus_v2` 참조가 없다.
  - 삭제 전후에 사용자 기존 변경이 동일하게 유지된다.
- 유지할 기존 계약: 레거시 코드 제거 전까지 현재 FastAPI·Next.js 진입점은 유지한다.

## 4. 삭제·보존 manifest

### 1차 정리에서 제거

- `doc/` 전체
- `RUN_GUIDE.md`
- `backend/README.md`
- `frontend/README.md`
- `scripts/argus-v2-kis-smoke.crontab.example`
- `.tmp/codex-tmp/`의 생성형 테스트 산출물

`README.md`는 삭제하지 않고 승인된 새 제품 방향과 `project-docs/`를 가리키는 최소 진입 문서로 다시 작성한다.

### 테스트 자산 추출 뒤 제거

- `backend/src/argus_v2/`
- `backend/tests/test_argus_v2_*.py`
- `frontend/src/argus_v2/`
- `frontend/src/app/argus/`
- 새 진입점으로 대체된 뒤 남는 `argus_v2` 전용 package script와 env 설정

### 유지

- `backend/tests/test_api.py`: 새 health·router 계약으로 다시 작성
- `backend/src/main.py`: 새 router가 준비될 때까지 유지한 뒤 조립 코드만 교체
- `frontend/src/app/page.tsx`, `frontend/src/app/not-found.tsx`: 새 3탭 shell이 준비되면 rewrite
- `.env.example`: 새 provider 설정 계약이 정해진 단계에서 rewrite
- `backend/requirements.txt`, `frontend/package.json`, pnpm workspace·lockfile와 framework 설정
- `.agent-harness/`, `.agents/`, `AGENTS.md`, `project-docs/`
- `.pnpm-store/`
- 발견될 경우 모든 실제 `.env`, token cache와 운영 DB

## 5. 선택지와 결정

| 순위 | 선택지 | 적합한 이유 | 단점·비용 | 추천 여부 |
|---:|---|---|---|---|
| 1 | 문서 선제 정리, 코드·테스트는 추출 후 제거 | 작업 화면을 단순화하면서 API 검증 지식은 보존한다. | 짧은 기간 레거시 코드가 남는다. | 추천 |
| 2 | 문서·코드·테스트 즉시 전부 제거 | 가장 빠르게 빈 구조가 된다. | KIS fixture와 실패 사례를 잃고 현재 앱이 즉시 깨진다. | 비추천 |

- 사용자 결정: 1차로 구제품 문서와 생성형 임시파일을 제거하고, 레거시 코드·테스트는 characterization 자산 이관 뒤 별도 승인으로 제거한다.
- 승인일: `2026-07-22`

## 6. 구현 단계

| 단계 | 결과 | 변경 책임·예상 파일 | 검증 | 복구 지점 |
|---:|---|---|---|---|
| 1 | 문서·임시파일 정리 | 1차 삭제 manifest, `README.md`, `project-docs/project-profile.md` | 깨진 링크와 `doc/` 참조 검색, 사용자 변경 대조 | tracked 문서는 Git에서 복구, README patch 역적용 |
| 2 | 첫 characterization 자산 추출 | 새 `market_data` 테스트 fixture, KIS auth·수급 mapping·redaction·lease 시나리오 | 기존·신규 fixture 기대값 대조, secret scan | 기존 코드·테스트 유지 |
| 3 | 새 skeleton과 `market_flow` 구현 | 승인된 클린 리빌드 Plan 단계 3~4 | backend/frontend 관련 테스트와 build | 새 경계 비활성 또는 제거 |
| 4 | 레거시 코드 삭제 승인 점검 | 2차 삭제 manifest와 잔여 소비자 검색 | `argus_v2` 참조·DB·env·token 재검색 | 삭제 전 별도 사용자 승인 |
| 5 | 레거시 코드·테스트 제거 | 2차 삭제 manifest, package/env/entrypoint rewrite | 전체 test·lint·build·boundary 검사 | 승인된 Git 복구 지점 또는 파일 복원 |

## 7. 테스트와 검증 계획

- 1차 정리: Markdown 링크 대상과 `doc/`, `RUN_GUIDE.md`, 기존 `/argus` 문서 참조 검색
- characterization: KIS token 발급·cache, 시장 수급 field mapping, redaction, provider run, collector lease
- 경계: 새 source의 `argus_v2` import 금지와 API request path의 provider 직접 호출 금지
- 전체 검증: `pytest -q backend/tests`, `pnpm --filter frontend test`, `pnpm --filter frontend lint`, `pnpm --filter frontend build`, `pnpm check:boundaries`
- 미설치 또는 live credential 부재로 실행하지 못한 검사는 성공으로 기록하지 않는다.

## 8. 문서 영향

- `README.md`: 새 제품과 `project-docs/` 진입 문서로 교체
- `project-docs/project-profile.md`: 기존 `doc/` 지도와 저장소 지도를 실제 상태에 맞게 갱신
- `project-docs/plans/2026-07-21-clean-rebuild.md`: 실제 정리 순서와 검증 결과를 반영
- 삭제한 과거 설명을 새 문서에 중복 이관하지 않고, 여전히 유효한 책임·계약만 현재 상태 문서에 반영

## 9. 복구와 중단 기준

- 1차 문서 정리는 tracked 파일이므로 Git에서 복구할 수 있지만, 사용자의 dirty worktree를 임의로 reset하지 않는다.
- `.tmp/codex-tmp/`는 Git에 추적된 생성형 산출물이므로 Git에서 복구하거나 관련 테스트를 다시 실행해 재생성할 수 있다.
- 실제 `.env`, token cache 또는 운영 DB가 발견되면 즉시 중단하고 삭제 대상에서 제외한다.
- 외부 소비자가 확인되거나 characterization test가 새 구조에서 통과하지 않으면 레거시 코드 삭제를 중단한다.
- Git commit·branch·push는 사용자가 요청하지 않는 한 수행하지 않는다.

## 10. 구현 후 대조

- 계획과 달라진 부분: 1차 정리는 계획한 manifest와 동일하게 수행했다. 단계 2~5는 아직 수행하지 않았다.
- 달라진 이유: 해당 없음
- 최종 검증 결과: 1차 삭제 대상 제거, README 링크 대상 존재, 레거시 코드·테스트 보존과 `git diff --check` 통과를 확인했다. `.tmp/codex-tmp/`는 62개 tracked 생성형 산출물이었으며 승인 범위대로 제거했다. 전체 test·lint·build는 동작 변경이 없는 문서·임시파일 정리 단계에서는 실행하지 않았다.
- 갱신한 현재 상태 문서: `README.md`, `project-docs/project-profile.md`, ADR-002, 승인된 클린 리빌드 Plan
- 남은 위험: 외부 소비자 존재 여부와 live provider 검증
