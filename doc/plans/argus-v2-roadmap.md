# Argus v2 Roadmap

## 목적

Argus v2를 레거시 KRX 화면/집계 계층 없이 완성하기 위한 실행 기준입니다.

작업 순서는 항상 아래를 따릅니다.

1. 실제 데이터가 들어오는지 확인한다.
2. provider run과 raw sample을 저장한다.
3. v2 데이터 계약으로 normalize한다.
4. 판단 엔진에 연결한다.
5. 화면에 노출한다.

## Current Runtime

- Frontend: `/argus`, `/argus/derivatives`, `/argus/reaction`, `/argus/triggers`
- Backend: `/api/argus/v2/dashboard`, `/health`
- Removed: `backend/src/krx`, `frontend/src/krx`, `/krx*`, `/api/krx*`, `/api/news*`, `/api/global-events*`

## Completion Baseline

- 레거시 전환: 완료 판정.
- 제품 완성: 약 65%.
- 레거시 전환 잔여 작업은 `legacy-transition-closeout.md`를 기준으로 마감합니다.
- 제품 고도화 작업은 레거시 전환 완료 후 backlog로 처리합니다.

## Phase 1. v2 Storage

상태: 완료.

- 완료: provider run 저장
- 완료: raw sample redaction 저장
- 완료: KIS 국내파생 snapshot 저장
- 완료: KIS 옵션체인 snapshot/level 저장
- 완료: 현물 반응 snapshot/sector 저장 계약
- 완료: 뉴스 트리거 저장 계약

## Phase 2. KIS Derivatives And Options

상태: 1차 완료. 시장 전체 투자자별 선물 수급 endpoint는 공식 샘플 기준 미확인.

- 완료: KIS token 자동 발급/cache
- 완료: access token env 제거
- 완료: 국내파생 provider 내부화
- 완료: 옵션체인 provider 내부화
- 완료: live smoke DB 저장
- 완료: KIS 선물 basis와 market basis 저장
- 완료: KIS 선물 미결제약정 증감률 dashboard 연결
- 완료: 옵션 OI 전시점 비교 계산과 CALL/PUT 변화 우위 판단 연결
- 완료: 옵션 OI 변화 방향을 summary 문자열 파싱이 아니라 구조 필드 `option_open_interest_change.dominant_side`로 판단 엔진에 전달
- 보류: KIS 공식 `domestic_futureoption` 샘플의 `inquire_balance_valuation_pl`은 이름/주석에 시장 동향 문구가 있으나 실제 path가 계좌 기반 `/trading/inquire-balance-valuation-pl`이고 `CANO`, `ACNT_PRDT_CD`가 필요하므로 시장 전체 외국인/기관/개인 수급으로 연결하지 않습니다.
- 남음: 공식 문서 또는 live smoke로 확인되는 시장 전체 투자자별 선물 수급 endpoint 대체 경로 조사

## Phase 3. Market Reaction

상태: 저장 계약, API 연결, KIS provider 1차 구현과 live field 확인 완료.

- 완료: `argus_v2_market_reaction_snapshots`
- 완료: `argus_v2_market_reaction_sectors`
- 완료: dashboard response 연결
- 완료: mock/file provider와 `collect-context` CLI 연결
- 완료: KIS KOSPI/KOSDAQ 지수 provider
- 완료: KIS 상승/하락 종목 수 provider
- 완료: KIS 업종 강약 provider
- 완료: 실제 KIS 응답 field `bstp_nmix_prdy_ctrt`, `ascn_issu_cnt`, `down_issu_cnt`, `hts_kor_isnm` 기준 저장 확인
- 완료: 해외/레버리지/지수성 항목 제외와 KOSPI/KOSDAQ 숫자 prefix 제거
- 남음: 장중 반복 수집 시 재시도 빈도와 섹터명 노이즈 운영 관찰

## Phase 4. News Triggers

상태: 저장 계약, API 연결, provider, AI enrichment 1차 완료.

