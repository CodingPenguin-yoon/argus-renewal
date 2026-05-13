# Current Status

## 한 줄 요약

Argus v2는 레거시 KRX 중심 프로젝트를 제거하고, `파생/옵션 + 실제 뉴스 AI 판단 + 원천 뉴스 피드 + 현물 반응 + 판단 엔진 + 대시보드` 구조로 재구성된 상태입니다.

현재 MVP의 기술 폐쇄 루프는 닫혔습니다.

```text
실제 데이터 수집
-> AI 뉴스 판단
-> SQLite 저장
-> dashboard API 조회
-> frontend 표시 계약

원천 뉴스 피드는 별도 API와 화면으로 분리했습니다.

```text
RSS/Naver/DART/hybrid 원천 뉴스
-> /api/argus/v2/news-feed
-> /argus/triggers/news
```
```

남은 일은 “기능이 존재하는가”가 아니라 “장중에 반복해서 믿고 볼 수 있는가”를 검증하고 보정하는 단계입니다.

## Completion Snapshot

- 레거시 전환 달성률: 완료.
- MVP 폐쇄 루프 달성률: 완료.
- 제품 완성 달성률: 약 70%.
- 기준 문서: `doc/plans/mvp-closeout.md`
- PRD 기준 문서: `doc/prd/argus-v2-prd.md`
- 공부 문서: `doc/study/`

완료로 보는 기준:

- 구 KRX runtime, route, 문서, 테스트는 제거했습니다.
- v2 backend runtime은 `/api/argus/v2/dashboard`, `/api/argus/v2/news-feed`, `/health` 중심입니다.
- frontend canonical route는 `/argus`, `/argus/derivatives`, `/argus/reaction`, `/argus/triggers`, `/argus/triggers/news`입니다.
- SQLite 저장소는 provider run, raw sample, derivatives, option chain, market reaction, news trigger를 기록합니다.
- DB가 비어 있을 때만 mock fallback을 사용합니다.
- 실뉴스는 AI 판단 없이는 임의로 호재/악재 분류하지 않습니다.
- 원천 뉴스 피드는 AI 판단과 별개로 `뉴스 분석 > 뉴스`에서 표시합니다.

## 현재 제품 방향

Argus는 매수/매도 추천기가 아닙니다.

목표는 장 시작 전과 장중에 시장 상황을 빠르게 읽는 것입니다.

핵심 질문은 세 가지입니다.

- 파생/옵션 쪽 압력은 어디를 향하는가?
- 실제 뉴스와 매크로 이벤트는 그 방향을 강화하는가, 상쇄하는가?
- 현물 반응과 섹터 흐름은 파생 신호를 확인해주는가?

현재 판단 우선순위:

```text
1. 파생/옵션
2. 뉴스/매크로
3. 현물 반응
4. 판단 엔진
5. 대시보드 표시
```

## 검증된 Live 결과

2026-05-13 기준으로 확인한 내용입니다.

- `smoke-kis`: 성공.
- KIS token: env에 직접 저장하지 않고 app key/secret으로 자동 발급 후 `backend/data/kis_token_cache.json`에 캐시.
- KIS 국내파생: snapshot 1건 저장 확인.
- KIS 옵션체인: sample 100건 수신 확인.
- KIS market reaction `collect-context --market-reaction-provider kis`: snapshot 1건 저장 확인.
- Gemini key: 인식 확인.
- Gemini smoke: `gemini-2.5-flash`로 `status=success`, `should_use=true` 확인.
- RSS live 뉴스: Gemini 판단 후 news trigger 1건 DB 저장 확인.
- dashboard 계약: 저장된 live 뉴스의 `ai_reason`, `ai_confidence`, `affected_factors` 확인.
- `/api/argus/v2/news-feed`: RSS 원천 뉴스 50건 수신 확인.
- `/argus/triggers/news`: HTTP 200 응답 확인.

주의할 점:

- `gemini-3-flash`는 API에서 404였습니다.
- `gemini-3-flash-preview`는 단건 smoke는 성공했지만 RSS 수집 중 timeout/429가 발생했습니다.
- MVP 운영 기본 모델은 `gemini-2.5-flash`입니다.
- RSS 후보 전체를 Gemini에 보내면 비용, 지연, rate limit 문제가 생기므로 후보를 먼저 줄인 뒤 AI 판단합니다.

## 현재 주요 구현

Backend:

