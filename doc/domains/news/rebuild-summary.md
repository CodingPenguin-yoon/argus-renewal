# KRX News Rebuild Summary

이번 뉴스 리빌드에서 실제로 바뀐 점과 남은 known gap을 짧게 정리한 문서입니다.

## 이전 구조
- 뉴스 탭 판단 경로가 `raw_documents` 기반 규칙 계산, 문서별 event LLM, 카드별 editorial AI가 섞여 있었습니다.
- `/krx/news`가 읽는 source-of-truth가 명확하지 않았고, 설계 문서의 `배치 1회 triage + compare 1회`와 구현이 어긋나 있었습니다.

## 현재 구조
- 뉴스 탭 1차 source-of-truth는 `news_batch_triage`입니다.
- 1차 AI는 `NEWS_PRODUCT_BATCH_TRIAGE_*`를 켜면 짧은 뉴스 묶음을 1회 호출하는 batch triage입니다.
- 2차 AI는 카드별 fan-out이 아니라 현재 표면과 top 후보를 한 번에 비교하는 compare pass입니다.
- `run-news-automation` 경로는 `sync -> normalize -> refresh`를 유지하되, 기본 normalize는 deterministic으로 두어 뉴스 자동화에서 문서별 event LLM fan-out을 만들지 않습니다.
- `/krx/news`는 SSR 초기 payload 뒤 60초 same-origin polling으로 자동 갱신됩니다.

## 이번에 바뀐 핵심 항목
1. `news_batch_triage`를 뉴스 탭 materialization의 실제 source-of-truth로 전환
2. 1차 batch triage provider 추가와 legacy row 업그레이드 경로 추가
3. 2차 editorial AI를 current surface vs top candidates compare pass로 축소
4. `market_surface_state`에 lead editorial/provenance 요약 저장
5. 같은 lead라도 metadata가 바뀌면 `market_surface_history`에 `metadata_update` 기록
6. 뉴스 문서와 시스템 맵을 현재 파일 경로 기준으로 재작성

## 현재 구조의 장점
- 원래 설계 의도였던 `배치 1회 triage + compare 1회` 방향으로 호출 구조가 정리됐습니다.
- 뉴스 화면과 event API의 경계가 더 분명해졌습니다.
- 열린 탭도 새로고침 없이 1분 주기로 backend 상태를 반영할 수 있습니다.
- state/history에 editorial provenance가 남아 운영 확인이 쉬워졌습니다.

## 남은 known gap
- story continuity가 여전히 `cluster_key` 중심이라 장중/장후나 스코프 변경 시 같은 흐름이 새 이야기처럼 보일 수 있습니다.
- 휴장일 캘린더는 자동 동기화가 아니라 운영자가 날짜를 넣는 방식입니다.
- compare 판단 히스토리는 요약 state snapshot 중심이며, 더 세밀한 decision log가 필요하면 별도 설계가 필요합니다.

## 현재 기준으로 먼저 볼 문서
- `doc/architecture/system-map.md`
- `doc/domains/news/source-map.md`
- `doc/domains/news/runbook.md`