- 완료: `argus_v2_news_triggers`
- 완료: dashboard response 연결
- 완료: mock/file/rss/naver/dart/hybrid provider와 `collect-context` CLI 연결
- 완료: 키워드 기반 호악재/중요도/source 품질 판정을 제거
- 완료: AI enrichment JSON(`should_use`, `impact`, `relevance_score`, `connection_strength`, `affected_factors`, `summary`, `reason`, `confidence`) 기준으로만 실뉴스를 노출
- 완료: AI가 꺼지거나 실패하면 RSS/Naver/DART 원문을 임의 판단으로 노출하지 않음
- 완료: dashboard 뉴스 trigger는 AI relevance와 confidence 기준으로 정렬
- 완료: Gemini provider와 `smoke-news-ai` CLI 추가
- 남음: Gemini 실키 기반 smoke test와 실제 운영 로그 기준 AI prompt/schema 보정
- 완료: macro event를 news trigger 계약으로 normalize하는 `macro` provider
- 남음: timeout/비용/재시도 운영 기준 확정

## Phase 5. Judgement Engine

상태: rule-based 1차 완료.

- 완료: 5단계 판단 라벨
- 완료: reasons, counter evidence, transition condition, watch points
- 완료: 미수신 데이터가 있으면 보수적으로 확신도 제한
- 완료: basis와 선물 OI 증감률 1차 가중치 반영
- 완료: 옵션 OI 변화 CALL/PUT 우위 1차 가중치 반영
- 완료: 옵션 OI 변화 방향을 summary 문자열이 아니라 구조 데이터로 읽도록 보정
- 완료: 선물 수급 미수신 시 외국인 현물 수급을 보조 신호로 반영
- 완료: 외국인 선물/현물 수급 충돌 시 반대 증거로 표시
- 완료: 파생 하방 + 현물/섹터 버팀, 파생 상방 + 약세 섹터/악재 케이스의 상충 신호 테스트
- 완료: missing/stale/뉴스 없음/live provider 미연결 confidence 제한 테스트
- 남음: PCR/OI와 뉴스 영향 가중치 운영 보정

## Phase 6. Frontend

상태: 1차 완료. 첫 화면 밀도 조정 완료.

- 완료: 4개 route
- 완료: 상단 tab nav
- 완료: 데이터 수신 상태 노출
- 완료: 미수신/빈 상태 노출
- 완료: `/argus`는 결론, 핵심 수급, 대표 뉴스, 강/약 섹터만 축약 표시
- 남음: 실제 장중 데이터 기준 문장 길이와 card 개수 미세 조정

## Next Order

1. Gemini 실키 기반 뉴스 AI smoke test와 prompt 운영 보정
2. KIS 현물 반응 운영 관찰
3. 판단 엔진 가중치 정교화

## Open Work Breakdown

### 1. 옵션 OI 전시점 비교

목표: 최근 옵션체인 snapshot과 직전 snapshot을 비교해 콜/풋 OI 증가 방향을 판단 입력으로 사용합니다.

상태: 완료.

완료 기준:

- 완료: 같은 만기 기준으로 최신 snapshot과 직전 snapshot을 찾습니다.
- 완료: 콜 OI 변화율, 풋 OI 변화율, 총 OI 변화율을 계산합니다.
- 완료: dashboard의 `open_interest_change_rate`는 옵션 비교값을 우선 사용합니다.
- 완료: 판단 엔진은 풋 OI 증가가 강하면 하방 점수를, 콜 OI 증가가 강하면 상방 점수를 보강합니다.
- 남음: “비교 기준 없음”을 화면에서 더 친절한 별도 문구로 보여주는 UX 조정.

### 2. 뉴스 트리거 AI enrichment

목표: 많이 보여주는 뉴스가 아니라 시장 판단에 연결되는 뉴스만 남깁니다.

상태: 1차 완료.

완료 기준:

- 완료: RSS/Naver/DART는 원문 수집만 담당합니다.
- 완료: 호악재, 노출 여부, relevance, connection strength는 AI JSON 응답만 사용합니다.
- 완료: 제목/요약 중복을 제거하고 AI relevance가 높은 원문을 우선합니다.
- 완료: dashboard에는 상위 trigger만 노출합니다.
- 완료: AI disabled/failed 상태에서는 실뉴스를 임의로 표시하지 않습니다.
- 남음: 실제 운영 로그를 보며 prompt, confidence 기준, 실패 처리 문구를 보정합니다.

