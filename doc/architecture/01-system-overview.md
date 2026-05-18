# 시스템 개요

## 한 줄 정의

Argus v2는 한국장 시장 상태를 `파생/옵션 -> 뉴스/매크로 -> 현물 반응` 순서로 읽고, 그 결과를 rule-based 판단 엔진과 dashboard 화면으로 보여주는 시장 상황판입니다.

이 제품은 뉴스 앱, 종목 추천 앱, 자동매매 도구가 아닙니다. 사용자가 빠르게 알고 싶은 것은 “무슨 종목을 사야 하는가”가 아니라 “현재 시장 압력이 어디로 기울었고, 그 근거가 무엇인가”입니다.

## 전체 런타임 구조

```text
외부 데이터
  - KIS 국내파생
  - KIS 옵션체인
  - KIS 현물 반응
  - RSS/Naver/DART 뉴스
  - macro event
  - mock/file fallback

        |
        v

provider layer
  - 외부 응답을 내부 record로 변환
  - 민감 정보는 저장 전에 redaction
  - provider run 상태 기록

        |
        v

SQLite storage
  - provider_runs
  - provider_samples
  - derivatives snapshots
  - option chain snapshots/levels
  - market reaction snapshots/sectors
  - news triggers

        |
        v

dashboard builder
  - 최신 DB snapshot 조회
  - 화면용 MarketDashboard 조립
  - 옵션 OI 변화, provider health, freshness 계산

        |
        v

judgement engine
  - 5단계 시장 판단 라벨 생성
  - 근거, 반대 근거, 전환 조건, watch point 생성

        |
        v

FastAPI
  - GET /api/argus/v2/dashboard
  - GET /api/argus/v2/news-feed

        |
        v

Next.js frontend
  - /argus
  - /argus/derivatives
  - /argus/reaction
  - /argus/triggers
  - /argus/triggers/news
```

## 핵심 경계

### Frontend는 외부 API를 직접 호출하지 않습니다

frontend는 KIS, Naver, DART, Gemini 같은 외부 API를 직접 호출하지 않습니다. frontend는 backend가 만든 Argus 전용 API만 봅니다.

이유:

- 외부 API key를 브라우저에 노출하지 않기 위해
- 외부 응답 형식 변경을 backend provider에서 흡수하기 위해
- 화면 계약을 안정적으로 유지하기 위해
- mock/local fallback을 frontend에서 신경 쓰지 않게 하기 위해

### Provider는 외부 세계와 내부 record 사이의 번역기입니다

provider는 외부 API 응답을 그대로 화면에 넘기지 않습니다. 각 provider는 외부 응답을 Argus 내부 record로 normalize합니다.

예:

```text
KIS 옵션전광판 응답
-> DerivativesOptionChainSnapshotRecord
-> argus_v2_option_chain_snapshots
-> DerivativesPressure
-> 화면
```

### Storage는 수집 이력과 원본 샘플을 남깁니다

Argus는 “현재 값”만 저장하지 않습니다. provider run과 raw sample을 함께 저장합니다.

이유:

- 어떤 provider가 언제 성공/실패했는지 추적
- 화면 데이터가 어떤 원본에서 왔는지 추적
- 수집 실패와 계약 오류를 디버깅
- 나중에 판단 엔진을 다시 보정할 때 근거 확보

### Dashboard API는 화면 계약의 중심입니다

`/api/argus/v2/dashboard`는 시장 판단 화면이 보는 핵심 API입니다.

frontend는 이 API가 내려주는 `MarketDashboard` 계약을 기준으로 렌더링합니다. DB 테이블 구조를 frontend가 알 필요는 없습니다.

### News-feed API는 원천 뉴스 전용입니다

`/api/argus/v2/news-feed`는 AI 판단을 거치지 않은 원천 뉴스 피드를 반환합니다. 이 API는 `뉴스 분석 > 뉴스` 화면에서 사용합니다.

이 API는 시장 판단용 trigger와 분리되어 있습니다.

```text
시장 판단용 trigger
-> AI enrichment 결과 should_use=true
-> /api/argus/v2/dashboard.triggers

원천 뉴스 feed
-> AI 판단 없음
-> /api/argus/v2/news-feed.items
```

## 상단 화면 구조

Argus v2의 상단 탭은 네 개입니다.

```text
시장 판단
옵션·선물
현물 반응
뉴스 분석
```

뉴스 분석 내부는 다시 두 개로 나뉩니다.

```text
메인
뉴스
```

각 화면의 역할:

- `/argus`: 전체 판단, 핵심 수급, 대표 뉴스, 강/약 섹터
- `/argus/derivatives`: 옵션·선물 상세
- `/argus/reaction`: 현물 지수/수급/섹터 반응 상세
- `/argus/triggers`: AI 판단을 거친 뉴스/매크로 trigger
- `/argus/triggers/news`: 실시간 원천 뉴스 피드

## 데이터 신뢰도 모델

Argus는 값이 없을 때 빈칸으로 숨기지 않습니다. freshness와 provider health를 화면에 드러냅니다.

사용하는 상태:

- `fresh`: 정상 수신
- `partial`: 일부 수신
- `stale`: 지연
- `missing`: 미수신

이 상태는 두 곳에 반영됩니다.

- 화면의 데이터 수신 상태
- 판단 엔진의 confidence와 data reliability

## Mock과 live의 관계

Argus는 외부 API key 없이도 로컬에서 실행되어야 합니다.

그래서 mock provider가 있습니다. 다만 mock은 실제 DB 데이터가 없을 때 fallback으로 쓰는 용도입니다.

기본 원칙:

- DB에 live snapshot이 있으면 live DB를 먼저 사용합니다.
- DB가 완전히 비어 있으면 mock dashboard를 사용합니다.
- 실뉴스는 AI 판단 없이 호재/악재로 분류하지 않습니다.
- 원천 뉴스 feed는 AI 판단과 별개로 RSS 기본 provider로 동작할 수 있습니다.

## 확장 방향

현재 구조는 아래 확장을 염두에 둡니다.

- SQLite에서 PostgreSQL로 이동
- CLI 수집에서 scheduler로 이동
- 뉴스 feed source 확대
- macro provider 실제 API 연결
- judgement engine 가중치 보정
- dashboard API versioning
- 원천 뉴스와 AI trigger 간 연결 UI

확장하더라도 지켜야 할 경계:

- frontend는 외부 API를 직접 호출하지 않음
- provider는 내부 record로 normalize
- storage는 provider run과 raw sample을 남김
- judgement engine은 구조화된 계약만 읽음
- 화면은 계약을 렌더링하고 임의 판단을 하지 않음
