# 05. 디버깅과 운영 체크리스트

이 문서는 Argus를 실제로 켰을 때 문제가 생기면 어디부터 봐야 하는지 정리합니다.

핵심은 감으로 찍지 않는 것입니다.

Argus는 provider run, raw sample, DB snapshot, dashboard contract를 남기므로 순서대로 보면 됩니다.

## 1. 장 시작 전 기본 실행

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

각 명령의 의미:

```text
smoke-news-ai = Gemini key/model/schema 확인
smoke-kis = KIS token/파생/옵션체인 확인
collect-context = 현물 반응 + 뉴스 trigger 수집
```

## 2. 장중 수시 확인

전체 수집:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

뉴스만:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

KIS 현물 반응만:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

KIS 파생/옵션 smoke:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

## 3. 화면 확인

대시보드:

```text
http://localhost:3000/argus
```

파생/옵션:

```text
http://localhost:3000/argus/derivatives
```

현물 반응:

```text
http://localhost:3000/argus/reaction
```

뉴스/매크로 trigger:

```text
http://localhost:3000/argus/triggers
```

원천 뉴스 feed:

```text
http://localhost:3000/argus/triggers/news
```

확인할 것:

- 판단 라벨이 나오는가.
- provider health가 fresh/partial/stale/missing 중 무엇인가.
- 대표 뉴스에 AI reason이 보이는가.
- `/argus/triggers`에서 confidence와 affected factors가 보이는가.
- `/argus/triggers/news`에서 최신 원천 뉴스와 원문 링크가 보이는가.
- 파생/옵션 데이터가 최신인가.
- 현물 반응과 섹터가 표시되는가.

## 4. 뉴스가 안 보일 때

가능한 원인:

- RSS 수집 실패.
- Gemini key 없음.
- Gemini 모델명 오류.
- Gemini timeout.
- Gemini 429 Too Many Requests.
- AI가 `should_use=false` 판단.
- DB 저장은 됐지만 dashboard가 못 읽음.
- frontend contract에서 필드가 누락됨.

확인 순서:

1. `smoke-news-ai`를 실행합니다.
2. `collect-context --skip-market-reaction --news-triggers-provider rss`를 실행합니다.
3. 출력 JSON에서 `news_trigger_count`를 봅니다.
4. provider run metadata에서 `ai_candidate_count`, `ai_enriched_count`, `ai_selected_count`, `ai_error_count`를 봅니다.
5. DB의 `argus_v2_news_triggers`에 저장됐는지 봅니다.
6. raw sample에 `_argus_ai`가 있는지 봅니다.
7. `/argus/triggers` 뉴스 분석 메인 화면을 봅니다.
8. 원천 뉴스 자체가 안 보이면 `/argus/triggers/news`와 `/api/argus/v2/news-feed`를 봅니다.

## 5. Gemini가 실패할 때

대표 실패:

```text
404 Not Found
```

의미:

```text
모델명이 현재 API에서 지원되지 않을 가능성이 큽니다.
```

Argus에서 확인된 사실:

- `gemini-3-flash`는 404였습니다.
- `gemini-3-flash-preview`는 단건 smoke는 성공했지만 RSS live에서 timeout/429가 있었습니다.
- `gemini-2.5-flash`가 MVP 기본 모델입니다.

대표 실패:

```text
429 Too Many Requests
```

의미:

```text
짧은 시간에 너무 많이 호출했거나 현재 rate limit에 걸렸습니다.
```

대응:

- `ARGUS_NEWS_TRIGGERS_LIMIT`를 낮춥니다.
- AI 후보를 더 강하게 줄입니다.
- RSS source 수를 줄입니다.
- 잠시 기다렸다가 다시 실행합니다.

대표 실패:

```text
read operation timed out
```

의미:

```text
Gemini 응답이 설정된 timeout 안에 오지 않았습니다.
```

대응:

- `ARGUS_NEWS_AI_TIMEOUT_SECONDS`를 확인합니다.
- 너무 높이면 수집이 느려집니다.
- 너무 낮으면 좋은 후보도 실패할 수 있습니다.
- MVP 기본값은 8초입니다.

## 6. KIS 데이터가 안 보일 때

가능한 원인:

- `KIS_APP_KEY` 없음.
- `KIS_APP_SECRET` 없음.
- token 발급 실패.
- token cache 문제.
- KIS endpoint 응답 지연.
- 장 시간이 아니라 데이터가 stale.
- KIS field alias 불일치.
- 일부 보조 API 실패.

확인 순서:

1. `smoke-kis`를 실행합니다.
2. 출력 JSON에서 `token_status`를 봅니다.
3. provider별 `status`를 봅니다.
4. derivatives snapshot count를 봅니다.
5. option chain sample count를 봅니다.
6. `collect-context --market-reaction-provider kis --skip-news-triggers`를 실행합니다.
7. market reaction snapshot count를 봅니다.