- `backend/src/argus_v2/cli.py`: `smoke-kis`, `collect-context`, `smoke-news-ai` 실행 입구.
- `backend/src/argus_v2/api/router.py`: dashboard API와 원천 뉴스 피드 API 입구.
- `backend/src/argus_v2/contracts.py`: backend API 응답 계약.
- `backend/src/argus_v2/dashboard.py`: DB 최신값을 화면용 `MarketDashboard`로 조립.
- `backend/src/argus_v2/judgement/engine.py`: 시장 판단 엔진.
- `backend/src/argus_v2/storage.py`: SQLite 저장/조회.
- `backend/src/argus_v2/providers/kis_*`: KIS token, 국내파생, 옵션체인 live provider.
- `backend/src/argus_v2/providers/context_inputs.py`: 현물 반응, 뉴스 트리거, 원천 뉴스 피드, Gemini AI enrichment.
- `backend/src/config/env.py`: env 기반 설정.

Frontend:

- `frontend/src/app/argus/page.tsx`: 첫 화면.
- `frontend/src/app/argus/derivatives/page.tsx`: 파생/옵션 상세.
- `frontend/src/app/argus/reaction/page.tsx`: 현물 반응 상세.
- `frontend/src/app/argus/triggers/page.tsx`: 뉴스 분석 메인, 뉴스/매크로 trigger 상세.
- `frontend/src/app/argus/triggers/news/page.tsx`: 실시간 원천 뉴스 피드.
- `frontend/src/argus_v2/components/dashboard.tsx`: 대시보드 UI.
- `frontend/src/argus_v2/contracts/dashboard.ts`: frontend Zod 계약.
- `frontend/src/argus_v2/server/dashboard.ts`: backend dashboard API 호출.

Docs:

- `doc/prd/argus-v2-prd.md`: 제품 요구사항.
- `doc/plans/mvp-closeout.md`: MVP 완료 기준과 남은 작업.
- `doc/plans/current-status.md`: 현재 상태 한 장 요약.
- `doc/study/`: 구조 학습 문서.

## 확정된 설계 결정

- SQLite를 로컬 DB로 사용합니다.
- 나중에 운영 규모가 커지면 PostgreSQL로 갈 수 있게 storage 책임을 분리합니다.
- 외부 API 호출은 frontend에서 직접 하지 않습니다.
- 시장 판단 화면은 dashboard API를 봅니다.
- 원천 뉴스 화면은 news-feed API를 봅니다.
- 수집은 CLI 또는 추후 스케줄러가 담당합니다.
- provider는 외부 API 응답을 Argus 내부 record로 변환합니다.
- storage는 provider run과 raw sample을 저장하고 민감값을 redaction합니다.
- dashboard builder는 DB를 읽어 화면용 데이터로 조립합니다.
- judgement engine은 구조화된 데이터만 보고 판단합니다.
- 뉴스 판단은 키워드 문자열 규칙이 아니라 AI JSON 응답을 기준으로 합니다.
- AI가 실패하거나 꺼져 있으면 실뉴스는 표시하지 않습니다.
- 원천 뉴스 피드는 AI 판단 실패 여부와 무관하게 최신 뉴스 아이템을 표시합니다.
- 테스트는 핵심 계약을 지키되, 테스트 작성이 개발 속도를 잡아먹지 않게 유지합니다.

## AI 뉴스 판단 정책

현재 정책:

- RSS/Naver/DART는 원문 수집 담당입니다.
- 호재/악재, 중요도, 연결강도, 사용 여부는 AI enrichment JSON이 결정합니다.
- AI 판단 JSON에는 `should_use`, `impact`, `relevance_score`, `connection_strength`, `confidence`, `summary`, `reason`, `affected_factors`가 들어갑니다.
- 저장된 trigger는 frontend에서 AI reason, confidence, affected factors로 표시됩니다.

원천 뉴스 피드 정책:

- `/api/argus/v2/news-feed`는 AI 판단을 거치지 않은 최신 원천 뉴스 아이템을 반환합니다.
- 기본 provider는 `ARGUS_NEWS_FEED_PROVIDER=rss`입니다.
- `ARGUS_NEWS_FEED_RSS_URLS`가 비어 있으면 `ARGUS_NEWS_TRIGGERS_RSS_URLS`를 재사용합니다.
- 원천 뉴스 피드는 title, summary, source, published_at, source_url, freshness 중심으로 표시합니다.

운영 기본값:

