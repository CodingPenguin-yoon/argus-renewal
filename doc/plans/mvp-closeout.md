# MVP Closeout

## 목적

이 문서는 Argus v2를 “실제로 켜서 시장 상황을 확인할 수 있는 최소 제품”으로 닫기 위한 기준 문서입니다.

MVP의 목표는 완벽한 예측이 아닙니다.

목표는 아래 폐쇄 루프가 실제로 동작하는 것입니다.

```text
실제 데이터 수집
-> AI 뉴스 판단
-> DB 저장
-> dashboard API 조회
-> 화면 표시
-> 실패 원인 확인
```

## 현재 판정

- MVP 상태: 기술 폐쇄 루프 완료.
- 레거시 전환: 완료.
- 주요 차단: 없음.
- 남은 핵심: 브라우저 화면 최종 확인, 장중 반복 관찰, 판단 품질 보정.
- 기준 날짜: 2026-05-13.

확인된 live 결과:

- Gemini key 인식 완료.
- `smoke-news-ai` 성공.
- RSS live 뉴스 1건 DB 저장 성공.
- 저장된 trigger에 AI payload, confidence, affected factors 포함 확인.
- dashboard 계약에서 `ai_reason`, `ai_confidence`, `affected_factors` 확인.
- `smoke-kis` 성공.
- KIS 국내파생 snapshot 1건 저장 확인.
- KIS 옵션체인 sample 100건 확인.
- KIS market reaction `collect-context` 성공.

중요한 모델 결정:

- `gemini-3-flash`: API 404.
- `gemini-3-flash-preview`: 단건 smoke는 성공, RSS 수집 중 timeout/429 발생.
- `gemini-2.5-flash`: MVP 기본 모델.

## 운영 기본 env

`backend/.env` 기준입니다.

```env
ARGUS_NEWS_AI_PROVIDER=gemini
ARGUS_GEMINI_MODEL=gemini-2.5-flash
ARGUS_GEMINI_API_KEY=
ARGUS_NEWS_TRIGGERS_LIMIT=3
ARGUS_NEWS_AI_TIMEOUT_SECONDS=8
```

KIS는 token을 직접 넣지 않습니다.

```env
KIS_APP_KEY=
KIS_APP_SECRET=
```

token은 실행 시 발급하고 `backend/data/kis_token_cache.json`에 캐시합니다.

## MVP 필수 작업 상태

### 1. Gemini smoke test

상태: 완료.

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

완료 기준:

- `status=success`.
- `provider=gemini`.
- `model=gemini-2.5-flash`.
- `should_use`, `impact`, `relevance_score`, `connection_strength`, `confidence`, `reason`, `summary` 반환.

현재 결과:

- 성공.
- 기본 smoke source를 신뢰 가능한 시장 뉴스 출처 형태로 맞춰 `should_use=true`까지 확인.
- 키가 없거나 provider가 disabled면 `news_ai_disabled`로 정상 차단.

### 2. RSS live 뉴스 -> Gemini 판단 -> DB 저장

상태: 완료.

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

완료 기준:

- RSS 원문 수집 성공.
- Gemini 판단 실행.
- `should_use=true`인 뉴스만 `argus_v2_news_triggers`에 저장.
- raw sample에는 `_argus_ai`, `_argus_ai_confidence`, `_argus_ai_relevance_score` 포함.
- dashboard에서 AI reason/confidence/factors 읽기 가능.

현재 결과:

- `gemini-2.5-flash`, `ARGUS_NEWS_TRIGGERS_LIMIT=1`, `ARGUS_NEWS_AI_TIMEOUT_SECONDS=8` 조건에서 live 뉴스 1건 저장 확인.
- 이후 운영 기본값은 limit 3, timeout 8초로 설정.
- RSS 후보 전체를 AI에 보내지 않도록 코드 보정 완료.

주의:

- RSS 기사 후보가 많으면 Gemini rate limit과 timeout이 발생합니다.
- 후보 제한은 비용과 안정성을 위해 필수입니다.
- AI 실패 후보는 버리고 provider 전체는 계속 진행합니다.

### 3. KIS 파생/옵션 smoke

