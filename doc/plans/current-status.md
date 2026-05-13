# Current Status

## Completion Snapshot

- 레거시 전환 달성률: 완료 판정.
- 제품 완성 달성률: 약 70%.
- MVP 상태: 폐쇄 루프 구성 완료, live AI RSS 저장 확인 완료. 기준 문서는 `doc/plans/mvp-closeout.md`입니다.
- 기준: 레거시 전환은 구 KRX runtime 제거, v2 runtime 대체, 레거시 파일 제거, 검증 통과를 기준으로 봅니다.
- 주의: 뉴스 품질, 판단 가중치, 매크로 source, 장중 운영 관찰은 레거시 전환 잔여 작업이 아니라 제품 고도화 작업입니다.

## Done

- 제품 기준을 `파생/옵션 -> 뉴스/매크로 -> 현물 반응 -> 판단` 순서로 고정했습니다.
- canonical frontend route를 `/argus`, `/argus/derivatives`, `/argus/reaction`, `/argus/triggers`로 정리했습니다.
- backend runtime은 `/api/argus/v2/dashboard`와 `/health`만 mount합니다.
- KIS token env 입력을 제거했고, app key/secret으로 발급한 token은 `backend/data/kis_token_cache.json`에만 캐시합니다.
- KIS 국내파생과 옵션체인 provider를 `backend/src/argus_v2/providers` 내부 구현으로 이관했습니다.
- KIS live smoke로 국내파생 1건과 옵션체인 100개 level 수신 및 v2 DB 저장을 확인했습니다.
- KIS 국내파생 응답의 basis, market basis, 선물 미결제약정 증감률을 dashboard 판단 입력에 연결했습니다.
- 옵션체인 최신 snapshot과 직전 snapshot을 비교해 옵션 OI 변화율과 CALL/PUT 우위 방향을 dashboard/판단 엔진에 연결했습니다.
- 판단 엔진은 옵션 OI 변화 방향을 summary 문자열 파싱이 아니라 `option_open_interest_change.dominant_side` 구조 필드로 읽습니다.
- KIS 현물 반응 provider를 추가해 KOSPI/KOSDAQ 등락률, 상승/하락 종목 수, 강/약 업종을 v2 DB에 저장할 수 있게 했습니다.
- KIS 현물 반응 live 수집에서 실제 field alias를 확인했고, 해외/레버리지/지수성 항목을 제외해 국내 현물 섹터만 남기도록 보정했습니다.
- KIS 시장별 투자자매매동향을 별도 현물 수급 계약(`spot_foreign_net_buy`, `spot_institution_net_buy`, `spot_individual_net_buy`)으로 추가했습니다. 선물 수급 필드에는 대입하지 않습니다.
- KIS 현물 수급 live 수집에서 `spot_flow_count=1`을 확인했고, 원시 `*_tr_pbmn` 값은 `ARGUS_MARKET_REACTION_INVESTOR_AMOUNT_MULTIPLIER`로 KRW 정규화해 저장합니다.
- v2 SQLite 저장소는 provider run, redacted raw sample, derivatives, option chain, market reaction, news trigger 계약을 가집니다.
- `/api/argus/v2/dashboard`는 v2 DB 최신 snapshot을 먼저 읽고, DB가 비어 있을 때만 mock fallback을 사용합니다.
- `collect-context` CLI로 현물 반응과 뉴스 트리거를 v2 DB에 적재할 수 있습니다.
- 뉴스 트리거의 키워드 기반 호악재/중요도/품질 판정은 제거했습니다. RSS/Naver/DART는 원문 수집만 담당하고, 노출 여부/영향/연결강도는 AI enrichment JSON만 사용합니다.
- AI가 꺼졌거나 실패한 상태에서는 실뉴스를 임의로 호재/악재 분류하지 않습니다. 로컬 UI는 `mock`, 수동 import는 명시적 `ai_enrichment` 계약으로 동작합니다.
- Gemini provider를 추가했고 `ARGUS_NEWS_AI_PROVIDER=gemini`, `ARGUS_GEMINI_MODEL`, `ARGUS_GEMINI_API_KEY`로 실뉴스 AI 판단을 실행할 수 있습니다. MVP 기본 모델은 `gemini-2.5-flash`입니다.
- `smoke-news-ai` CLI로 DB 저장 없이 AI 뉴스 판단 JSON 응답을 검증할 수 있습니다.
- `smoke-news-ai`는 Gemini 실키가 없을 때 `news_ai_disabled`로 실패 상태를 명확히 반환합니다.
- 2026-05-13 기준 Gemini key 인식, `smoke-news-ai` 성공, RSS live 뉴스 1건 DB 저장, dashboard AI reason/confidence/factors 계약 확인, KIS `smoke-kis`와 `collect-context --market-reaction-provider kis` 성공을 확인했습니다.
- RSS live 수집은 AI 후보를 먼저 줄인 뒤 Gemini에 보내도록 제한했습니다. `gemini-3-flash-preview`는 RSS 수집 중 timeout/429가 있어 MVP 기본값으로 쓰지 않습니다.
- 매크로 이벤트는 `macro` provider를 통해 뉴스 트리거와 같은 계약으로 normalize할 수 있습니다.
- 판단 엔진은 선물 변동률, basis, 선물 미결제약정 증감률, 옵션 압력, 현물 반응, 뉴스 트리거를 1차 점수화합니다.
- 판단 엔진은 선물 수급이 비어 있을 때 외국인 현물 수급을 보조 신호로 쓰고, 선물/현물 외국인 수급이 충돌하면 반대 증거로 표시합니다.
- 판단 엔진은 파생 하방 + 반도체/강세 업종, 파생 상방 + 약세 업종/악재처럼 상충 신호가 있을 때 한 단계 완충하도록 테스트로 고정했습니다.
- frontend는 PRD 기준 4개 탭 UI와 리서치 데스크 디자인 톤으로 재구성했고, `/argus` 첫 화면은 결론/핵심 수급/대표 뉴스/섹터 검증 중심으로 축약했습니다.
- 구형 `domains/health`, `shared/errors`, `NEWS_PROVIDER` 설정을 제거하고 backend runtime을 Argus v2 중심으로 단순화했습니다.
- `backend/src/krx`, `frontend/src/krx`, `/krx*` route, 구 KRX 테스트를 제거했습니다.
- 오래된 KRX 문서와 크론 예시를 제거하고 v2 문서만 남겼습니다.

