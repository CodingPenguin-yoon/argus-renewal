# MVP Closeout

## 목적

Argus v2를 실제 장 시작 전과 장중에 켜서 확인할 수 있는 최소 제품으로 닫기 위한 작업 목록입니다.

MVP 완료 기준은 완벽한 판단 튜닝이 아니라 `실제 데이터 수집 -> AI 뉴스 판단 -> DB 저장 -> 화면 확인 -> 실패 원인 확인` 폐쇄 루프가 동작하는 것입니다.

## 현재 판정

- 레거시 전환: 완료.
- MVP 상태: 폐쇄 루프 구성 완료, live AI 검증은 Gemini 실키 입력 대기.
- 주요 차단: `backend/.env`에 Gemini 실키가 아직 없습니다.
- 2026-05-13 확인: `smoke-kis` 성공, KIS `collect-context` 성공, RSS 수집 경로 성공. 단, AI disabled 상태라 live 뉴스 trigger 저장은 0건입니다.

## MVP 필수 작업

### 1. Gemini 실키 smoke test

상태: 명령 동작 확인, 키 입력 대기.

필요 env:

```bash
ARGUS_NEWS_AI_PROVIDER=gemini
ARGUS_GEMINI_MODEL=gemini-3-flash
ARGUS_GEMINI_API_KEY=...
```

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
```

완료 기준:

- `status`가 `success`입니다.
- `should_use`, `impact`, `relevance_score`, `connection_strength`, `confidence`가 JSON으로 반환됩니다.
- 키가 없거나 실패하면 실뉴스를 임의 분류하지 않습니다.

최근 결과:

- `ARGUS_NEWS_AI_PROVIDER`가 disabled라 `status=failed`, `reason=news_ai_disabled`로 정상 차단됩니다.

### 2. 실뉴스 source 1개 live 연결 확인

상태: RSS 경로 성공, Gemini 실키 입력 후 DB 저장 확인 필요.

우선 source:

- RSS

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli collect-context --skip-market-reaction --news-triggers-provider rss
```

완료 기준:

- RSS 원문 수집이 성공합니다.
- Gemini 판단을 거친 trigger만 `argus_v2_news_triggers`에 저장됩니다.
- `/argus/triggers`에서 뉴스 제목, 요약, AI 근거, confidence, affected factors를 확인할 수 있습니다.

최근 결과:

- RSS provider 실행은 성공했습니다.
- AI disabled 상태라 `news_trigger_count=0`입니다. 실키 입력 후 재실행해야 live 뉴스 저장까지 닫힙니다.

### 3. KIS 데이터 반복 수집 확인

상태: 1회 smoke/collect 성공, 장중 반복 관찰 필요.

확인 명령:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --skip-news-triggers
```

완료 기준:

- 파생 snapshot이 저장됩니다.
- 옵션체인 snapshot/level이 저장됩니다.
- 현물 반응과 현물 투자자 수급이 저장됩니다.
- provider health에서 success/partial/failed 원인을 확인할 수 있습니다.

최근 결과:

- `smoke-kis`: token 자동 발급, 국내파생 snapshot 1건, 옵션체인 sample 100건 성공.
- `collect-context --market-reaction-provider kis --skip-news-triggers`: market reaction snapshot 1건 저장 성공.
- 일부 KIS 보조 API 실패 로그가 있어 장중 반복 실행으로 freshness와 provider health를 봐야 합니다.

주의:

- 장중이 아니면 일부 값이 stale/partial일 수 있습니다.
- KOSPI200 시장 전체 외국인/기관/개인 선물 수급은 아직 공식 endpoint 미확인이라 현물 수급을 보조 신호로만 씁니다.

### 4. 프런트 뉴스 AI 근거 표시

상태: 완료.

표시 항목:

- AI reason
- AI confidence
- affected factors
- AI 꺼짐/실패 시 empty state

완료 기준:

- 첫 화면 대표 뉴스 카드에서 AI 근거를 볼 수 있습니다.
- `/argus/triggers` 상세에서 source, confidence, affected factors를 볼 수 있습니다.

### 5. MVP 실행 명령 정리

상태: 완료.

문서:

- `RUN_GUIDE.md`
- `README.md`
- `backend/README.md`
- `doc/plans/mvp-closeout.md`

MVP 기본 실행 순서:

```bash
cd backend
python3 -m src.argus_v2.cli smoke-news-ai
python3 -m src.argus_v2.cli smoke-kis
python3 -m src.argus_v2.cli collect-context --market-reaction-provider kis --news-triggers-provider rss
```

화면 확인:

```text
http://localhost:3000/argus
http://localhost:3000/argus/triggers
```

## MVP 이후 작업

- Gemini prompt/schema 운영 보정
- 매크로 실제 source 결정
- 판단 엔진 가중치 보정
- KIS 장중 반복 수집 자동화
- DB 보관 기간과 실패 로그 정책

## 남은 작업 목록

- [ ] `backend/.env`에 `ARGUS_NEWS_AI_PROVIDER=gemini`, `ARGUS_GEMINI_MODEL=gemini-3-flash`, `ARGUS_GEMINI_API_KEY` 입력.
- [ ] `smoke-news-ai`가 `status=success`를 반환하는지 확인.
- [ ] RSS live 뉴스가 Gemini 판단을 거쳐 DB에 저장되는지 확인.
- [ ] `/argus/triggers`에서 live 뉴스의 AI reason, confidence, affected factors 확인.
- [ ] 장중 KIS `smoke-kis`와 `collect-context --market-reaction-provider kis`를 2회 이상 반복해 freshness/provider health 확인.
- [ ] 실제 장중 케이스를 보고 판단 엔진 가중치와 Gemini prompt를 보정.

## Last Updated

- 2026-05-13
