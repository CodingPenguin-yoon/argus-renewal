# 03. Argus 실제 흐름

이 문서는 Argus v2에서 데이터가 실제로 어떻게 움직이는지 설명합니다.

핵심은 두 흐름입니다.

```text
수집 흐름 = CLI가 외부 데이터를 가져와 DB에 저장
조회 흐름 = frontend가 API를 통해 DB 최신값 조회
```

## 1. 화면을 열 때 흐름

사용자가 `/argus`를 열면 흐름은 이렇습니다.

```text
브라우저
-> frontend /argus page
-> frontend server/dashboard.ts
-> backend /api/argus/v2/dashboard
-> SQLite DB 조회
-> dashboard builder
-> judgement engine
-> MarketDashboard JSON
-> frontend component 표시
```

중요:

```text
화면을 열 때 KIS, RSS, Gemini를 직접 호출하지 않습니다.
```

화면은 이미 DB에 쌓인 최신 데이터를 읽습니다.

## 2. `/argus` 화면 파일

대표 route:

```text
frontend/src/app/argus/page.tsx
```

역할:

- dashboard 데이터를 가져옵니다.
- `MarketDashboardView` 같은 화면 component에 넘깁니다.
- 직접 외부 API를 호출하지 않습니다.

관련 파일:

```text
frontend/src/argus_v2/server/dashboard.ts
frontend/src/argus_v2/components/dashboard.tsx
frontend/src/argus_v2/contracts/dashboard.ts
```

각 역할:

```text
server/dashboard.ts = backend API 호출
components/dashboard.tsx = 화면 표시
contracts/dashboard.ts = JSON 모양 검사
```

## 3. Dashboard API 흐름

backend API 입구:

```text
backend/src/argus_v2/api/router.py
```

흐름:

```text
GET /api/argus/v2/dashboard
-> DB 연결
-> ArgusV2Storage 생성
-> build_dashboard_from_storage()
-> DB 최신값 있으면 반환
-> DB 비어 있으면 mock fallback 반환
```

API는 얇습니다.

여기서 KIS나 Gemini를 직접 호출하지 않습니다.

## 4. Dashboard Builder 흐름

위치:

```text
backend/src/argus_v2/dashboard.py
```

하는 일:

```text
1. 최신 derivatives snapshot 읽기
2. 최신 option chain snapshot 읽기
3. 최신 market reaction snapshot 읽기
4. 최신 news triggers 읽기
5. provider health 만들기
6. judgement engine 호출하기
7. MarketDashboard로 묶기
```

뉴스 AI 필드도 여기서 dashboard contract로 옮깁니다.

예:

```text
raw sample 안의 _argus_ai.reason
-> TriggerEvent.ai_reason
```

```text
raw sample 안의 _argus_ai.confidence
-> TriggerEvent.ai_confidence
```

```text
raw sample 안의 _argus_ai.affected_factors
-> TriggerEvent.affected_factors
```

## 5. Judgement Engine 흐름

위치:

```text
backend/src/argus_v2/judgement/engine.py
```

입력:

- derivatives pressure.
- option pressure.
- market reaction.
- news triggers.
- provider health.

출력:

- 판단 라벨.
- confidence.
- summary.
- evidence.
- contradictory evidence.

현재 판단 라벨:

```text
강한 상방
상방 우위
중립
하방 우위
강한 하방
```

중요:

```text
judgement engine은 외부 API 응답 원본을 직접 보지 않습니다.
이미 정리된 내부 구조만 봅니다.
```

## 6. KIS 파생/옵션 수집 흐름

명령:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

흐름:

```text
cli.py
-> run_kis_live_smoke()
-> KIS token 발급 또는 cache 사용
-> domestic derivatives provider
-> option chain provider
-> raw sample redaction
-> SQLite 저장
-> 실행 결과 JSON 출력
```

관련 파일:

```text
backend/src/argus_v2/providers/kis_auth.py
backend/src/argus_v2/providers/kis_live.py
backend/src/argus_v2/providers/kis_derivatives.py
backend/src/argus_v2/providers/kis_option_chain.py
backend/src/argus_v2/storage.py
```

저장되는 것:

```text
argus_v2_provider_runs
argus_v2_provider_samples
argus_v2_derivatives_snapshots
argus_v2_option_chain_snapshots
argus_v2_option_chain_levels
```

현재 확인:

- token 자동 발급.
- 국내파생 snapshot 1건.
- 옵션체인 sample 100건.

## 7. KIS 현물 반응 수집 흐름

명령:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

흐름:

```text
cli.py
-> run_context_collection()
-> KIS market reaction provider
-> KOSPI/KOSDAQ 지수 반응
-> 상승/하락 종목 수
-> 강세/약세 섹터
-> 현물 투자자 수급
-> SQLite 저장
```

관련 파일:

```text
backend/src/argus_v2/providers/context_inputs.py
backend/src/argus_v2/storage.py
```

저장되는 것:

```text
argus_v2_market_reaction_snapshots
argus_v2_market_reaction_sectors
argus_v2_provider_runs
argus_v2_provider_samples
```

주의:

- 일부 KIS 보조 API는 실패할 수 있습니다.
- provider result와 provider health를 봐야 합니다.
- KOSPI200 시장 전체 선물 수급은 아직 공식 endpoint 미확인입니다.

