# 판단 엔진

## 역할

판단 엔진은 구조화된 데이터를 받아 시장 상태 라벨과 설명을 만듭니다.

파일:

```text
backend/src/argus_v2/judgement/engine.py
```

입력:

- `DerivativesPressure`
- `list[TriggerEvent]`
- `MarketReaction`
- `live_provider_missing`

출력:

- `MarketJudgement`

## 판단 라벨

Argus v2는 투자 행동 언어를 쓰지 않습니다.

사용하는 라벨:

```text
강한 상방
상방 우위
중립
하방 우위
강한 하방
```

쓰지 않는 표현:

- 매수
- 매도
- 강력 추천
- 진입
- 청산

## 전체 처리 흐름

```text
build_market_judgement()
-> 핵심 숫자 추출
-> 파생/옵션 점수 계산
-> 뉴스 trigger 점수 계산
-> 현물 반응 점수 계산
-> 섹터 상충 신호 보정
-> score를 5단계 label로 변환
-> confidence 계산
-> data reliability 계산
-> primary driver 선정
-> reasons/counter evidence 구성
-> transition condition/watch points 구성
```

## 주요 입력 신호

### 파생/옵션

현재 판단 엔진이 보는 파생/옵션 신호:

- 외국인 KOSPI200 선물 순매수/순매도
- 외국인 현물 순매수/순매도 보조 신호
- 옵션 미결제약정 CALL/PUT 압력
- KOSPI200 선물 변동률
- basis
- 미결제약정 변화율
- 옵션 OI 변화 dominant side

선물 수급이 없으면 외국인 현물 수급을 보조 신호로 사용합니다.

### 뉴스/매크로 trigger

뉴스는 `TriggerEvent`만 판단 엔진에 들어갑니다.

즉, 원천 뉴스 feed 전체가 판단 엔진에 바로 들어가지 않습니다.

```text
원천 뉴스 feed
-> AI enrichment
-> should_use=true
-> TriggerEvent
-> judgement engine
```

trigger impact:

- `positive`: 상방 점수
- `negative`: 하방 점수
- `neutral`: 직접 방향 점수 없음

### 현물 반응

현물 반응에서 보는 것:

- KOSPI 변화율
- 강한 섹터
- 약한 섹터
- 외국인 현물 수급

현물 반응은 파생/옵션 결론을 확인하거나 약화시키는 검증 레이어입니다.

## 점수 계산

현재 엔진은 rule-based score 방식입니다.

예시:

- 외국인 선물 순매수: 상방 점수
- 외국인 선물 순매도: 하방 점수
- 옵션 CALL 우위: 상방 점수
- 옵션 PUT 우위: 하방 점수
- 선물 상승 + OI 증가: 상방 강화
- 선물 하락 + OI 증가: 하방 강화
- 긍정 trigger: 상방 점수
- 부정 trigger: 하방 점수
- 강한 섹터가 있으면 하방 점수 일부 완화
- 약한 섹터가 있으면 상방 점수 일부 완화

점수에서 라벨로 바뀌는 기준:

```text
score >= 3  -> 강한 상방
score >= 1  -> 상방 우위
score <= -3 -> 강한 하방
score <= -1 -> 하방 우위
otherwise   -> 중립
```

## Confidence

confidence는 방향 점수와 데이터 상태를 같이 봅니다.

기본:

- score 절대값이 크면 confidence가 높아짐
- score가 약하면 confidence가 낮음

제한:

- live provider missing이면 low
- derivatives/reaction/triggers가 missing/partial/stale이면 confidence를 낮춤
- trigger가 없으면 data limited로 봄

## Data reliability

data reliability는 판단에 쓰인 데이터가 얼마나 정상 수신됐는지를 나타냅니다.

결정 기준:

- live provider missing이면 `partial`
- derivatives 또는 reaction이 missing이면 `partial`
- derivatives 또는 reaction이 stale이면 `stale`
- trigger가 없거나 일부 데이터가 partial이면 `partial`
- 모두 정상이고 trigger도 있으면 `fresh`

## Primary driver

`primary_driver`는 판단의 핵심 원인을 짧게 보여줍니다.

우선순위:

1. 외국인 KOSPI200 선물 수급
2. 옵션 CALL/PUT 압력
3. basis
4. 외국인 현물 수급
5. KOSPI200 선물 변동률
6. 데이터 수신 상태

## Reasons

`reasons`는 판단 근거입니다.

현재 구성:

- derivatives summary
- 대표 negative trigger
- 대표 positive trigger
- reaction summary

최대 3개만 반환합니다.

## Counter evidence

`counter_evidence`는 판단을 약화하거나 반대로 볼 수 있는 근거입니다.

예:

- 하방인데 반도체가 강함
- 상방인데 약한 섹터가 있음
- positive trigger가 하방 압력을 상쇄
- 외국인 선물/현물 수급이 충돌
- 미결제약정이 감소해 추세 확신이 낮음
- 현물 반응이나 뉴스 trigger가 충분하지 않음

최대 2개만 반환합니다.

## Transition condition

전환 조건은 사용자가 “무엇이 바뀌면 판단이 바뀌는가”를 알게 해줍니다.

예:

- 하방 판단이면 PUT 우위 완화 또는 KOSPI200 선물 회복 여부
- 상방 판단이면 CALL 우위 약화 또는 KOSPI200 선물 하락 여부
- 중립이면 옵션 압력과 선물 변동률이 같은 방향으로 누적되는지

## Watch points

watch point는 다음에 봐야 할 항목입니다.

기본:

- KOSPI200 선물 변동률 유지 여부
- basis 0pt 회귀 여부
- 선물 미결제약정 증감
- 주요 옵션 key level

## 중요한 설계 원칙

### 판단 엔진은 원문을 직접 읽지 않습니다

판단 엔진은 RSS XML, Naver 응답, Gemini raw response를 직접 읽지 않습니다.

항상 아래 구조만 봅니다.

```text
DerivativesPressure
TriggerEvent
MarketReaction
```

이렇게 해야 판단 엔진 테스트가 단순해지고, provider 변경이 판단 엔진에 직접 영향을 덜 줍니다.

### AI는 판단 엔진이 아닙니다

AI는 뉴스 후보를 구조화하고 선별합니다. 최종 시장 라벨은 rule-based judgement engine이 만듭니다.

이유:

- 판단 기준을 테스트로 고정하기 위해
- AI 응답 변동성을 제한하기 위해
- 매수/매도 추천처럼 보이지 않게 하기 위해

### 원천 뉴스 feed는 판단 입력이 아닙니다

`/argus/triggers/news`에 보이는 모든 뉴스가 판단에 들어가는 것은 아닙니다.

판단에 들어가는 것은 AI 선별을 거쳐 `TriggerEvent`가 된 항목뿐입니다.

## 향후 보정 포인트

- PCR/OI 가중치 세밀화
- 뉴스 impact별 점수 조정
- connection_strength를 점수에 반영
- 현물 수급과 선물 수급 충돌 처리 고도화
- 장중 사례 기반 threshold 보정
- confidence 설명 문구 세분화
