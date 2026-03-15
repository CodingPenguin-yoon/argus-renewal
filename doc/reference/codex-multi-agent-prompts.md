# Codex Multi-Agent Parent Prompts

Argus에서 parent session이 child agents를 명시적으로 부를 때 쓰는 프롬프트 모음입니다.

## 기본 원칙
- repo 루트에서 시작한다.
- agent 이름은 `explorer`, `reviewer`, `docs_researcher`, `worker`를 그대로 쓴다.
- 구현 작업은 가능하면 `explorer -> reviewer -> docs_researcher -> worker` 순서를 유지한다.
- `worker`는 범위가 좁혀진 뒤에만 수정하게 한다.
- 최종 응답은 긴 로그 대신 요약 섹션으로 받는다.

## 1) 일반 구현 작업

```text
이 작업은 Argus 기본 멀티 에이전트 플로우로 처리해.

1. explorer가 먼저 실제 코드 경로, 영향 파일, 관련 심볼, 설정과 마이그레이션, 연관 테스트를 정리한다.
2. reviewer가 correctness, regression, security, missing tests 관점에서 실제 리스크만 찾는다.
3. docs_researcher가 프레임워크, API, 설정 가정을 검증한다.
4. worker가 가장 작은 수정만 적용한다.

중간 로그는 길게 노출하지 말고 마지막에 아래 형식으로 통합해서 보여줘.
- scope
- risks
- docs constraints
- changes made
- validation
- residual risk
```

## 2) 버그 조사 + 수정

```text
이 버그를 Argus 멀티 에이전트 플로우로 조사하고 수정해.

- explorer는 재현에 관련된 실제 코드 경로와 상태 전이를 찾는다.
- reviewer는 실패 원인 후보와 회귀 포인트를 severity 순으로 정리한다.
- docs_researcher는 관련 옵션, 버전 제약, 설정 요구사항을 검증한다.
- 원인 가설이 정리된 뒤에만 worker가 수정한다.

수정 전에는 원인 가설과 근거를 먼저 한 번 요약해.
수정 후에는 변경 파일, 검증 결과, 남은 불확실성을 정리해.
```

## 3) 현재 브랜치 리뷰

```text
현재 브랜치를 main과 비교해 Argus 멀티 에이전트 리뷰를 해줘.

- explorer는 변경 영향 범위와 연쇄 영향 파일을 맵핑한다.
- reviewer는 must-fix 수준의 correctness, security, regression 이슈만 찾는다.
- docs_researcher는 패치가 기대는 외부 동작이나 버전 의존성을 확인한다.
- worker는 수정하지 않는다.

최종 결과는 아래 세 구역으로만 정리해.
- must fix
- should fix
- watchlist
```

## 4) 안전한 리팩터링

```text
이 리팩터를 바로 크게 하지 말고 Argus 방식으로 안전 범위부터 잡아줘.

- explorer가 변경 후보 파일, 호출 경로, 인터페이스 경계를 찾는다.
- reviewer가 깨질 수 있는 계약, 데이터 흐름, 테스트 공백을 찾는다.
- docs_researcher가 버전, 설정, 마이그레이션 제약을 확인한다.
- worker는 단계 1의 최소 변경만 수행한다.

한 번에 큰 리팩터 대신 되돌리기 쉬운 작은 단계로 나눠서 진행해.
단계 1이 끝나면 다음 단계로 넘어가기 전에 리스크를 다시 요약해.
```

## 5) 문서와 설정 가정 검증만 필요할 때

```text
이번 작업은 구현보다 가정 검증이 먼저다.

- explorer는 관련 파일과 설정 경로만 좁혀라.
- docs_researcher는 README, doc/, package 버전, lockfile, env 요구사항을 먼저 확인하고 필요한 경우 외부 문서 의존성을 검증해라.
- reviewer는 수정 없이도 터질 수 있는 설정 리스크만 짚어라.
- worker는 실행하지 마라.

최종 결과는 아래 순서로 정리해.
- claim to verify
- confirmed facts
- config or version caveats
- implementation impact
```

## 6) 범위 파악만 먼저 할 때

```text
아직 수정하지 말고 Argus에서 이 작업의 실제 범위만 먼저 좁혀줘.

- explorer만 우선 실행해서 엔트리 포인트, 실제 실행 경로, 영향 파일, 관련 심볼, 연관 테스트를 정리해.
- reviewer와 worker는 아직 실행하지 마라.
- docs_researcher는 explorer 결과에서 문서 확인이 꼭 필요한 주장만 보이면 그때만 붙여라.

최종 결과는 아래 형식으로만 정리해.
- scope summary
- affected files
- execution path
- likely tests
- unknowns
```

## 7) 아주 작은 수정이라 멀티 에이전트를 건너뛸 때

```text
이 작업은 단일 파일의 작은 수정이므로 멀티 에이전트를 쓰지 말고 메인 세션에서 바로 처리해.

- 대상 파일과 변경 범위를 먼저 짧게 확인해.
- 관련 없는 리팩터링은 하지 마.
- 필요한 최소 검증만 실행해.
- 마지막에 변경 파일, 검증 결과, 잔여 리스크만 정리해.
```