## 8. RSS 뉴스 + Gemini AI 판단 흐름

명령:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

흐름:

```text
cli.py
-> run_context_collection()
-> ArgusNewsTriggerService
-> RSS feed 수집
-> RSS item을 NewsTriggerRecord 후보로 변환
-> query/limit으로 AI 후보 제한
-> Gemini AI 판단 요청
-> should_use=true인 후보만 선택
-> raw sample 저장
-> news trigger 저장
```

관련 파일:

```text
backend/src/argus_v2/providers/context_inputs.py
backend/src/argus_v2/storage.py
backend/src/config/env.py
```

AI 판단 JSON:

```json
{
  "should_use": true,
  "impact": "negative",
  "relevance_score": 90,
  "connection_strength": "strong",
  "confidence": "high",
  "summary": "미국 금리 상승과 달러 강세가 위험자산에 부담입니다.",
  "reason": "해외 금리와 달러는 한국장 외국인 수급과 지수 심리에 연결됩니다.",
  "affected_factors": ["금리", "환율", "외국인 수급"]
}
```

저장되는 곳:

```text
argus_v2_news_triggers
argus_v2_provider_samples
argus_v2_provider_runs
```

raw sample에는 AI 정보가 같이 들어갑니다.

```text
_argus_ai
_argus_ai_provider
_argus_ai_should_use
_argus_ai_relevance_score
_argus_ai_confidence
```

## 9. 왜 AI 후보를 먼저 줄이나

RSS는 기사 후보가 많습니다.

후보 전체를 Gemini에 보내면 문제가 생깁니다.

- 느립니다.
- 비용이 늘어납니다.
- 429 Too Many Requests가 날 수 있습니다.
- timeout이 늘어납니다.
- 잡음 뉴스까지 판단하게 됩니다.

그래서 Argus는 AI 호출 전에 후보를 줄입니다.

흐름:

```text
RSS 전체 후보
-> 최신순 정렬
-> query term 매칭
-> candidate limit 적용
-> Gemini 호출
```

현재 기본값:

```text
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

## 10. Gemini smoke 흐름

명령:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

흐름:

```text
cli.py
-> run_news_ai_smoke()
-> 신뢰 가능한 시장 뉴스 형태의 sample 생성
-> Gemini AI 판단 요청
-> JSON 결과 출력
-> DB 저장 없음
```

용도:

- Gemini key가 맞는지 확인.
- 모델명이 맞는지 확인.
- AI JSON schema가 동작하는지 확인.
- DB에 저장하지 않고 빠르게 확인.

성공 예:

```json
{
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "status": "success",
  "should_use": true,
  "impact": "negative",
  "relevance_score": 90,
  "connection_strength": "strong",
  "confidence": "high"
}
```

## 11. Storage가 저장하는 대표 테이블

provider 실행 기록:

```text
argus_v2_provider_runs
```

외부 응답 샘플:

```text
argus_v2_provider_samples
```

파생 snapshot:

```text
argus_v2_derivatives_snapshots
```

옵션체인:

```text
argus_v2_option_chain_snapshots
argus_v2_option_chain_levels
```

현물 반응:

```text
argus_v2_market_reaction_snapshots
argus_v2_market_reaction_sectors
```

뉴스 trigger:

```text
argus_v2_news_triggers
```

## 12. Provider Run이 남기는 의미

예를 들어 뉴스 수집 결과가 0건일 수 있습니다.

이때 가능한 이유:

```text
RSS 수집 실패
Gemini key 없음
Gemini timeout
Gemini 429
AI가 should_use=false 판단
저장할 trigger 없음
```

provider run metadata가 있으면 원인을 좁힐 수 있습니다.

예:

```text
input_count
ai_candidate_count
ai_enriched_count
ai_selected_count
ai_error_count
ai_disabled_count
filtered_count
```

## 13. Dashboard에서 뉴스 AI 정보를 읽는 흐름

저장 시:

```text
raw sample payload_json 안에 _argus_ai 저장
```

dashboard 조립 시:

```text
_trigger_ai_payload()
-> _argus_ai 또는 ai_enrichment 읽기
-> TriggerEvent.ai_reason
-> TriggerEvent.ai_confidence
-> TriggerEvent.affected_factors
```

frontend 표시:

```text
frontend/src/argus_v2/components/dashboard.tsx
```

표시되는 것:

- AI reason.
- AI confidence.
- affected factors.
- source.
- published_at.

## 14. 실제 장 시작 전 실행 예

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

이후 화면:

```text
http://localhost:3000/argus
http://localhost:3000/argus/triggers
```

## 15. 장중 수시 확인 예

KIS와 뉴스 둘 다:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

KIS만:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

뉴스만:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

## 16. API와 CLI의 차이 다시 정리

```text
CLI = 외부 API 호출, DB 저장, 운영 수집
API = DB 조회, dashboard 반환
frontend = API 결과 표시
```

이 구조를 유지해야 장중 화면이 안정적입니다.

## 17. 한 줄 요약

```text
smoke-kis와 collect-context가 데이터를 쌓고,
dashboard API가 그 데이터를 읽고,
frontend가 판단과 근거를 보여준다.
```