```text
ARGUS_NEWS_AI_PROVIDER=gemini
ARGUS_GEMINI_MODEL=gemini-2.5-flash
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

중요한 제한:

- RSS 후보 전체를 AI에 보내지 않습니다.
- 먼저 시간순, query match, 후보 제한을 적용합니다.
- 이후 제한된 후보만 Gemini에 보냅니다.
- timeout/429가 있으면 해당 후보는 버리고 전체 provider는 계속 진행합니다.

## 판단 엔진 현황

현재 판단 엔진은 아래 신호를 봅니다.

- KOSPI200 선물 변동률.
- basis, market basis.
- 선물 미결제약정 증감률.
- 옵션체인 CALL/PUT 압력과 OI 변화.
- 현물 지수 반응.
- 현물 상승/하락 종목 수.
- 현물 강세/약세 섹터.
- 뉴스/매크로 trigger.
- 외국인 현물 수급 보조 신호.

현재 라벨:

```text
강한 상방
상방 우위
중립
하방 우위
강한 하방
```

주의:

- KOSPI200 시장 전체 외국인/기관/개인 선물 수급 endpoint는 아직 공식 확인 전입니다.
- 계좌 기반 잔고/손익 API는 시장 전체 수급으로 쓰지 않습니다.
- 선물 수급이 없을 때만 외국인 현물 수급을 보조 신호로 씁니다.
- 선물/현물 외국인 수급이 충돌하면 반대 증거로 표시합니다.

## 완료된 작업

- PRD 기준 재정리.
- 레거시 KRX route/runtime 제거.
- v2 backend runtime 단순화.
- KIS token 자동 발급/cache 구조 정리.
- KIS 국내파생 provider 이관.
- KIS 옵션체인 provider 이관.
- KIS 현물 반응 provider 추가.
- KIS 시장별 투자자매매동향을 현물 수급 계약으로 추가.
- SQLite 저장소 계약 구성.
- provider run 저장.
- redacted raw sample 저장.
- derivatives snapshot 저장.
- option chain snapshot/level 저장.
- market reaction snapshot/sector 저장.
- news trigger 저장.
- dashboard API DB-first 조회.
- mock fallback 유지.
- Gemini provider 추가.
- `smoke-news-ai` CLI 추가.
- RSS live 뉴스 -> Gemini 판단 -> DB 저장 확인.
- 뉴스 AI reason/confidence/factors frontend 표시 계약 추가.
- 뉴스 분석 상단 탭 rename.
- 뉴스 분석 내부 `메인` / `뉴스` 서브탭 추가.
- `/argus/triggers/news` 원천 뉴스 피드 화면 추가.
- `/api/argus/v2/news-feed` API와 frontend Zod 계약 추가.
- PRD 기준 4탭 UI 구성.
- 리서치 데스크 디자인 톤 적용.
- 공부 문서 작성 및 보강.

## In Progress

- KIS 장중 반복 수집 관찰.
- provider health와 freshness 기준 운영 보정.
- Gemini prompt/schema 운영 보정.
- 판단 엔진 가중치 보정.
- 매크로 실제 source 결정.
- 원천 뉴스 피드 source 확대와 필터/중복 제거 UX 보정.

## Next

1. 장중에 `smoke-kis`와 `collect-context --market-reaction-provider kis`를 2회 이상 반복 실행합니다.
2. provider health에서 fresh/partial/stale/missing 표시가 실제 운영 감각과 맞는지 확인합니다.
3. RSS 수집에서 timeout/429 빈도를 관찰하고 limit/timeout을 조정합니다.
4. `/argus/triggers/news`에서 source, 중복, 기사 품질을 관찰합니다.
5. 실제 장중 사례를 모아 judgement engine 가중치를 보정합니다.
6. 매크로 이벤트 source를 결정합니다.
7. 장중 자동 수집 스케줄러를 붙일지 결정합니다.

## Risks

- KIS field와 TR 응답은 문서와 실제가 다를 수 있습니다.
- KIS 보조 API 일부는 실패 로그가 있을 수 있으므로 provider health를 봐야 합니다.
- Gemini 응답은 모델, rate limit, prompt에 따라 흔들릴 수 있습니다.
- RSS 기사 품질이 낮으면 AI 판단 전에 후보 제한을 더 강하게 해야 합니다.
- 원천 뉴스 피드가 많아지면 중복 제거, source 필터, 중요도 표시가 필요합니다.
- 판단 엔진은 아직 1차 버전이므로 실제 장중 사례로 보정해야 합니다.
- 테스트는 핵심 계약 위주로 유지해야 합니다.

## Last Updated

- 2026-05-14