### 3. 매크로 이벤트 normalize

목표: 뉴스가 아닌 금리/환율/미국 지수/원자재 이벤트도 같은 trigger 구조로 저장합니다.

상태: 1차 완료.

완료 기준:

- 완료: provider run과 raw sample을 저장합니다.
- 완료: 이벤트 제목, 요약, 영향 방향, 발표/관측 시간을 같은 계약으로 normalize합니다.
- 완료: `macro` provider와 `hybrid` provider에서 macro event를 같은 trigger pipeline에 태웁니다.
- 남음: 실제 macro source를 정하면 file/API provider의 필드 alias를 보정합니다.

### 4. KIS 수급 endpoint

목표: 외국인/기관/개인 KOSPI200 선물 수급을 실제 데이터로 연결합니다.

상태: 선물 수급은 보류, 현물 수급은 별도 계약으로 1차 완료.

조사 결과:

- KIS 공식 `MCP/Kis Trading MCP/configs/domestic_futureoption.json`에는 기본시세, 옵션전광판, 계좌 주문/잔고 계열 API가 확인됩니다.
- `examples_user/domestic_futureoption/domestic_futureoption_functions.py`의 `inquire_balance_valuation_pl`은 docstring에 시장별 투자자매매동향 문구가 있으나, 실제 endpoint는 계좌 기반 잔고평가손익 `/uapi/domestic-futureoption/v1/trading/inquire-balance-valuation-pl`입니다.
- 계좌번호가 필요한 API는 시장 전체 외국인/기관/개인 수급으로 normalize하지 않습니다.
- KIS 공식 `domestic_stock`에는 `/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market`와 `/uapi/domestic-stock/v1/quotations/inquire-investor-daily-by-market`가 있으나, 이는 현물 시장 투자자매매동향입니다.
- 현물 투자자 수급은 `foreign_futures_net_buy` 같은 선물 수급 필드에는 대입하지 않습니다.

현물 수급 구현:

- 완료: `/uapi/domestic-stock/v1/quotations/inquire-investor-time-by-market`, TR `FHPTJ04030000`를 KIS 현물 반응 provider에 연결했습니다.
- 완료: DB에는 `spot_foreign_net_buy`, `spot_institution_net_buy`, `spot_individual_net_buy` 컬럼으로 저장합니다.
- 완료: KIS 원시 `*_tr_pbmn` 값은 `ARGUS_MARKET_REACTION_INVESTOR_AMOUNT_MULTIPLIER`로 KRW 정규화합니다.
- 완료: 첫 화면 핵심 수급에는 외국인 현물만 축약 노출하고, 현물 반응 상세 탭에는 외국인/기관/개인을 모두 노출합니다.

완료 기준:

- 완료: 현물 수급 endpoint와 필드는 공식 샘플 및 live smoke로 확인합니다.
- 완료: raw sample redaction을 유지합니다.
- 남음: 선물 수급은 공식 문서나 live smoke로 확인되기 전까지 runtime에 연결하지 않습니다.

### 5. 판단 엔진 테스트

목표: 결론 문장이 흔들리지 않게 대표 케이스를 테스트로 고정합니다.

완료 기준:

- 완료: 파생 하방 + 현물/섹터 버팀
- 완료: 파생 상방 + 뉴스 악재 + 약세 섹터
- 완료: 데이터 일부 미수신 시 confidence 제한
- 남음: 뉴스 AI 악재 + 수급 중립

### 6. 화면 밀도 조정

목표: 한 화면에서 결론, 핵심 수급, 옵션 압력, 뉴스 원인을 빠르게 읽게 합니다.

완료 기준:

- 완료: `/argus`는 결론 중심으로 줄입니다.
- 완료: 상세값은 `/argus/derivatives`, `/argus/reaction`, `/argus/triggers`에 둡니다.
- 완료: 미수신 값은 숨기지 않고 이유를 짧게 표시합니다.

## Validation

```bash
cd backend
pytest -q
python3 -m compileall src tests
```

```bash
pnpm --filter frontend lint
pnpm --filter frontend test -- --runInBand
pnpm --filter frontend build
```

## Last Updated

- 2026-05-13
