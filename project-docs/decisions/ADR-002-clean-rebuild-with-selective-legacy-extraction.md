# ADR-002: 선별 추출 후 클린 리빌드

- 상태: `ACCEPTED`
- 날짜: `2026-07-21`
- 결정자: 사용자
- 관련 ADR: `ADR-001-capability-based-market-data-providers.md`
- 대체하는 ADR: 없음
- 대체된 ADR: 없음

## 배경

현재 Argus v2는 파생·뉴스·시장 판단을 하나의 dashboard 계약으로 조립하는 제품이다. 새 제품은 `대시보드 | 종목 | 파생`을 중심으로 KOSPI200 종목과 투자자 수급을 제공하는 시장 데이터 터미널이다. 제품 중심과 주요 조회 계약이 달라 기존 화면과 dashboard 조립 코드를 계속 확장하면 새 경계가 기존 `argus_v2` 책임에 종속된다.

반면 현재 코드에는 다시 검증하는 비용이 큰 자산이 있다.

- KIS access token 발급과 cache 동작
- KIS 요청 header, retry, 응답 path와 field alias 처리
- KOSPI200 근월물 code 탐색과 옵션 만기·콜풋 행사가 정규화
- provider run, raw sample redaction, collector lease의 실패 처리 경험
- `httpx.MockTransport` 기반 KIS 인증·옵션·선물 통합 테스트
- FastAPI, Next.js, pnpm workspace의 실행 골격

현재 구현의 결합 신호도 확인했다.

- `backend/src/argus_v2/storage.py`: 1,180줄
- `backend/src/argus_v2/dashboard.py`: 884줄
- `backend/src/argus_v2/providers/context_inputs.py`: 1,726줄
- `frontend/src/argus_v2/components/dashboard.tsx`: 1,199줄
- `scripts/check-market-boundaries.sh`: 실제 경계를 검사하지 않고 성공 문자열만 출력

따라서 기존 애플리케이션 구조를 유지할 이유는 약하지만, 외부 API 지식과 characterization test까지 제거할 이유도 없다.

## 결정 기준

- 새 제품 경계가 `argus_v2` 계약에 종속되지 않을 것
- 증권사 API의 이미 확인한 요청·응답 지식을 잃지 않을 것
- 현재 사용자 변경과 local data를 복구 불가능하게 만들지 않을 것
- 하네스가 요구하는 승인, 검증, 문서 동기화 흐름을 유지할 것
- 새 코드가 legacy import 없이 독립적으로 실행될 것

## 검토한 선택지

### 1순위: 선별 추출 후 같은 저장소에서 클린 리빌드

- 새 `market_data`와 `market_terminal` 경계는 legacy import 없이 작성한다.
- 기존 코드에서는 외부 API fixture, characterization test, 검증된 parsing 규칙만 새 계약으로 옮긴다.
- 새 수직 기능이 해당 자산을 대체한 뒤 기존 `argus_v2` 코드와 과거 `doc/`를 제거한다.
- 장점: 새 구조의 독립성과 기존 API 지식 보존을 동시에 달성한다.
- 단점: 삭제 전에 짧은 추출·대조 단계가 필요하다.
- 추천: 예

### 2순위: 기존 코드와 장기간 병행하는 Strangler 전환

- 기존 `/argus`와 새 화면을 장기간 함께 운영한다.
- 장점: 매 단계 rollback이 쉽다.
- 단점: 현재 제품이 운영 중이라는 근거가 없으면 병행 비용이 크고, 이전 구조를 계속 유지해야 한다.
- 추천: 실운영 소비자가 확인될 때만

### 3순위: 기존 코드·테스트·문서를 즉시 전부 삭제

- 장점: active tree가 즉시 단순해진다.
- 단점: KIS 요청 규칙, mock payload, 옵션 정규화와 실패 사례까지 잃으며 현재 dirty worktree의 사용자 변경을 훼손할 수 있다.
- 추천: 아니오

## 제안 결정