상태: 완료, 장중 반복 관찰 필요.

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
```

완료 기준:

- KIS token 발급 또는 cache 사용.
- 국내파생 snapshot 저장.
- 옵션체인 snapshot/level 저장.
- provider result가 success 또는 원인 있는 partial/failed로 반환.

현재 결과:

- token 자동 발급.
- 국내파생 snapshot 1건.
- 옵션체인 sample 100건.
- DB 저장 성공.

주의:

- 장중이 아니면 일부 데이터가 stale 또는 partial일 수 있습니다.
- KIS 응답 field는 문서와 다를 수 있으므로 raw sample이 중요합니다.

### 4. KIS 현물 반응 collect

상태: 1회 성공, 장중 반복 관찰 필요.

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

완료 기준:

- market reaction snapshot 저장.
- KOSPI/KOSDAQ 등락률 확인.
- 상승/하락 종목 수 확인.
- 강세/약세 섹터 저장.
- 현물 투자자 수급 저장.

현재 결과:

- market reaction snapshot 1건 저장 성공.
- 일부 KIS 보조 API 실패 로그가 있었으므로 장중 반복 확인 필요.

주의:

- KOSPI200 시장 전체 외국인/기관/개인 선물 수급 endpoint는 아직 공식 확인 전입니다.
- 계좌 기반 API는 시장 전체 수급으로 쓰지 않습니다.
- 현물 외국인 수급은 선물 수급이 없을 때 보조 신호로만 씁니다.

### 5. Frontend AI reason/confidence/factors 표시

상태: 계약 완료, 브라우저 최종 확인 필요.

표시 항목:

- 뉴스 제목.
- AI 요약.
- AI reason.
- AI confidence.
- affected factors.
- source.
- published_at.
- AI 꺼짐/실패 시 empty state.

확인 화면:

```text
http://localhost:3000/argus
http://localhost:3000/argus/triggers
http://localhost:3000/argus/triggers/news
```

확인 결과:

- `/argus/triggers/news`는 200 OK 응답을 확인했습니다.
- `/api/argus/v2/news-feed`에서 RSS 원천 뉴스 50건 수신을 확인했습니다.

## MVP 기본 실행 순서

장 시작 전:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

장중 수시 확인:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

뉴스만 확인:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

KIS만 확인:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

## 대시보드 확인 순서

1. `/argus`에서 전체 판단 라벨을 봅니다.
2. 핵심 수급 카드에서 파생/옵션 압력을 봅니다.
3. 대표 뉴스 카드에서 AI reason을 봅니다.
4. `/argus/derivatives`에서 옵션/선물 상세를 봅니다.
5. `/argus/reaction`에서 현물 반응과 섹터를 봅니다.
6. `/argus/triggers`에서 뉴스 분석 메인의 뉴스/매크로 trigger를 봅니다.
7. `/argus/triggers/news`에서 실시간 원천 뉴스 피드를 봅니다.
8. provider health에서 데이터 수신 상태를 봅니다.

## 남은 작업 목록

- [x] `backend/.env`에 Gemini key 입력.
- [x] Gemini 모델을 `gemini-2.5-flash`로 확정.
- [x] `smoke-news-ai` success 확인.
- [x] RSS live 뉴스가 Gemini 판단을 거쳐 DB에 저장되는지 확인.
- [x] dashboard 계약에서 live 뉴스 AI reason/confidence/factors 확인.
- [x] RSS 후보 제한을 AI 호출 전에 적용.
- [x] `/api/argus/v2/news-feed` 원천 뉴스 피드 API 추가.
- [x] `/argus/triggers/news` 실시간 뉴스 서브탭 추가.
- [x] `/argus/triggers/news` route 200 OK 확인.
- [x] RSS 원천 뉴스 50건 수신 확인.
- [x] KIS `smoke-kis` 1회 성공 확인.
- [x] KIS market reaction `collect-context` 1회 성공 확인.
- [ ] 장중 KIS `smoke-kis` 2회 이상 반복.
- [ ] 장중 `collect-context --market-reaction-provider kis --news-triggers-provider rss` 2회 이상 반복.
- [ ] provider health fresh/partial/stale/missing 기준 운영 보정.
- [ ] Gemini prompt/schema 운영 보정.
- [ ] 판단 엔진 가중치 실제 장중 사례로 보정.
- [ ] 매크로 실제 source 결정.
- [ ] 장중 자동 수집 스케줄러 도입 여부 결정.

## MVP 이후 작업

제품 품질:

- 판단 엔진 가중치 보정.
- 뉴스 trigger 품질 보정.
- 매크로 source 추가.
- provider health UI 개선.
- 장중 반복 수집 자동화.
- DB 보관 기간 정책.

데이터 품질:

- KIS field alias 추가 보정.
- KIS 보조 API 실패 원인 분리.
- option OI 변화율 운영 관찰.
- 현물 수급 단위 배율 재확인.
- RSS source 품질 개선.
- Naver/DART/hybrid source 운영 여부 결정.

운영:

- cron 또는 scheduler 추가 여부 결정.
- provider run 실패 알림 여부 결정.
- raw sample 보관 기간 결정.
- API rate limit 대응 정책 결정.

## Last Updated

- 2026-05-13
