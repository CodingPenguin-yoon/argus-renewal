# Legacy Transition Closeout

## 기준

레거시 전환은 구 KRX 앱을 개선하는 작업이 아니라, Argus v2 runtime으로 대체하고 구 runtime을 제거하는 작업입니다.

현재 상태: 완료 판정.

완료 판정 기준:

- `/argus` 4개 route와 `/api/argus/v2/dashboard`만 핵심 runtime으로 남습니다.
- `/krx*`, `/api/krx*`, 구 뉴스/API/global-events runtime은 동작하지 않습니다.
- `backend/src/krx`, `frontend/src/krx`, 구 KRX 테스트와 구 KRX 문서는 제거됩니다.
- v2 storage, provider, judgement, frontend가 테스트와 build를 통과합니다.
- 문서와 env example이 v2 기준으로 일치합니다.

## 레거시 전환 잔여 작업

1. 최종 잔여 grep
   상태: 완료.
   기준: `krx`, `/api/krx`, `/krx`, `company_master`, `market_signal`, `global_events` 검색 결과가 런타임 레거시가 아닌 문서 설명이나 시장명만 남아야 합니다.
   결과: 남은 항목은 제거 사실을 설명하는 문서와 `/api/krx` 미마운트 확인 테스트뿐입니다.

2. 빈 디렉토리 cleanup
   상태: 완료.
   기준: 삭제된 레거시 파일이 남긴 빈 디렉토리를 제거합니다.

3. 문서/env 정합성 확인
   상태: 완료.
   기준: `README.md`, `RUN_GUIDE.md`, `.env.example`, backend/frontend README가 v2 runtime과 provider 기준을 동일하게 설명해야 합니다.

4. 전체 검증
   상태: 완료.
   기준: backend test, backend compile, frontend lint/test/build, `git diff --check`가 통과해야 합니다.

5. closeout 기록
   상태: 완료.
   기준: `current-status.md`에 레거시 전환 완료 상태와 남은 제품 고도화 backlog를 분리해서 기록합니다.

## 제품 고도화 Backlog

아래는 레거시 전환 잔여 작업이 아닙니다. 전환 완료 후 품질을 올리는 작업입니다.

- KIS 현물 반응 장중 운영 관찰: 재시도 빈도, 섹터명 노이즈, 현물 수급 단위 배율.
- 뉴스 트리거 품질 보정: source 신뢰도, 중복 제거, 감점 키워드, `connection_strength`.
- 판단 엔진 가중치 정교화: 외국인 현물 수급, PCR, OI 변화, basis, 뉴스 악재/호재.
- 매크로 실제 source 결정: 금리, 환율, 미국 지수, 원자재.
- 프런트 실제 장중 데이터 기준 문장 길이와 card 개수 미세 조정.
- 운영 자동화: 장 시작 전/장중 수집 스케줄, DB 보관 기간, 실패 로그, 재수집 기준.

## 실행 순서

1. 완료: 빈 레거시 디렉토리를 제거합니다.
2. 완료: 최종 grep으로 레거시 runtime 참조가 없는지 확인합니다.
3. 완료: 문서/env 차이를 정리합니다.
4. 완료: 전체 검증을 실행합니다.
5. 완료: `current-status.md`에 closeout 상태를 업데이트합니다.