- 선택: `선별 추출 후 같은 저장소에서 클린 리빌드`
- 기술 스택: 별도 변경 근거가 생기기 전까지 FastAPI, Next.js, pnpm workspace를 유지한다.
- 코드 규칙: 새 애플리케이션 코드는 `argus_v2`를 import하지 않는다.
- 삭제 규칙: characterization 자산 이관, 복구 지점, 삭제 대상 확인, 사용자 최종 승인을 모두 충족한 뒤 legacy를 제거한다.
- 승인 내용: 새 `market_data`·`market_terminal` 경계에서 작은 수직 기능부터 구현하고, 레거시는 characterization 자산 이관과 별도 삭제 승인 전까지 유지한다.
- 승인일: `2026-07-21`

## 보존 분류

### 새 구조로 이관할 지식과 테스트

- `backend/src/argus_v2/providers/kis_auth.py`
- `backend/src/argus_v2/providers/kis_common.py`
- `backend/src/argus_v2/providers/kis_derivatives.py`
- `backend/src/argus_v2/providers/kis_option_chain.py`
- `backend/tests/test_argus_v2_kis_auth.py`
- `backend/tests/test_argus_v2_kis_live.py`
- provider sample redaction과 collector lease의 테스트 시나리오

파일을 그대로 복사한다는 뜻은 아니다. 새 provider port와 fact 계약에 맞춰 최소 동작만 다시 작성하고 기존 fixture로 결과를 대조한다.

### 개념만 참고하고 다시 작성할 부분

- `backend/src/argus_v2/market_calendar.py`: 장 세션 개념은 유지하되 휴장일을 일부 날짜에 고정한 구현은 재사용하지 않는다.
- `backend/src/argus_v2/db.py`: 순차 migration 개념은 유지하되 새 schema 소유권에 맞춰 다시 작성한다.
- `backend/src/argus_v2/storage.py`: provider run, provenance, lease 개념만 새 repository로 분해한다.
- `frontend/src/argus_v2/components/option-quotes-table.tsx`: 옵션체인 열과 행사가 중심 표현만 새 UI 계약에서 재검토한다.

### 새 제품에서 제거할 후보

- `backend/src/argus_v2/dashboard.py`, `contracts.py`, `judgement/`
- `backend/src/argus_v2/providers/context_inputs.py`와 뉴스·AI 수집 경로
- 기존 `argus_v2` API, storage와 migration
- `frontend/src/argus_v2/`와 `frontend/src/app/argus/`
- 과거 제품 기준 `doc/`
- placeholder 경계 검사와 기존 제품 전용 실행 script

## 문서 정책

- `AGENTS.md`, `.agent-harness/`, `.agents/skills/`는 하네스 관리 영역이므로 제거하지 않는다.
- `project-docs/`는 새 제품의 승인된 공동 지식이므로 유지하고 실제 구현에 맞춰 갱신한다.
- 기존 `doc/`는 KIS 운영 정보와 아직 유효한 사실을 추출한 뒤 삭제 후보로 둔다.
- `README.md`, `RUN_GUIDE.md`, `.env.example`은 새 실행 경로가 생긴 시점에 전면 다시 작성한다.

## 감수한 단점

- 초기 한 단계는 기능 개발 대신 fixture와 동작을 추출하는 데 사용한다.
- legacy 삭제 전까지 짧은 기간 두 구조가 저장소에 공존한다.
- 현재 테스트 의존성이 설치되지 않아 기존 테스트의 실제 통과 여부는 아직 확인하지 못했다.

## 재검토 조건

- 현재 `/argus` 또는 `argus_v2` DB를 사용하는 실운영 소비자가 확인됨
- 외부 API fixture 또는 KIS live 검증 근거가 모두 무효임이 확인됨
- FastAPI·Next.js 유지가 새 요구사항을 방해하는 구체적인 제약이 확인됨

## 구현 메모

- `2026-07-22`: 기존 `doc/`, `RUN_GUIDE.md`, backend·frontend README와 레거시 collector 배포 예시는 코드 삭제보다 먼저 제거했다. 해당 문서의 KIS 운영 규칙은 코드, `.env.example`, 기존 테스트에서 다시 확인할 수 있음을 대조했다.
- 루트 `README.md`는 승인된 새 제품과 `project-docs/`를 가리키는 최소 진입 문서로 교체했다.
- 레거시 코드와 테스트는 characterization 자산을 새 계약으로 이관할 때까지 유지한다.