## In Progress

- MVP closeout: `/argus/triggers` 브라우저 화면 확인, KIS 장중 반복 수집 관찰.
- 제품 고도화: 판단 엔진 운영 가중치 보정, 매크로 실제 source 결정.
- 보류: KIS 공식 `domestic_futureoption` 샘플에서는 시장 전체 외국인/기관/개인 KOSPI200 선물 수급 endpoint가 아직 확인되지 않았습니다. 계좌 기반 잔고/손익 API는 시장 수급으로 연결하지 않습니다.

## Next

1. `/argus/triggers` 브라우저 화면에서 live 뉴스 AI reason/confidence/factors 표시를 확인합니다.
2. KIS `smoke-kis`와 `collect-context --market-reaction-provider kis`를 장중 2회 이상 반복 실행해 freshness와 provider health를 확인합니다.
3. RSS 수집은 `ARGUS_NEWS_TRIGGERS_LIMIT`와 `ARGUS_NEWS_AI_TIMEOUT_SECONDS`를 낮게 유지하면서 timeout/429 빈도를 관찰합니다.
4. MVP 확인 후 판단 엔진 가중치는 실제 장중 케이스 기준으로 추가 보정합니다.
5. KOSPI200 시장 전체 선물 수급 endpoint는 공식 문서나 live smoke로 확인되기 전까지 보류합니다.

## Risks

- KIS field와 TR 응답은 문서와 다를 수 있으므로 raw sample 저장과 redaction을 계속 유지해야 합니다.
- 뉴스 트리거는 “많이 보여주기”보다 판단에 연결되는 이벤트만 남겨야 하며, 키워드 룰 대신 AI 판단 로그와 실제 장중 결과로 보정해야 합니다.
- 테스트는 핵심 계약을 지키되, 테스트 작성 자체가 구현 속도를 잡아먹지 않게 유지합니다.

## Last Updated

- 2026-05-13