KIS token 정책:

```text
env에 token을 직접 넣지 않는다.
KIS_APP_KEY/KIS_APP_SECRET으로 발급한다.
token은 backend/data/kis_token_cache.json에 캐시한다.
```

## 7. Provider status 읽는 법

`success`:

```text
실행이 성공했고 저장 가능한 데이터가 있거나 정상적으로 빈 결과를 반환했습니다.
```

`partial`:

```text
일부 데이터는 들어왔지만 일부는 실패했습니다.
```

`failed`:

```text
provider 실행이 실패했습니다.
```

`skipped`:

```text
provider가 꺼져 있거나 필요한 설정이 없습니다.
```

주의:

```text
status가 success라도 news_trigger_count가 0일 수 있습니다.
```

예를 들어 AI가 모든 뉴스를 `should_use=false`로 판단하면 provider 실행은 성공이지만 저장 trigger는 0건입니다.

## 8. DB에서 직접 확인할 때

SQLite DB:

```text
backend/data/argus.db
```

테이블 확인:

```bash
cd backend
sqlite3 data/argus.db ".tables"
```

최근 provider run:

```bash
cd backend
sqlite3 data/argus.db "SELECT id, provider_key, status, observed_count, sample_count, created_at FROM argus_v2_provider_runs ORDER BY id DESC LIMIT 10;"
```

최근 뉴스 trigger:

```bash
cd backend
sqlite3 data/argus.db "SELECT id, title, impact, connection_strength, source_name, published_at FROM argus_v2_news_triggers ORDER BY id DESC LIMIT 5;"
```

최근 raw sample:

```bash
cd backend
sqlite3 data/argus.db "SELECT id, provider_key, payload_json FROM argus_v2_provider_samples ORDER BY id DESC LIMIT 1;"
```

주의:

- raw sample에는 긴 JSON이 들어갈 수 있습니다.
- secret은 redaction되어야 합니다.
- 터미널에 key를 출력하지 않도록 조심합니다.

## 9. Dashboard가 이상할 때

증상:

```text
DB에는 데이터가 있는데 화면이 mock처럼 보임
```

확인:

- backend API가 올바른 DB_PATH를 쓰는지 확인합니다.
- frontend가 올바른 backend URL을 호출하는지 확인합니다.
- `backend/data/argus.db`에 실제 데이터가 있는지 확인합니다.
- dashboard API 응답이 비어 있는지 확인합니다.

증상:

```text
뉴스는 저장됐는데 AI reason이 안 보임
```

확인:

- raw sample에 `_argus_ai`가 있는지 확인합니다.
- `dashboard.py`의 `_trigger_ai_payload()`가 해당 key를 읽는지 확인합니다.
- `contracts.py`에 `ai_reason`, `ai_confidence`, `affected_factors`가 있는지 확인합니다.
- frontend Zod contract에 같은 필드가 있는지 확인합니다.
- `dashboard.tsx`에서 실제로 표시하는지 확인합니다.

## 10. 환경변수 확인

중요 env:

```env
KIS_APP_KEY=
KIS_APP_SECRET=
ARGUS_NEWS_AI_PROVIDER=gemini
ARGUS_GEMINI_MODEL=gemini-2.5-flash
ARGUS_GEMINI_API_KEY=
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

확인할 때 주의:

- key 값을 터미널에 그대로 출력하지 않습니다.
- 변수명만 확인합니다.
- `.env.example`에는 실제 key를 넣지 않습니다.

## 11. 장중 운영 메모

장중에는 완벽한 수집보다 빠른 확인이 중요합니다.

추천 방식:

```text
1. smoke-kis로 KIS 파생/옵션 연결 확인
2. collect-context로 현물 반응과 뉴스 수집
3. /argus에서 판단 라벨과 핵심 수급 확인
4. /argus/triggers에서 뉴스 AI 근거 확인
5. /argus/triggers/news에서 원천 뉴스 feed 확인
6. provider health가 partial이면 원인을 기록
```

뉴스는 너무 많이 보여주지 않는 것이 좋습니다.

대시보드는 판단에 연결되는 뉴스만 보여주는 편이 낫습니다.

## 12. 문제가 생겼을 때 생각 순서

```text
1. 외부 API가 실패했나?
2. provider가 내부 record로 변환했나?
3. storage가 DB에 저장했나?
4. dashboard가 DB에서 읽었나?
5. judgement engine이 판단에 반영했나?
6. API contract가 필드를 포함하나?
7. frontend contract가 필드를 허용하나?
8. component가 표시하나?
```

이 순서대로 보면 감으로 고치는 일이 줄어듭니다.

## 13. 한 줄 결론

```text
데이터가 안 보이면 화면부터 뜯지 말고,
provider run -> raw sample -> storage -> dashboard -> frontend 순서로 본다.
```
